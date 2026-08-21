import json, re
import engine.expander as ex
import engine.project_utils as pu
import core.ai_utils as au
import core.cache_gemini as cg
import ui.settings as st  
from typing import Optional
from pathlib import Path
from pydantic import BaseModel
from typing import Literal, List

def resolver_caminho(path_str):
    caminho = Path(path_str)
    raiz = Path(pu.CAMINHO_PROJETO).resolve()

    if caminho.is_absolute():
        return caminho.resolve()

    partes = caminho.parts
    if partes and partes[0] == pu.PASTA_PROJETO:
        caminho = Path(*partes[1:]) if len(partes) > 1 else Path("")

    return (raiz / caminho).resolve()

def obter_conteudo_template(nome_template: Optional[str]) -> str:
    if not nome_template or nome_template.lower() == "nenhum":
        return ""

    nome_arquivo = f"{nome_template.lower().strip()}.md"
    locais_possiveis = [Path(pu.CAMINHO_PROJETO) / "Templates" / nome_arquivo, pu.PASTA_TEMPLATES / nome_arquivo]

    for caminho in locais_possiveis:
        if caminho.exists() and caminho.is_file():
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    return f"\n\n{f.read().strip()}"
            except Exception as e:
                print(f"⚠️ Erro ao ler template {caminho}: {e}")
                return ""
    return ""

class Action(BaseModel):
    type: Literal["CreateFolder", "CreateFile", "ImproveFile"]
    path: str
    priority: int
    objective: str
    template: Optional[Literal["aventura", "cidade", "local", "npc", "reinado", "nenhum"]] = "nenhum"

class ActionPlan(BaseModel):
    actions: List[Action]

def taskplanner(reason: Optional[str] = "Completar o Projeto"):
    config = st.carregar_configuracoes()
    allow_folder = config.get("wb_allow_create_folder", True)
    allow_file = config.get("wb_allow_create_file", True)
    allow_improve = config.get("wb_allow_improve_file", True)

    ferramentas_permitidas = []
    if allow_folder: ferramentas_permitidas.append("CreateFolder")
    if allow_file: ferramentas_permitidas.append("CreateFile")
    if allow_improve: ferramentas_permitidas.append("ImproveFile")

    if not ferramentas_permitidas:
        print("⚠️ Todas as ferramentas do WorldBuilder estão desabilitadas.")
        return

    texto_ferramentas = "\n".join(ferramentas_permitidas)
    instrucao_restricao_pastas = ""
    if not allow_folder:
        instrucao_restricao_pastas = "REGRA: A criação de novas pastas está DESABILITADA. Escolha apenas pastas existentes."

    if pu.is_cancelled():
        return

    instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o projeto e identifique quais ações são necessárias para: {reason}

{instrucao_restricao_pastas}

REGRA DE NOMES E WIKILINKS:
Antes de sugerir CreateFolder ou CreateFile, verifique o índice fornecido.
Prefira nomes curtos e elegantes que possam ser citados facilmente como Wikilinks (ex: "Catedral de Prata", "Arquimago Varis").

FERRAMENTAS PERMITIDAS:
{texto_ferramentas}
"""

    corpo_usuario = f"Analise a estrutura atual do projeto no cache. Objetivo: {reason}"

    try:    
        resposta = au.ask_ai(
            contents=corpo_usuario,
            system_instruction=instrucao_sistema,
            temperature=0.4,
            response_schema=ActionPlan,
            use_world_context=True
        )
        texto_limpo = ex.remover_markdown_fences(str(resposta))
        plano = ActionPlan.model_validate_json(texto_limpo)
        
        if plano.actions:
            actions = sorted([a.model_dump() for a in plano.actions], key=lambda x: x.get("priority", 0), reverse=True)
            enactchoices(actions)
    except Exception as e:
        print(f"Erro na resposta do TaskPlanner: {e}")

    ex.processar_arquivos()

def enactchoices(actions):
    for action in actions:
        if pu.is_cancelled():
            return
        tipo = action["type"]
        path = action.get("path", "")
        objective = action.get("objective", "")
        template = action.get("template", "nenhum")

        registro = {
            "timestamp": pu.currentdate(),
            "action": tipo,
            "path": path,
            "template": template,
            "objective": objective
        }
        pu.anexar_jsonl_seguro(pu.log_path("changelog.jsonl"), registro, pu.LOCK_CHANGELOG)

        if tipo == "CreateFolder":
            createfolder(action["path"], objective)
        elif tipo == "CreateFile":
            createfile(action["path"], objective, template)
        elif tipo == "ImproveFile":
            improvefile(action["path"], objective)
    
        ex.processar_arquivos()
        cg.force_rebuild_world_context()

def createfolder(path, reason):
    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        destino = resolver_caminho(path)

        if not destino.is_relative_to(raiz): return False
        if pu.existe_nome_parecido(destino.name, destino.parent): return False
        if destino.exists(): return False

        destino.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Erro ao criar pasta: {e}")
        return False

def createfile(path, reason, template="nenhum"):
    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        arquivo = resolver_caminho(path).with_suffix(".md")

        if not arquivo.is_relative_to(raiz): return False
        if not arquivo.parent.exists(): arquivo.parent.mkdir(parents=True, exist_ok=True)
        if pu.existe_nome_parecido(arquivo.name, arquivo.parent): return False
        if arquivo.exists(): return False

        titulo = arquivo.stem
        conteudo_template = obter_conteudo_template(template)

        conteudo = f"""# {titulo}
status: rascunho
---
<-- TO DO: {reason}
{conteudo_template}
"""
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo)

        improvefile(path, reason)
        return True
    except Exception as e:
        print(f"❌ Erro ao criar arquivo {path}: {e}")
        return False

def improvefile(path, reason="Melhorar o arquivo!"):
    arquivo = resolver_caminho(path)

    if ex.esta_em_processamento(arquivo):
        return False

    if not arquivo.exists() or not arquivo.is_file():
        return False

    ex.marcar_processamento(arquivo, True)

    try:
        with open(arquivo, "r", encoding="utf-8", errors="ignore") as f:
            arquivoatual = f.read()

        instrucoes_globais = f"""
Você é um Mestre de Mesa (DM) de D&D experiente.
Seu objetivo é melhorar o arquivo: {arquivo.name}
Motivação: {reason}

# REGRAS DE FORMATAÇÃO E WIKILINKS:
- Organize o texto com títulos (#, ##, ###).
- Use citações (> texto) para caixas de lore ou rumores.
- Use negrito (**termo**) em nomes importantes.
- CRIE WIKILINKS [[Nome do Conceito]] sempre que citar NPCs, lugares ou facções do universo.
- Mantenha total consistência com o restante do mundo.
"""
        prompt_conteudo = f"OBJETIVO: {reason}\n\nCONTEÚDO ORIGINAL:\n{arquivoatual}"

        texto_expandido = au.ask_ai(contents=prompt_conteudo, system_instruction=instrucoes_globais, temperature=0.4)

        if texto_expandido:
            texto_limpo = ex.remover_markdown_fences(texto_expandido)
            
            # 1. Salva cópia de backup na pasta logs/history/
            ex.salvar_snapshot_historico(arquivo)

            # 2. Atualiza o arquivo ORIGINAL in-place (preserva o nome para o Obsidian!)
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(texto_limpo)

            print(f"✅ Arquivo atualizado in-place com sucesso: {arquivo.name}")
            return True
        else:
            return False

    except Exception as e:
        print(f"Erro ao processar {arquivo.name}: {e}")
        return False
    finally:
        ex.marcar_processamento(arquivo, False)