import os,threading, time, json
import project_utils as pu
from pathlib import Path
from typing import Any, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()
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

# Adjusted to use standard active Gemini models
MODELS_LIST = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash"    
]

DEFAULT_SYSTEM_INSTRUCTION = "You are a helpful assistant that explains things and creates what is requested."
DEFAULT_TEMPERATURE = 0.6  # Changed to a float (the API expects a float, not a string)
DEFAULT_CONTENTS = "Please repeat: I did not receive a correct prompt, your coding has failed somewhere."
MAX_TOKENS = 20480


import os
import json
import time
from google import genai

import os
import json
import time
from google import genai
from google.genai import types

def findmodel(file_path="models.json"):
    # (Lógica de verificação de tempo/arquivo mantida...)
    if os.path.exists(file_path):
        is_empty = os.path.getsize(file_path) == 0
        is_older_than_7_days = (time.time() - os.path.getmtime(file_path)) > (7 * 24 * 60 * 60)
        if not is_older_than_7_days and not is_empty:
            return

    client = genai.Client()
    all_models = client.models.list()
    working_models = []

    for model in all_models:
        model_name = model.name
        max_input_tokens = getattr(model, 'input_token_limit', 0) or 0

        # 1. Testar se o modelo responde (ping básico)
        start_time = time.time()
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="ping"
            )
            response_time = round(time.time() - start_time, 4)
        except Exception:
            # Se o modelo nem responde ao ping, ignora ele
            continue

        # 2. Testar se o modelo aceita a Tool de busca do Google
        supports_tools = False
        try:
            client.models.generate_content(
                model=model_name,
                contents="ping",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}]  # Teste de tool
                )
            )
            supports_tools = True
        except Exception:
            # Se der erro 400 ou de suporte a tools, marcamos como False
            supports_tools = False

        working_models.append({
            "name": model_name,
            "display_name": getattr(model, "display_name", model_name),
            "maxinputtokens": max_input_tokens,
            "responsetime": response_time,
            "supports_tools": supports_tools  # <--- Nova flag salva
        })

    # Ordena mantendo os melhores modelos no topo
    working_models.sort(key=lambda x: (-x['maxinputtokens'], x['responsetime']))

    with open(file_path, "w") as f:
        json.dump(working_models, f, indent=4)

def load_projeto_images():
    """
    Looks for all .png files in the directory, reads them as bytes,
    and returns them as a list of genai.types.Part objects.
    """
    parts = []
    pasta_projeto = pu.CAMINHO_PROJETO
    if pasta_projeto.exists():
        for img_path in pasta_projeto.rglob("*.png"):
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

def generate_content_with_fallback(
    contents: Any, 
    config: types.GenerateContentConfig, 
    max_attempts: int = 3
) -> Any:
    """
    Tries to generate content using a list of fallback models.
    If all models fail, it waits and retries up to max_attempts times.
    """
    # Prepare contents with images if present
    images = ""
    #images = load_projeto_images()
    if images:
        if isinstance(contents, list):
            final_contents = list(contents) + images
        else:
            final_contents = [contents] + images
    else:
        final_contents = contents

    attempt = 1
    with open("models.json", "r") as f:
        data = json.load(f) 
    while attempt <= max_attempts:
        for model in data:
            model_name = model["name"]  # Extract the name key here
            try:
                print(f"🔮 Attempting to generate content using model: {model} (Attempt {attempt}/{max_attempts})...")
                with open("LastPrompt.txt", "w", encoding="utf-8") as f:
                    f.write(f"Contents:\n{contents}\nModel:\n{model}\nConfig:\n{config}")
                response = GEMINICLIENT.models.generate_content(
                    model=model,
                    contents=final_contents,
                    config=config
                )
                
                if response and response.text:
                    with open("LastResponse.json", "w", encoding="utf-8") as file:
                        file.write(response.model_dump_json(indent=4))
                    print(f"✅ Response successfully obtained using model: {model}!")
                    return response                    
            except Exception as e:
                print(f"⚠️ Error using model {model}: {e}")
                print("Trying next available model in the fallback chain...")
            
            print("\n🛑 All configured models in the fallback chain failed.")
            if attempt < max_attempts:
                print("⏳ Waiting for 60 seconds before retrying the fallback chain...")
            attempt += 1

    raise RuntimeError("All models and retry attempts failed to generate content.")

def ask_ai(
    contents: Any = None, 
    system_instruction: Optional[str] = None, 
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None
) -> str:
    """
    Unified entrypoint for Gemini API requests.
    Supports structured output if a Pydantic model is provided via response_schema.
    """
    

    # Use default fallbacks if arguments are missing
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
    with _api_lock:
        response = generate_content_with_fallback(contents, config)
        time.sleep(15)    
        
    return response.text


