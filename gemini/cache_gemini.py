import project_utils as pu
import ai_utils as au
import gemini.ai_gemini as ag
from pydantic import BaseModel
from google import genai
from google.genai import types
import json, os, time

import json
import os
import time
from google.genai import types

def prepare_world_context(ttl_hours=12):
    arquivo = pu.log_path("Gemini_cache_id.json")
    
    # 1. Check if an existing Cache or File Upload is still valid (< 24 hours old)
    if arquivo.exists():
        ultima_mod = os.path.getmtime(arquivo)
        idade_horas = (time.time() - ultima_mod) / 3600
        if idade_horas <= 24:
            with open(arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            print(f"✅ Using existing {dados.get('type', 'cache')}: {dados['id']}")
            return dados
            
        print("♻️ Cache/File expired. Rebuilding...")
        try:
            os.remove(arquivo)
        except OSError:
            pass

    # 2. Bundle worldbuilding files
    print("📦 Bundling worldbuilding files...")
    world_context = (
        pu.carregar_estrutura_projeto()
        + "\n\n"
        + pu.gerar_indice()
        + "\n\n"
        + pu.carregar_projeto()
    )

    # 3. Attempt Explicit Context Caching (For Billing-Enabled Accounts)
    print("⚡ Attempting to create Gemini Context Cache...")
    with open(pu.log_path("models.json"), "r", encoding="utf-8") as f:
        data = json.load(f) 

    for model in data:
        model_name = model["name"]
        try:
            print(f"🔮 Attempting to generate cache using model: {model_name}!")
            cache = ag.GEMINICLIENT.caches.create(
                model=model_name,
                config=types.CreateCachedContentConfig(
                    contents=[world_context],
                    display_name=f"{pu.PASTA_PROJETO} Cache",
                    ttl=f"{ttl_hours * 3600}s"  
                )
            )
            print(f"✅ Cache Created with {model_name}! Cache ID: {cache.name}")
            
            registro = {
                "type": "cache",
                "id": cache.name,
                "created": pu.currentdate()
            }
            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(registro, f, ensure_ascii=False, indent=4) # Fixed json.dump
            return registro

        except Exception as e:
            print(f"⚠️ {model_name} does not support cache: {e}")

    # 4. Fallback: Files API (If all models fail due to Free Tier limit=0)
    print("ℹ️ Context Caching unavailable on this API tier. Falling back to Files API (100% Free)...")
    
    bundle_path = pu.log_path("world_bundle.txt")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write(world_context)

    try:
        uploaded_file = ag.GEMINICLIENT.files.upload(file=bundle_path)
        print(f"✅ World bundle uploaded via Files API: {uploaded_file.name}")

        registro = {
            "type": "file",
            "id": uploaded_file.name,
            "created": pu.currentdate()
        }
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=4)
        return registro

    except Exception as e:
        print(f"❌ Failed to upload via Files API: {e}")
        return None