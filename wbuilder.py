import os, json, re, time
import project_utils as pu
import expander as ex
from typing import Optional
from pathlib import Path
from ai_utils import ask_gemini



CONTEUDO = pu.carregar_phaeton()
DIRETORIOS = pu.carregar_estrutura_phaeton()
INDICE = pu.gerar_indice()
print("Iniciando World Builder! Boa Sorte!")


def iterationschoice(reason: Optional[str] = "O projeto esteja concluído"):
    CONTEUDO = pu.carregar_phaeton()
    DIRETORIOS = pu.carregar_estrutura_phaeton()
    INDICE = pu.gerar_indice()
    instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o estado atual do projeto e estime quantas iterações de expansão são necessárias para que: 
{reason}.
Responda apenas um número inteiro entre 1 e 10.
"""

    corpo_usuario = f"""
Projeto:
{CONTEUDO}

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

        numero = re.search(r"\d+", str(resposta))
        numero = max(1, min(10, int(numero.group())))

        if numero:
            print(f"Gemini analisou e decidiu que precisa de: {numero} etapas para melhorar o projeto")
            taskplanner(numero, reason)
            return 1

    except Exception as e:
        print(f"Erro ao determinar iterações: {e}")
        return 1

def taskplanner(maxiterations: int = 1, reason: Optional[str] = "O projeto esteja concluído"):
    print(f"O iterationschoice retornou que vamos precisar de {maxiterations} iterações! Vamos começar o Taskplanner!")
    CONTEUDO = pu.carregar_phaeton()
    DIRETORIOS = pu.carregar_estrutura_phaeton()
    INDICE = pu.gerar_indice()
    while maxiterations>0:
        instrucao_sistema = f"""
Você é um especialista em worldbuilding para RPG.
Analise o projeto e identifique quais ações são necessárias para:
{reason}
Você possui apenas três ferramentas:

CreateFolder
CreateFile
ImproveFile

Retorne EXCLUSIVAMENTE um JSON válido.
Formato obrigatório:
{{
    "actions": [
    {{
        "type": "CreateFolder",
        "path": "Phaeton/...",
        "priority":7,
        "objective": "motivo"
    }},
    {{
        "type": "CreateFile",
        "path": "Phaeton/.../arquivo.md",
        "priority":8,        
        "objective": "O que deve ter no arquivo"
    }},
    {{
        "type": "ImproveFile",
        "path": "Phaeton/.../arquivo.md",
        "priority":10,        
        "objective": "O que deve ter no arquivo"
    }}
    ]
}}

Não escreva explicações.
Não utilize markdown.
Não utilize ```json.
Retorne apenas o JSON.
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
Retorne apenas JSON.
"""

        try:    
            resposta = ask_gemini(
            contents=corpo_usuario,
            system_instruction=instrucao_sistema,
            temperature=0.4
            )
            resposta = resposta.strip()
            inicio = resposta.find("{")
            fim = resposta.rfind("}")
            if inicio == -1 or fim == -1:
                raise ValueError("Resposta não contém JSON.")
            resposta = resposta[inicio:fim+1]
            dados = json.loads(resposta)
            actions = dados.get("actions", [])
            if not actions:
                print("Nenhuma ação necessária.")
                break
            actions = sorted(
                actions,
                key=lambda x: x.get("priority", 0),
                reverse=True
            )
            enactchoices(actions)
            maxiterations -= 1
        except Exception as e:
            print(f"Erro na resposta do TaskPlanner: {e}")
            maxiterations -= 1
            
    ex.processar_arquivos()

def enactchoices(actions):
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

def createfolder(path, reason):
    print(f"Vamos criar uma pasta: {path}, por que {reason}")
    try:
        pasta = Path(path)
        raiz = Path(os.getenv("PASTA_PROJETO", "Phaeton")).resolve()
        destino = pasta.resolve()
        if not str(destino).is_relative_to(raiz):
            print("❌ Tentativa de criar pasta fora da pasta raiz de conhecimento.")
            return False
        if destino.exists():
            print(
                f"⚠️ Pasta já existe: "
                f"{destino}"
            )
            return False
        destino.mkdir(
            parents=True,
            exist_ok=True
        )
        print(
            f"✅ Pasta criada: "
            f"{destino}"
        )
        return True
    except Exception as e:
        print(
            f"❌ Erro ao criar pasta: "
            f"{e}"
        )
        return False

def createfile(path, reason):
    print(f"Vamos criar um arquivo: {path}, por que {reason}")
    try:
        arquivo = Path(path)
        # Força extensão .md
        arquivo = arquivo.with_suffix(".md")
        # Verifica se já existe
        if arquivo.exists():
            print(
                f"⚠️ Arquivo já existe: "
                f"{arquivo}"
            )
            return False
        # Garante que a pasta existe
        arquivo.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        titulo = re.sub(r"_v\d+$","",arquivo.stem)

        conteudo = f"""# {titulo}
> Este arquivo foi criado automaticamente pelo WorldBuilder.
----
status: rascunho
----
<-- TO DO: {reason}
"""
        with open(
            arquivo,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(conteudo)
        print(
            f"✅ Arquivo criado com sucesso: "
            f"{arquivo}"
        )
        return True
    except Exception as e:
        print(
            f"❌ Erro ao criar arquivo "
            f"{path}: {e}"
        )
        return False

def improvefile(path, reason):
    print(f"Vamos melhorar o arquivo: {path}")
    print(f"Motivo: {reason}")
    arquivo = Path(path)
    CONTEUDO = pu.carregar_phaeton()
    with open(arquivo, "r", encoding="utf-8") as f:
        arquivoatual = f.read()

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

        texto_limpo = ex.remover_markdown_fences(
            texto_expandido
        )

        novo_arquivo_path = ex.obter_proximo_nome_versao(
            arquivo
        )

        with open(
            novo_arquivo_path,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(texto_limpo)

        print(
            f"✅ Nova versão criada: "
            f"{novo_arquivo_path.name}"
        )
        
    except Exception as e:
        print(
            f"❌ Erro ao processar "
            f"{arquivo.name}: {e}"
        )
        