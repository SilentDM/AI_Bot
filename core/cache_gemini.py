import engine.project_utils as pu
import core.ai_gemini as ag
from google.genai import types
import json, os, time

def force_rebuild_world_context():
    arquivo = pu.log_path("Gemini_cache_id.json")
    try:
        if arquivo.exists():
            print("Deletando o contexto criado!")
            arquivo.unlink()
    except Exception as e:
        print(f"Erro removendo arquivo:{e}")
    return prepare_world_context()

def prepare_world_context(is_dm: bool = True, ttl_hours=12):
    arquivo = pu.log_path("Gemini_cache_id.json")
    
    # 1. Check if an existing Cache or File Upload is still valid (< 24 hours old)
    if arquivo.exists():
        ultima_mod = os.path.getmtime(arquivo)
        idade_horas = (time.time() - ultima_mod) / 3600
        if idade_horas <= 12:  # Ajustado para bater com ttl_hours
            with open(arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            chave = "dm" if is_dm else "player"
            if chave in dados:
                return dados[chave]
            
        print("O Cache/bundle já está velho! Recriando!")
        try:
            os.remove(arquivo)
        except OSError:
            pass

    # 2. Bundle worldbuilding files
    print("Criando o bundle!")
    context_dm = (
        pu.carregar_estrutura_projeto() + "\n\n" + 
        pu.gerar_indice() + "\n\n" + 
        pu.carregar_projeto(is_dm=True)
    )

    context_player = (
        pu.carregar_estrutura_projeto() + "\n\n" + 
        pu.gerar_indice() + "\n\n" + 
        pu.carregar_projeto(is_dm=False)
    )

    # 3. Attempt Explicit Context Caching (For Billing-Enabled Accounts)
    print("Fazendo upload do Bundle!")
    data = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])
    if not data:
        print("Recriando lista de modelos...")
        ag.findmodel()
        data = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])

    #for model in data:
        #model_name = model["name"]
        #try:
            #print(f"Tentando gerar Cache explícito com o modelo: {model_name}")
            #cache_dm_path = ag.GEMINICLIENT.caches.create(
                #model=model_name,
                #config=types.CreateCachedContentConfig(
                    #contents=[context_dm],
                    #display_name=f"{pu.PASTA_PROJETO} Cache(DM)",
                    #ttl=f"{ttl_hours * 3600}s"  
                #)
            #)
            #cache_player_path = ag.GEMINICLIENT.caches.create(
                            #model=model_name,
                            #config=types.CreateCachedContentConfig(
                                #contents=[context_player],
                                #display_name=f"{pu.PASTA_PROJETO} Cache(Player)",
                                #ttl=f"{ttl_hours * 3600}s"  
                            #)
                        #)
            
            #registro = {
                #"dm": {"type": "cache","id": cache_dm_path.name,"model": model_name,"created": pu.currentdate()},
                #"player":{"type": "cache","id": cache_player_path.name,"model": model_name,"created": pu.currentdate()}
            #}
            #with open(arquivo, "w", encoding="utf-8") as f:
                #json.dump(registro, f, ensure_ascii=False, indent=4)
            #print(f"Context Cache foi gerado com sucesso!")
            #return registro["dm" if is_dm else "player"]

        #except Exception as e:
            #print(f"{model_name} não suporta cache: {e}")

    bundle_dm_path = pu.log_path("world_bundle_dm.txt")
    bundle_player_path = pu.log_path("world_bundle_player.txt")

    with open(bundle_dm_path, "w", encoding="utf-8") as f:
        f.write(context_dm)

    with open(bundle_player_path, "w", encoding="utf-8") as f:
        f.write(context_player)

    try:
        client = ag.get_gemini_client()
        if not client:
            print("Sem chave de API para upload do Bundle.")
            return None
        uploaded_dm = ag.GEMINICLIENT.files.upload(file=bundle_dm_path)
        uploaded_player = ag.GEMINICLIENT.files.upload(file=bundle_player_path)

        registro = {
            "dm": {"type": "file", "id": uploaded_dm.name, "created": pu.currentdate()},
            "player": {"type": "file", "id": uploaded_player.name, "created": pu.currentdate()}
        }

        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=4)
        print("Tudo certo, Bundle criado!")
        return registro["dm" if is_dm else "player"]

    except Exception as e:
        print(f"Failed to upload bundles via Files API: {e}")
        return None