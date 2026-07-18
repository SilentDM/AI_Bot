import time
from pathlib import Path
from google.genai import types
import os

from google.genai import types
import time

def ask_gemini(
    client,
    prompt,
    system_instruction="",
    extra_contents=None,
    models_list=None,
    temperature=0.5,
    max_output_tokens=20480
):

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens
    )

    contents = []

    if extra_contents:
        contents.extend(extra_contents)

    contents.append(prompt)

    response = generate_content_with_fallback(
        client=client,
        contents=contents,
        config=config,
        models_list=models_list
    )

    return response.text

def load_phaeton_images():
    """
    Looks for all .png files in the Phaeton directory, reads them as bytes,
    and returns them as a list of genai.types.Part objects.
    """
    parts = []
    pasta_phaeton = Path(os.getcwd()) / "phaeton"
    if pasta_phaeton.exists():
        for img_path in pasta_phaeton.rglob("*.png"):
            try:
                print(f"🖼️ [Local API] Automatically attaching map/region image: {img_path.name}")
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

def generate_content_with_fallback(client, contents, config=None, models_list=None):
    """
    Tries to generate content using a list of fallback models.
    If a model fails, it tries the next one.
    If all models fail, it waits for 60 seconds and recursively tries again.
    """
    if models_list is None:
        # Standard robust fallback list of model tags
        models_list = ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    # Automatically read and load any map or region .png files from Phaeton directory
    images = load_phaeton_images()
    if images:
        if isinstance(contents, list):
            contents = list(contents) + images
        else:
            contents = [contents] + images

    attempt = 1
    while True:
        for model in models_list:
            try:
                print(f"🔮 Attempting to generate content using model: {model} (Attempt {attempt})...")
                if config:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config
                    )
                else:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents
                    )
                if response and response.text:
                    print(f"✅ Response successfully obtained using model: {model}!")
                    return response
            except Exception as e:
                print(f"⚠️ Error using model {model}: {e}")
                print("Trying next available model in the fallback chain...")
        
        print("\n🛑 All configured models in the fallback chain failed due to high load, rate limits, or network errors.")
        print("⏳ Waiting for 60 seconds before retrying the fallback chain...")
        time.sleep(60)
        attempt += 1
