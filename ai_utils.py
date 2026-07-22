import os,threading, time
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
    while attempt <= max_attempts:
        for model in MODELS_LIST:
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

def ask_gemini(
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


