import os,threading, time, json
import engine.project_utils as pu
from typing import Any, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types, errors
import core.cache_gemini as cg
from dotenv import load_dotenv
load_dotenv(pu.PROJECT_ROOT / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
_faltando = []
if not GOOGLE_API_KEY:
    _faltando.append("GOOGLE_API_KEY")
if _faltando:
    raise SystemExit(
        f"❌ Erro de configuração: variável(is) ausente(s) no .env: {', '.join(_faltando)}.\n"
        f"Verifique se o arquivo .env existe na raiz do projeto e contém essas chaves."
    )
GEMINICLIENT = genai.Client(api_key=GOOGLE_API_KEY)

_api_lock = threading.Lock()

DEFAULT_SYSTEM_INSTRUCTION = "You are a helpful assistant that explains things and creates what is requested."
DEFAULT_TEMPERATURE = 0.6  # Changed to a float (the API expects a float, not a string)
DEFAULT_CONTENTS = "Please repeat: I did not receive a correct prompt, your coding has failed somewhere."
MAX_TOKENS = 20480
_last_call_time = 0

def _is_rate_limit_error(e: Exception) -> bool:
    """Detecta se a exceção é referente a estouro de limite de taxa (HTTP 429 / Quota)."""
    err_str = str(e).lower()
    if isinstance(e, errors.APIError):
        if getattr(e, "code", None) == 429:
            return True
    return any(
        kw in err_str
        for kw in ["429", "resource_exhausted", "quota", "rate limit", "too many requests"]
    )

def findmodel(file_path=pu.log_path("models.json")):
    # 1. Check cache freshness
    print("Verificando lista de modelos disponíveis!")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                is_empty = not data
        except Exception:
            is_empty = True
        is_older_than_7_days = (time.time() - os.path.getmtime(file_path)) > (7 * 24 * 60 * 60)
        if not is_older_than_7_days and not is_empty:
            print("Lista de modelos disponíveis OK!")
            return
    print("Lista de modelos disponíveis NOT OK! Criando nova lista!")
    all_models = GEMINICLIENT.models.list()
    print("all models ok!")
    working_models = []

    for model in all_models:
        model_name = model.name
        max_input_tokens = getattr(model, 'input_token_limit', 0) or 0
        support_image = "IMAGE" in (getattr(model, "input_modalities", []) or [])
        print(f"Testando modelo: {model_name}")
        if "gemini" not in model_name.lower() or "embedding" in model_name.lower():
            continue
        else:
            start_time = time.time()
            try:
                GEMINICLIENT.models.generate_content(
                    model=model_name,
                    contents="ping"
                )
                response_time = round(time.time() - start_time, 4)
            except Exception as e:
                # Skip model if it fails to respond to a basic prompt
                print(f"Skipping {model_name}: {e}")
                continue

            # Step 2: Google Search Tool Test
            supports_tools = False
            try:
                GEMINICLIENT.models.generate_content(
                    model=model_name,
                    contents="ping",
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                supports_tools = True
            except Exception:
                supports_tools = False

            working_models.append({
                "name": model_name,
                "display_name": getattr(model, "display_name", model_name),
                "maxinputtokens": max_input_tokens,
                "responsetime": response_time,
                "supports_tools": supports_tools,
                "supports_images": support_image  
            })

            # Brief pause to respect Free Tier RPM limits during model discovery
            time.sleep(1)

            # Sort models: Most input tokens first, then fastest response time
            working_models.sort(
                key=lambda x: (
                    not x.get("supports_tools", False),
                    not x.get("supports_images", False),
                    -x.get("maxinputtokens", 0),
                    x.get("responsetime", 9999)
                )
            )

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(working_models, f, indent=4)
    print("Lista de modelos disponíveis Criada!")

def generate_content_with_fallback(contents: Any, config: types.GenerateContentConfig, cache_model: Optional[str] = None) -> Any:
    try:
        with open(pu.log_path("models.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            raise ValueError("models.json está vazio")
    except Exception as e:
        print(f"Problema com models.json: {e}")
        print("Recriando lista de modelos...")
        findmodel()
        with open(pu.log_path("models.json"), "r", encoding="utf-8") as f:
            data = json.load(f)

    for model in data:
        model_name = model["name"]
        print(f"Tentando gerar conteúdo no modelo: {model_name}...")
        config_to_use = config.model_copy(deep=True)

        # 🛡️ PROTEÇÃO CONTRA INCOMPATIBILIDADE DE CACHE:
        # Se o cache foi gerado para outro modelo (ex: Modelo 1), limpamos a propriedade
        # 'cached_content' no Modelo 2 para evitar que a API rejeite a chamada.
        if config_to_use.cached_content and cache_model and cache_model != model_name:
            print(f"Cache {config_to_use.cached_content} pertence ao modelo '{cache_model}'. Removendo cache para tentar com '{model_name}'.")
            config_to_use.cached_content = None

        # Ferramentas de busca
        if model.get("supports_tools", False):
            config_to_use.tools = [types.Tool(google_search=types.GoogleSearch())]
        else:
            config_to_use.tools = []

        try:
            response = GEMINICLIENT.models.generate_content(
                model=model_name,
                contents=contents,
                config=config_to_use
            )

            if response and response.text:
                return response

        except Exception as e:
            if _is_rate_limit_error(e):
                print(f"Rate Limit atingido no modelo {model_name}. Pulando imediatamente para o próximo...")
            else:
                print(f"Erro no modelo {model_name}: {e}")
        
        print(f"🔄 Passando para o próximo modelo da cadeia de fallback...")

    raise RuntimeError("Todos os modelos e tentativas de fallback falharam em gerar conteúdo.")

def ask_ai(
    contents: Any = None, 
    system_instruction: Optional[str] = None, 
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None,
    use_world_context: Optional[bool] = True
) -> str:
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
            world_context = cg.prepare_world_context()
            config = config.model_copy(deep=True)
            
            if world_context["type"] == "file":
                uploaded_file = GEMINICLIENT.files.get(name=world_context["id"])
                contents_to_send = [uploaded_file, contents]
            elif world_context["type"] == "cache":
                config.cached_content = world_context["id"]
                cache_model = world_context.get("model")  # 👈 Passa o nome do modelo criador do cache
        except Exception as e:
            print(f"⚠️ World Context unavailable: {e}")
            print("Continuing without cache or file.")
        
    with _api_lock:
        response = generate_content_with_fallback(contents_to_send, config, cache_model=cache_model)
        
    return response.text




