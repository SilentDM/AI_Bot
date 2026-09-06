import os, threading, time, json, concurrent.futures
import engine.project_utils as pu
from typing import Any, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types, errors
import core.cache_gemini as cg
from dotenv import load_dotenv

load_dotenv(pu.PROJECT_ROOT / ".env")

_api_lock = threading.Lock()

DEFAULT_SYSTEM_INSTRUCTION = "You are a helpful assistant that explains things and creates what is requested."
DEFAULT_TEMPERATURE = 0.6
DEFAULT_CONTENTS = "Please repeat: I did not receive a correct prompt, your coding has failed somewhere."
MAX_TOKENS = 20480

# Em core/ai_gemini.py

def get_gemini_client(timeout_seconds: Optional[int] = 90):
    """
    Obtém o cliente Gemini atualizado dinamicamente.
    Se timeout_seconds for None, utiliza o tempo nativo da Google/HTTPX.
    Caso contrário, converte segundos para milissegundos.
    """
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None

    if timeout_seconds is not None:
        # 90 segundos = 90_000 milissegundos
        http_opts = types.HttpOptions(timeout=timeout_seconds * 1000)
    else:
        # Padrão nativo do SDK / Google
        http_opts = types.HttpOptions()

    return genai.Client(api_key=api_key, http_options=http_opts)

def _is_rate_limit_error(e: Exception) -> bool:
    err_str = str(e).lower()
    if isinstance(e, errors.APIError):
        if getattr(e, "code", None) == 429:
            return True
    return any(
        kw in err_str
        for kw in ["429", "resource_exhausted", "quota", "rate limit", "too many requests"]
    )

def _criterio_ordenacao_eficiencia(m: dict):
    """
    Ordena os modelos priorizando a eficiência real observada:
    1. Maior taxa de sucesso (menos falhas e timeouts)
    2. Menor tempo médio de resposta (mais veloz)
    3. Maior score de capacidade/contexto (inteligência do modelo)
    """
    tentativas = max(1, m.get("attempts", 1))
    sucessos = m.get("success", 0)
    taxa_sucesso = sucessos / tentativas

    tempo_resposta = m.get("responsetime", 9999.0)
    score_qualidade = m.get("quality_score", 0)

    # Ordenamos por:
    # -taxa_sucesso -> decrescente (ex: 1.0 antes de 0.8)
    # tempo_resposta -> crescente (ex: 1.2s antes de 4.5s)
    # -score_qualidade -> decrescente (desempate pela capacidade do modelo)
    return (-taxa_sucesso, tempo_resposta, -score_qualidade)

def _calcular_score_modelo(model_name: str, max_tokens: int) -> int:
    name = model_name.lower()
    score = 0
    if max_tokens >= 1_000_000:
        score += 5000
    elif max_tokens >= 500_000:
        score += 3000
    elif max_tokens >= 128_000:
        score += 1000
    else:
        score -= 2000

    if "pro" in name:
        score += 4000
    elif "thinking" in name or "reasoning" in name:
        score += 3500
    elif "flash" in name and "8b" not in name:
        score += 1500
    elif "flash-8b" in name or "lite" in name:
        score += 200

    if "2.5" in name:
        score += 1000
    elif "2.0" in name:
        score += 800
    elif "1.5" in name:
        score += 500

    if "latest" in name or "preview" in name:
        score += 300
    if "exp" in name:
        score += 200

    if "vision" in name or "imagen" in name or "audio" in name:
        score -= 5000

    return score

def findmodel(file_path=pu.log_path("models.json")):
    client = get_gemini_client(timeout_seconds=90)
    client_fast = get_gemini_client(timeout_seconds=15)
    
    if not client:
        print("Nenhuma GOOGLE_API_KEY configurada. Pulando ranqueamento de modelos.")
        return

    print("Verificando e ranqueando modelos disponíveis para Worldbuilding...")
    
    data = pu.ler_json_seguro(file_path, pu.LOCK_MODELS, padrao=None)
    is_empty = not data

    is_older_than_7_days = False
    if file_path.exists():
        is_older_than_7_days = (time.time() - os.path.getmtime(file_path)) > (7 * 24 * 60 * 60)

    if not is_older_than_7_days and not is_empty:
        print("Lista de modelos disponíveis OK!")
        return

    print("Atualizando compêndio de modelos da API...")
    try:
        all_models = client.models.list()
    except Exception as e:
        print(f"Erro ao listar modelos da API: {e}")
        return

    working_models = []
    for model in all_models:
        model_name = model.name
        max_input_tokens = getattr(model, 'input_token_limit', 0) or 0
        
        name_lower = model_name.lower()
        if any(w in name_lower for w in ["embedding", "robotics", "aqa", "realtime", "tts"]):
            continue
        if "gemini" not in name_lower:
            continue

        start_time = time.time()
        try:
            client_fast.models.generate_content(model=model_name, contents="ping")
            response_time = round(time.time() - start_time, 4)
        except Exception:
            continue

        # Apenas registramos se suporta ferramentas como dado informativo,
        # sem usar isso como critério de prioridade de fila
        supports_tools = False
        try:
            client_fast.models.generate_content(
                model=model_name,
                contents="ping",
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            )
            supports_tools = True
        except Exception:
            supports_tools = False

        quality_score = _calcular_score_modelo(model_name, max_input_tokens)

        working_models.append({
            "name": model_name,
            "display_name": getattr(model, "display_name", model_name),
            "maxinputtokens": max_input_tokens,
            "responsetime": response_time,
            "supports_tools": supports_tools,
            "quality_score": quality_score,
            "attempts": 1,
            "success": 1
        })
        time.sleep(0.3)

    # 🟢 Nova ordenação focada exclusivamente em Eficiência:
    working_models.sort(key=_criterio_ordenacao_eficiencia)

    pu.salvar_json_seguro(file_path, working_models, pu.LOCK_MODELS)
    print("Lista de modelos ranqueada com foco em eficiência!")

def improvemodel(model, success, response_time=None):
    file_path = pu.log_path("models.json")
    if not file_path.exists():
        return

    data = pu.ler_json_seguro(file_path, pu.LOCK_MODELS, padrao=[])
    if not data:
        return

    for m in data:
        if m.get("name") == model:
            if response_time is not None and success:
                # Média móvel ponderada simples para amortecer oscilações de rede
                tempo_anterior = m.get("responsetime", response_time)
                m["responsetime"] = round((tempo_anterior * 0.7) + (response_time * 0.3), 4)
                
            m["attempts"] = m.get("attempts", 0) + 1
            m["success"] = m.get("success", 0) + (1 if success else 0)
            m["quality_score"] = _calcular_score_modelo(m["name"], m.get("maxinputtokens", 0))
            
            # 🟢 Reordena a fila inteira dinamicamente com base no desempenho real
            data.sort(key=_criterio_ordenacao_eficiencia)
            
            pu.salvar_json_seguro(file_path, data, pu.LOCK_MODELS)
            return

def generate_content_with_fallback(contents: Any, config: types.GenerateContentConfig, cache_model: Optional[str] = None) -> Any:
    # 🟢 Timeout estendido para 90 segundos nas gerações reais
    # Se preferir o tempo 100% nativo da Google, use: client = get_gemini_client(timeout_seconds=None)
    client = get_gemini_client(timeout_seconds=90)
    
    if not client:
        raise ValueError("Nenhuma GOOGLE_API_KEY configurada.")

    data = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])
    if not data:
        findmodel()
        data = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])

    if not data:
        raise ValueError("models.json está vazio ou indisponível")

    for model in data:
        model_name = model["name"]
        config_to_use = config.model_copy(deep=True)

        if config_to_use.cached_content and cache_model and cache_model != model_name:
            config_to_use.cached_content = None

        if model.get("supports_tools", False):
            config_to_use.tools = [types.Tool(google_search=types.GoogleSearch())]
        else:
            config_to_use.tools = []

        start_time = time.time()
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config_to_use
            )
            response_time = round(time.time() - start_time, 4)
            improvemodel(model_name, True, response_time)
            if response and response.text:
                return response

        except Exception as e:
            response_time = round(time.time() - start_time, 4)
            improvemodel(model_name, False, response_time)
            
            err_msg = str(e).lower()
            if _is_rate_limit_error(e):
                print(f"Rate Limit atingido no modelo {model_name}. Pulando para o próximo...")
            elif "timeout" in err_msg or "timed out" in err_msg or "deadline" in err_msg:
                print(f"⏱️ Timeout no modelo {model_name} após {response_time}s. Pulando para o próximo...")
            else:
                print(f"Erro no modelo {model_name}: {e}")

    raise RuntimeError("Todos os modelos de fallback falharam em gerar conteúdo.")

def ask_ai(
    contents: Any = None, 
    system_instruction: Optional[str] = None, 
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None,
    use_world_context: Optional[bool] = True,
    is_dm: Optional[bool] = True
) -> str:
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        return "❌ Nenhuma chave de API da IA (GOOGLE_API_KEY) foi configurada. Acesse a aba 'Opções' para cadastrar sua chave."

    if not system_instruction:
        system_instruction = DEFAULT_SYSTEM_INSTRUCTION
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if contents is None:
        contents = DEFAULT_CONTENTS
    
    config_args = {
        "system_instruction": system_instruction,
        "temperature": temperature,
        "max_output_tokens": MAX_TOKENS
    }

    if response_schema:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = response_schema
        
    config = types.GenerateContentConfig(**config_args)
    contents_to_send = contents
    cache_model = None

    if use_world_context:
        try:
            world_context = cg.prepare_world_context(is_dm=is_dm)
            client = get_gemini_client()
            if world_context and client:
                config = config.model_copy(deep=True)
                if world_context.get("type") == "file":
                    uploaded_file = client.files.get(name=world_context["id"])
                    contents_to_send = [uploaded_file, contents]
                elif world_context.get("type") == "cache":
                    config.cached_content = world_context["id"]
                    cache_model = world_context.get("model")
        except Exception as e:
            print(f"⚠️ World Context não disponível: {e}")
        
    with _api_lock:
        response = generate_content_with_fallback(contents_to_send, config, cache_model=cache_model)
        
    return response.text