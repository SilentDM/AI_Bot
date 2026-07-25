import os,threading, time, json
import engine.project_utils as pu
from typing import Any, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types
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
        if "gemini" not in model_name:
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
                "supports_images": support_image  # Fixed lowercase casing
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

def load_projeto_images():
    parts = []
    pasta_projeto = pu.CAMINHO_PROJETO
    if pasta_projeto.exists():
        print("Carregando Imagens para o projeto!")
        for img_path in pasta_projeto.rglob("*.png", ".jpg", ".webp", ".jpeg"):
            try:
                #print(f"🖼️ [Local API] Automatically attaching map/region image: {img_path.name}")
                with open(img_path, "rb") as f:
                    img_data = f.read()
                parts.append(
                    types.Part.from_bytes(
                        data=img_data,
                        mime_type="image/png"
                    )
                )
            except Exception as e:
                print(f"⚠️ Error loading image {img_path.name}: {e}")
    return parts

def generate_content_with_fallback(contents: Any, config: types.GenerateContentConfig, max_attempts: int = 3) -> Any:
    attempt = 1
    try:
        with open(pu.log_path("models.json"),"r",encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            raise ValueError("models.json está vazio")
    except Exception as e:
        print(f"Problema com models.json: {e}")
        print("Recriando lista de modelos...")
        findmodel()
        with open(pu.log_path("models.json"),"r",encoding="utf-8") as f:
            data = json.load(f)
        
    while attempt <= max_attempts:
        for model in data:
            model_name = model["name"]  # Extract the name key here
            print(f"🔮 Attempting to generate content using model: {model}!")
            if model.get("supports_images", False):
                print("Esse modelo suporta imagens!")
                images = load_projeto_images()
                if images:
                    if isinstance(contents, list):
                        final_contents = list(contents) + images
                    else:
                        final_contents = [contents] + images
                else:
                    final_contents = contents
            else:
                final_contents = contents
    
            config_to_use = config.model_copy(deep=True)
            if model.get("supports_tools", False):
                config_to_use.tools = [
                    types.Tool(google_search=types.GoogleSearch())
                ]
            else:
                config_to_use.tools = []
                print(f"🔒 Tools unavailable for {model_name}")
            try:
                print(f"🔮 (Attempt {attempt}/{max_attempts})...")
                with open("LastPrompt.txt", "w", encoding="utf-8") as f:
                    f.write(f"Contents:\n{contents}\nModel:\n{model}\nConfig:\n{config_to_use}")
                response = GEMINICLIENT.models.generate_content(
                    model=model_name,
                    contents=final_contents,
                    config=config_to_use
                )
                
                if response and response.text:
                    with open(pu.log_path("LastResponse.json"), "w", encoding="utf-8") as file:
                        file.write(response.model_dump_json(indent=4))
                    print(f"🔮 Attempting model: \n"
                        f"{model_name} | "
                        f"Tools: {model.get('supports_tools', False)} | "
                        f"Tokens: {model.get('maxinputtokens')} | "
                        f"Response Time: {model.get('responsetime')}"
                    )
                    return response                    
            except Exception as e:
                print(f"⚠️ Error using model {model}: {e}")
                print("Trying next available model in the fallback chain...")
            
            print("\n🛑 All configured models in the fallback chain failed.")
        if attempt < max_attempts:
            attempt += 1

    raise RuntimeError("All models and retry attempts failed to generate content.")

def ask_ai(
    contents: Any = None, 
    system_instruction: Optional[str] = None, 
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None,
    use_world_context: Optional[bool]=True
) -> str:
    if not system_instruction:
        system_instruction = DEFAULT_SYSTEM_INSTRUCTION
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if contents is None:
        contents = DEFAULT_CONTENTS
    
    # Build configuration arguments
    config_args = {
        "system_instruction": system_instruction,
        "temperature": temperature,
        "max_output_tokens": MAX_TOKENS
    }

    # If a schema is specified, configure the response output format
    if response_schema:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = response_schema
    config = types.GenerateContentConfig(**config_args)
    contents_to_send = contents
    if use_world_context:
        try:
            world_context = cg.prepare_world_context()
            config = config.model_copy(deep=True)
            
            if world_context["type"] == "file":
                uploaded_file = GEMINICLIENT.files.get(name=world_context["id"])
                contents_to_send = [uploaded_file,contents]
            elif world_context["type"] == "cache":
                config.cached_content = world_context["id"]
        except Exception as e:
            print(f"⚠️ World Context unavailable: {e}")
            print("Continuing without cache or file.")
        
    with _api_lock:
        response = generate_content_with_fallback(contents_to_send, config)
        time.sleep(15)    
        
    return response.text




