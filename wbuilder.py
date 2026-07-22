import os, json, re, time
import project_utils as pu
import expander as ex
from typing import Optional
from pathlib import Path
from ai_utils import ask_gemini
from pydantic import BaseModel
from typing import Literal, List

CONTEUDO = pu.carregar_projeto()
DIRETORIOS = pu.carregar_estrutura_projeto()
INDICE = pu.gerar_indice()
print("Iniciando World Builder! Boa Sorte!")

def resolver_caminho(path_str):
    """
    Normaliza um caminho sugerido pela IA para garantir que ele sempre
    seja interpretado como relativo à pasta raiz do projeto (CAMINHO_PROJETO),
    não relativo à pasta onde o Python está rodando (cwd).

    A IA às vezes manda o caminho:
    - sem o nome da pasta do projeto na frente: "4.Regions/Colwin/arquivo.md"
    Esta função trata os dois casos da mesma forma, sempre resultando
    no caminho real correto dentro de CAMINHO_PROJETO.
    """
    caminho = Path(path_str)
    raiz = Path(pu.CAMINHO_PROJETO).resolve()

    # Se por algum motivo vier um caminho absoluto, apenas resolvemos ele
    # (a checagem de segurança "is_relative_to" feita depois, em quem chamar
    # esta função, ainda vai barrar se ele cair fora da raiz).
    if caminho.is_absolute():
        return caminho.resolve()

    partes = caminho.parts

    if partes and partes[0] == pu.PASTA_PROJETO:
        caminho = Path(*partes[1:]) if len(partes) > 1 else Path("")

    return (raiz / caminho).resolve()

def iterationschoice(reason: Optional[str] = "O projeto esteja concluído"):
    print("Iterations Iniciado!")
    CONTEUDO = pu.carregar_projeto()
    DIRETORIOS = pu.carregar_estrutura_projeto()
    INDICE = pu.gerar_indice()
    numero=1
    instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o estado atual do projeto e estime quantas iterações de expansão são necessárias para que: 
{reason}.
Responda apenas um número inteiro entre 1 e 10.
"""
    corpo_usuario = f"""
Projeto:
{DIRETORIOS}\n
{INDICE}\n
{CONTEUDO}\n

Critérios:
- Regiões
- Cidades
- Facções
- NPCs
- História
- Potencial para aventuras
Quantas iterações ainda são necessárias?
"""
    try:

        resposta = ask_gemini(
            contents=corpo_usuario,
            system_instruction=instrucao_sistema,
            temperature=0.35
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
class ActionPlan(BaseModel):
    actions: List[Action]

def taskplanner(maxiterations: int = 1, reason: Optional[str] = "O projeto esteja concluído"):
    print(f"O iterationschoice retornou que vamos precisar de {maxiterations} iterações! Vamos começar o Taskplanner!")
    CONTEUDO = pu.carregar_projeto()
    DIRETORIOS = pu.carregar_estrutura_projeto()
    INDICE = pu.gerar_indice()
    while maxiterations>0:
        instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o projeto e identifique quais ações são necessárias para:
{reason}

REGRA IMPORTANTE SOBRE NOMES:
Antes de sugerir CreateFolder ou CreateFile, verifique cuidadosamente o Índice
e a Estrutura fornecidos. NÃO crie algo com nome igual, similar, singular/plural,
ou com pequenas variações de grafia/acentuação de algo que já existe
(ex: "Segredos" e "Segredo" são a MESMA coisa, "Ruína" e "Ruinas" são a MESMA coisa).
Se um conceito já existe com outro nome, use ImproveFile no arquivo existente
em vez de criar um novo.

Você possui apenas três ferramentas:

CreateFolder
CreateFile
ImproveFile

Formato obrigatório:
{{
    "actions": [
    {{
        "type": "CreateFolder",
        "path": "{pu.PASTA_PROJETO}/...",
        "priority":7,
        "objective": "motivo"
    }},
    {{
        "type": "CreateFile",
        "path": "{pu.PASTA_PROJETO}/.../arquivo.md",
        "priority":8,        
        "objective": "O que deve ter no arquivo"
    }},
    {{
        "type": "ImproveFile",
        "path": "{pu.PASTA_PROJETO}/.../arquivo.md",
        "priority":10,        
        "objective": "O que deve ter no arquivo"
    }}
    ]
}}
Passe o path inteiro desde a pasta {pu.PASTA_PROJETO}.
Não utilize markdown.
"""

        corpo_usuario = f"""
Estrutura:
{DIRETORIOS}

Índice:
{INDICE}

Projeto:
{CONTEUDO}

Critérios:
- Quantidade de regiões documentadas.
- Quantidade de cidades documentadas.
- Possibilidade de conduzir aventuras sem gerar novas informações.

Liste no máximo 15 ações prioritárias.
"""

        try:    
            resposta = ask_gemini(
            contents=corpo_usuario,
            system_instruction=instrucao_sistema,
            temperature=0.4,
            response_schema=ActionPlan
            )
            plano = ActionPlan.model_validate_json(resposta)

            if not plano.actions:
                print("Nenhuma ação necessária.")
                break

            # model_dump() converte os objetos Pydantic de volta para dicts,
            # já que enactchoices() e o resto do código trabalham com dicts/JSON puro.
            actions = sorted(
                [a.model_dump() for a in plano.actions],
                key=lambda x: x.get("priority", 0),
                reverse=True
            )
            enactchoices(actions)
            print("1 iteração concluída!")
            maxiterations -= 1
        except Exception as e:
            print(f"Erro na resposta do TaskPlanner: {e}")
            print("1 iteração concluída!")
            maxiterations -= 1
    ex.processar_arquivos()
    print("TaskPlanner Concluído!")

def enactchoices(actions):
    print("Enactchoices Iniciado!")
    for action in actions:
        tipo = action["type"]
        path = action.get("path", "")
        objective = action.get("objective", "")
        with open("changelog.jsonl","a",encoding="utf-8") as f:
            registro = {
                "timestamp": pu.currentdate(),
                "action": tipo,
                "path": path,
                "objective": objective
            }
            f.write(
                json.dumps(
                    registro,
                    ensure_ascii=False
                )
                + "\n"
            )
        if tipo == "CreateFolder":
            createfolder(action["path"], action.get("objective", ""))
        elif tipo == "CreateFile":
            createfile(action["path"], action.get("objective", ""))
        elif tipo == "ImproveFile":
            improvefile(action["path"], action.get("objective", ""))
    print("Enactchoices Concluído!")


def createfolder(path, reason):
    print(f"Vamos criar uma pasta: {path}, por que {reason}")
    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        destino = resolver_caminho(path)

        if not destino.is_relative_to(raiz):
            print("❌ Tentativa de criar pasta fora da pasta raiz de conhecimento.")
            return False

        # --- CHECAGEM DE NOME PARECIDO ---
        # Evita criar "Segredos" quando já existe "Segredo" na mesma pasta pai.
        parecido = pu.existe_nome_parecido(destino.name, destino.parent)
        if parecido:
            print(f"⚠️ Pasta não criada: '{destino.name}' é muito parecida com a já existente '{parecido}'.")
            return False

        if destino.exists():
            print(f"⚠️ Pasta já existe: {destino}")
            return False
        destino.mkdir(parents=True, exist_ok=True)
        print(f"✅ Pasta criada: {destino}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar pasta: {e}")
        return False

def createfile(path, reason):
    print(f"Vamos criar um arquivo: {path}, por que {reason}")
    try:
        raiz = Path(pu.CAMINHO_PROJETO).resolve()
        arquivo = resolver_caminho(path)

        if not arquivo.is_relative_to(raiz):
            print("❌ Tentativa de criar arquivo fora da pasta raiz de conhecimento.")
            return False

        arquivo = arquivo.with_suffix(".md")

        # --- CHECAGEM DE NOME PARECIDO ---
        parecido = pu.existe_nome_parecido(arquivo.name, arquivo.parent)
        if parecido:
            print(f"⚠️ Arquivo não criado: '{arquivo.name}' é muito parecido com o já existente '{parecido}'.")
            return False

        if arquivo.exists():
            print(f"⚠️ Arquivo já existe: {arquivo}")
            return False

        arquivo.parent.mkdir(parents=True, exist_ok=True)
        titulo = re.sub(r"_v\d+$", "", arquivo.stem)

        conteudo = f"""# {titulo}
> Este arquivo foi criado automaticamente pelo WorldBuilder.
----
status: rascunho
----
<-- TO DO: {reason}
"""
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"✅ Arquivo criado com sucesso: {arquivo}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar arquivo {path}: {e}")
        return False

def improvefile(path, reason):
    print(f"Vamos melhorar o arquivo: {path}")
    print(f"Motivo: {reason}")
    arquivo = resolver_caminho(path)   # <-- normaliza o caminho recebido

    if not arquivo.exists():
        print(f"❌ Arquivo não encontrado, ação ignorada: {arquivo}")
        return False

    if not arquivo.is_file():
        print(f"❌ O caminho informado não é um arquivo, ação ignorada: {arquivo}")
        return False

    CONTEUDO = pu.carregar_projeto()

    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            arquivoatual = f.read()
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo {arquivo.name}: {e}")
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
PROJETO COMPLETO:
{CONTEUDO}
Estrutura:
{DIRETORIOS}
Índice:
{INDICE}
CONTEÚDO ORIGINAL:
{arquivoatual}

Retorne apenas o conteúdo final do arquivo.
"""

    try:
        texto_expandido = ask_gemini(
            contents=prompt_conteudo,
            system_instruction=instrucoes_globais,
            temperature=0.4
        )
        texto_limpo = ex.remover_markdown_fences(texto_expandido)
        novo_arquivo_path = ex.obter_proximo_nome_versao(arquivo)

        with open(novo_arquivo_path, "w", encoding="utf-8") as f:
            f.write(texto_limpo)

        print(f"✅ Nova versão criada: {novo_arquivo_path.name}")
        return True
    except Exception as e:
        print(f"❌ Erro ao processar {arquivo.name}: {e}")
        return False
        