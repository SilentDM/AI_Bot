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
    """
    Normaliza um caminho sugerido pela IA para garantir que ele sempre
    seja interpretado como relativo à pasta raiz do projeto (CAMINHO_PROJETO).
    """
    caminho = Path(path_str)
    raiz = Path(pu.CAMINHO_PROJETO).resolve()

    if caminho.is_absolute():
        return caminho.resolve()

    partes = caminho.parts

    if partes and partes[0] == pu.PASTA_PROJETO:
        caminho = Path(*partes[1:]) if len(partes) > 1 else Path("")

    return (raiz / caminho).resolve()

def obter_conteudo_template(nome_template: Optional[str]) -> str:
    """Busca e retorna o conteúdo do arquivo de template (.md) dentro da pasta Templates."""
    if not nome_template or nome_template.lower() == "nenhum":
        return ""

    nome_arquivo = f"{nome_template.lower().strip()}.md"

    locais_possiveis = [Path(pu.CAMINHO_PROJETO) / "Templates" / nome_arquivo, pu.PASTA_TEMPLATES / nome_arquivo]

    for caminho in locais_possiveis:
        if caminho.exists() and caminho.is_file():
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    conteudo = f.read().strip()
                    print(f"📑 Template '{nome_template}' aplicado a partir de: {caminho.name}")
                    return f"\n\n{conteudo}"
            except Exception as e:
                print(f"⚠️ Erro ao ler template {caminho}: {e}")
                return ""

    print(f"⚠️ Template '{nome_template}' solicitado, mas '{nome_arquivo}' não foi encontrado na pasta Templates.")
    return ""

def iterationschoice(reason: Optional[str] = "O projeto esteja concluído"):
    print("Iterations Iniciado!")
    numero = 1
    instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o estado atual do projeto e estime quantas iterações de expansão são necessárias para que: 
{reason}.
Responda apenas um número inteiro entre 1 e 10.
"""
    corpo_usuario = f"""
Utilize o projeto carregado no cache.

Critérios:
- Regiões
- Cidades
- NPCs
- História
- Potencial para aventuras

Objetivo:
{reason}

Quantas iterações ainda são necessárias?
Responda apenas um número.
"""
    try:
        resposta = au.ask_ai(
            contents=corpo_usuario,
            system_instruction=instrucao_sistema,
            temperature=0.35,
            use_world_context=True
        )
        match = re.search(r"\d+", str(resposta))
        if not match:
            print("⚠️ A IA não retornou um número válido de iterações. Usando 1 como padrão.")
        else:
            numero = max(1, min(10, int(match.group())))
        print(f"Gemini analisou e decidiu que precisa de: {numero} etapas para melhorar o projeto")
        print("Iterations Concluído!")
        return numero
    except Exception as e:
        print(f"Erro ao determinar iterações: {e}")
        print("Iterations Concluído!")
        return numero

class Action(BaseModel):
    type: Literal["CreateFolder", "CreateFile", "ImproveFile"]
    path: str
    priority: int
    objective: str
    template: Optional[Literal["aventura", "cidade", "local", "npc", "reinado", "nenhum"]] = "nenhum"

class ActionPlan(BaseModel):
    actions: List[Action]

def taskplanner(reason: Optional[str] = "O projeto esteja concluído"):
    print("Vamos começar o Taskplanner!")
    
    # 1. Lê as permissões configuradas na aba de Opções
    config = st.carregar_configuracoes()
    allow_folder = config.get("wb_allow_create_folder", True)
    allow_file = config.get("wb_allow_create_file", True)
    allow_improve = config.get("wb_allow_improve_file", True)

    # 2. Monta dinamicamente quais ferramentas o Gemini pode usar
    ferramentas_permitidas = []
    if allow_folder:
        ferramentas_permitidas.append("CreateFolder")
    if allow_file:
        ferramentas_permitidas.append("CreateFile")
    if allow_improve:
        ferramentas_permitidas.append("ImproveFile")

    if not ferramentas_permitidas:
        print("⚠️ Todas as ferramentas do WorldBuilder estão desabilitadas nas Opções! Ação cancelada.")
        return

    texto_ferramentas = "\n".join(ferramentas_permitidas)

    # 🛡️ REGRA RESTRITIVA SE CRIAÇÃO DE PASTAS ESTIVER BLOQUEADA
    instrucao_restricao_pastas = ""
    if not allow_folder:
        instrucao_restricao_pastas = """
REGRA OBRIGATÓRIA E ABSOLUTA DE PASTAS:
- A criação de novas pastas está DESABILITADA pelo Mestre.
- Ao sugerir 'CreateFile', você DEVE OBRIGATORIAMENTE escolher apenas caminhos de PASTAS QUE JÁ EXISTEM no Índice/Estrutura.
- É PROIBIDO inventar pastas ou subpastas novas no caminho de 'CreateFile'.
"""

    if pu.is_cancelled():
        print("\n🛑 Processamento do Expander interrompido pelo usuário!")
        return
    else:
        instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o projeto e identifique quais ações são necessárias para:
{reason}

{instrucao_restricao_pastas}

REGRA IMPORTANTE SOBRE NOMES:
Antes de sugerir CreateFolder ou CreateFile, verifique cuidadosamente o Índice
e a Estrutura fornecidos. NÃO crie algo com nome igual, similar, singular/plural,
ou com pequenas variações de grafia/acentuação de algo que já existe.
Se um conceito já existe com outro nome, use ImproveFile no arquivo existente
em vez de criar um novo.

REGRA SOBRE TEMPLATES (Apenas para CreateFile):
Ao sugerir 'CreateFile', escolha obrigatoriamente um dos seguintes valores para o campo 'template':
- "aventura": para quests, missões, módulos de aventura
- "cidade": para vilas, povoados, metrópoles e assentamentos
- "local": para ruínas, dungeons, florestas, cavernas e regiões
- "npc": para personagens, vilões, aliados e figuras históricas
- "reinado": para países, reinos, impérios e ducados
- "nenhum": para conceitos genéricos, facções ou tópicos gerais (padrão)

FERRAMENTAS PERMITIDAS (Você DEVE usar APENAS estas ferramentas autorizadas):
{texto_ferramentas}

Formato obrigatório:
{{
    "actions": [
    {{
        "type": "CreateFolder",
        "path": "{pu.PASTA_PROJETO}/...",
        "priority":10,
        "objective": "motivo"
    }}
    ]
}}
Passe o path inteiro desde a pasta {pu.PASTA_PROJETO}.
Não utilize markdown.
"""

        corpo_usuario = f"""
Analise a estrutura atual do projeto no cache.
Objetivo do Mestre: {reason}

Crie o plano de ação no formato JSON estruturado com as próximas etapas prioritárias usando APENAS as ferramentas permitidas.
"""

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
            
            if not plano.actions:
                print("Nenhuma ação necessária.")
            else:
                acoes_filtradas = []
                for a in plano.actions:
                    if a.type == "CreateFolder" and not allow_folder:
                        print(f"🚫 Ação '{a.type}' bloqueada pelas Opções.")
                        continue
                    if a.type == "CreateFile" and not allow_file:
                        print(f"🚫 Ação '{a.type}' bloqueada pelas Opções.")
                        continue
                    if a.type == "ImproveFile" and not allow_improve:
                        print(f"🚫 Ação '{a.type}' bloqueada pelas Opções.")
                        continue
                    acoes_filtradas.append(a)

                actions = sorted(
                    [a.model_dump() for a in acoes_filtradas],
                    key=lambda x: x.get("priority", 0),
                    reverse=True
                )
                
                if actions:
                    enactchoices(actions)
                else:
                    print("Nenhuma ação permitida a ser executada nesta iteração.")
                if pu.is_cancelled():
                    print("\nProcessamento do Expander interrompido pelo usuário!")
                    return
        except Exception as e:
            print(f"Erro na resposta do TaskPlanner: {e}")
            
    ex.processar_arquivos()
    print("TaskPlanner Concluído!")

def enactchoices(actions):
    print("Enactchoices Iniciado!")
    for action in actions:
        if pu.is_cancelled():
            print("\nProcessamento do Expander interrompido pelo usuário!")
            return
        tipo = action["type"]
        path = action.get("path", "")
        objective = action.get("objective", "")
        template = action.get("template", "nenhum")
        
        with open(pu.log_path("changelog.jsonl"), "a", encoding="utf-8") as f:
            registro = {
                "timestamp": pu.currentdate(),
                "action": tipo,
                "path": path,
                "template": template,
                "objective": objective
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            
        if tipo == "CreateFolder":
            createfolder(action["path"], action.get("objective", ""))
        elif tipo == "CreateFile":
            createfile(action["path"], action.get("objective", ""), template)
        elif tipo == "ImproveFile":
            improvefile(action["path"], action.get("objective", ""))
    
        ex.processar_arquivos()
        print("♻️ Reconstruindo contexto do cache para refletir as novas criações...")
        cg.force_rebuild_world_context()
    
    print("Enactchoices Concluído!")

def createfolder(path, reason):
    print(f"Vamos criar uma pasta: {path}, por que {reason}")
    config = st.carregar_configuracoes()
    if not config.get("wb_allow_create_folder", True):
        print("🚫 Ação Cancelada: A criação de pastas está desabilitada nas Opções.")
        return False

    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        destino = resolver_caminho(path)

        if not destino.is_relative_to(raiz):
            print("Tentativa de criar pasta fora da pasta raiz de conhecimento.")
            return False

        parecido = pu.existe_nome_parecido(destino.name, destino.parent)
        if parecido:
            print(f"Pasta não criada: '{destino.name}' é muito parecida com a já existente '{parecido}'.")
            return False

        if destino.exists():
            print(f"Pasta já existe: {destino}")
            return False
        destino.mkdir(parents=True, exist_ok=True)
        print(f"Pasta criada: {destino}")
        return True
    except Exception as e:
        print(f"Erro ao criar pasta: {e}")
        return False

def createfile(path, reason, template="nenhum"):
    print(f"Vamos criar um arquivo: {path} (Template: {template}), motivo: {reason}")
    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        arquivo = resolver_caminho(path)

        if not arquivo.is_relative_to(raiz):
            print("Tentativa de criar arquivo fora da pasta raiz de conhecimento.")
            return False

        arquivo = arquivo.with_suffix(".md")

        # 🛡️ TRAVA MECÂNICA DE SEGURANÇA (VERIFICA A PASTA PAI)
        config = st.carregar_configuracoes()
        allow_folder = config.get("wb_allow_create_folder", True)

        if not arquivo.parent.exists():
            if not allow_folder:
                print(f"🚫 Arquivo '{arquivo.name}' CANCELADO: A pasta '{arquivo.parent.name}' NÃO EXISTE e a criação de novas pastas está DESABILITADA nas Opções.")
                return False
            else:
                arquivo.parent.mkdir(parents=True, exist_ok=True)

        # --- CHECAGEM DE NOME PARECIDO ---
        parecido = pu.existe_nome_parecido(arquivo.name, arquivo.parent)
        if parecido:
            print(f"⚠️ Arquivo não criado: '{arquivo.name}' é muito parecido com o já existente '{parecido}'.")
            return False

        if arquivo.exists():
            print(f"⚠️ Arquivo já existe: {arquivo}")
            return False

        titulo = re.sub(r"_v\d+$", "", arquivo.stem)
        conteudo_template = obter_conteudo_template(template)

        conteudo = f"""# {titulo}
> Este arquivo foi criado automaticamente pelo WorldBuilder.
----
status: rascunho
----
<-- TO DO: {reason}
{conteudo_template}
"""
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"✅ Arquivo criado com sucesso: {arquivo}")
        improvefile(path, reason)
        return True
    except Exception as e:
        print(f"❌ Erro ao criar arquivo {path}: {e}")
        return False

def improvefile(path, reason="Melhorar o arquivo!"):
    print(f"Vamos melhorar o arquivo: {path}\nMotivo: {reason}")
    arquivo = resolver_caminho(path)

    if not arquivo.exists():
        print(f"Arquivo não encontrado, ação ignorada: {arquivo}")
        return False

    if not arquivo.is_file():
        print(f"O caminho informado não é um arquivo, ação ignorada: {arquivo}")
        return False

    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            arquivoatual = f.read()
    except Exception as e:
        print(f"Erro ao ler o arquivo {arquivo.name}: {e}")
        return False

    instrucoes_globais = f"""
Você é um Mestre de Mesa (DM) de D&D experiente.
Seu objetivo é melhorar o arquivo:
{arquivo.name}
Seguindo a motivação:
{reason}
Não contradiga informações existentes.
Mantenha consistência com o restante do mundo.
"""
    prompt_conteudo = f"""
OBJETIVO:
{reason}
O PROJETO COMPLETO está no cache para ser analisado!

CONTEÚDO ORIGINAL:
{arquivoatual}

Retorne apenas o conteúdo final do arquivo.
"""

    try:
        texto_expandido = au.ask_ai(
            contents=prompt_conteudo,
            system_instruction=instrucoes_globais,
            temperature=0.4
        )
        texto_limpo = ex.remover_markdown_fences(texto_expandido)
        novo_arquivo_path = ex.obter_proximo_nome_versao(arquivo)

        with open(novo_arquivo_path, "w", encoding="utf-8") as f:
            f.write(texto_limpo)
        ex.arquivar_versao_antiga(arquivo)
        print(f"Nova versão criada!! {novo_arquivo_path.name}")
        return True
    except Exception as e:
        print(f"Erro ao processar {arquivo.name}: {e}")
        return False