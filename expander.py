import os
import re
from pathlib import Path
import time
from google import genai  # Utilizando o SDK moderno
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")  
PASTA_PHAETON = os.path.join(os.getcwd(), "Phaeton")
ARQUIVO_REGRAS = "vision.md"
MODELO_IA = 'gemini-2.5-flash'

# Lista de variações para busca rápida
TAG_ALVO = [
    "<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo",
    "<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do",
    "<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", 
    "<-- To-do", "<-- Todo:"
]

# Inicializa o cliente oficial do SDK moderno
client = genai.Client(api_key=API_KEY)

def obter_arquivos_relacionados(titulo, arquivo_base):
    relacionados = []
    titulo = titulo.lower()
    arquivo_base_name = arquivo_base.name

    for arquivo in Path(PASTA_PHAETON).rglob("*.md"):
        with open(arquivo, encoding="utf-8") as f:
            conteudo = f.read()

        # Ignora o próprio arquivo e arquivos que ainda possuem pendências de TODO
        if (
            arquivo.name == arquivo_base_name
            or any(tag in conteudo for tag in TAG_ALVO)
        ):
            continue

        score = conteudo.lower().count(titulo)

        if score > 0:
            relacionados.append((arquivo.name, conteudo, score))

    # Correção: Ordenar pelo score (índice 2)
    relacionados.sort(
        key=lambda x: x[2],
        reverse=True
    )
    
    # Limita aos 10 mais relevantes
    relacionados = relacionados[:10]
    
    print("\n==== Arquivos relacionados encontrados:====")
    for name, _, score in relacionados:
        print(f"{name}: {score} ocorrências")
    
    # Correção: Ajustado o separador de join para quebras de linha limpas
    return "\n\n".join(
        conteudo for _, conteudo, _ in relacionados
    )

def obter_instrucoes():
    try:
        with open(ARQUIVO_REGRAS, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Erro: O arquivo de regras {ARQUIVO_REGRAS} não foi encontrado.")
        return ""

def obter_proximo_nome_versao(caminho_original):
    diretorio = caminho_original.parent
    nome_base = re.sub(r'_v\d+$', '', caminho_original.stem)
    extensao = caminho_original.suffix
    versao = 1
    while True:
        novo_nome = f"{nome_base}_v{versao}{extensao}"
        novo_caminho = diretorio / novo_nome
        if not novo_caminho.exists():
            return novo_caminho
        versao += 1

def processar_arquivos():
    instrucoes_globais = obter_instrucoes()
    if not instrucoes_globais:
        return

    caminho_phaeton = Path(PASTA_PHAETON)
    print(f"🔍 Analisando arquivos em: {caminho_phaeton.resolve()}")
    
    for arquivo in caminho_phaeton.rglob("*.md"):
        # Evita reprocessar arquivos que já são versões antigas (ex: _v1.md, _v2.md)
        if re.search(r'_v\d+$', arquivo.stem):
            continue

        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
            conteudo = "".join(linhas)
            titulo = linhas[0].lstrip("# ").strip() if linhas else ""

        # Verifica se o arquivo atual possui alguma das tags de To Do
        tag_encontrada = next((tag for tag in TAG_ALVO if tag in conteudo), None)
        
        if tag_encontrada:
            print(f"\n📄 Tag encontrada no arquivo: {arquivo.name}")
            
            # Busca arquivos no mesmo diretório
            info_locais = ""
            for arquivo_local in arquivo.parent.glob("*.md"):
                if arquivo_local != arquivo and not re.search(r'_v\d+$', arquivo_local.stem):
                    with open(arquivo_local, "r", encoding="utf-8") as f:
                        # Correção: printando o nome do arquivo local correto
                        print(f" -> Lendo contexto local de: {arquivo_local.name}")
                        info_locais += f.read() + "\n\n"
            
            info_importante = obter_arquivos_relacionados(titulo, arquivo)
            
            # Criamos uma instrução clara para que a IA busque a tag específica presente no arquivo
            prompt = f"""
            INSTRUÇÕES DE MUNDO (Siga estritamente):
            {instrucoes_globais}

            INFORMAÇÕES LOCAIS (Siga estritamente):
            {info_locais}

            INFORMAÇÕES IMPORTANTES DE OUTROS ARQUIVOS:
            {info_importante}

            CONTEXTO DO ARQUIVO ATUAL ({arquivo.name}):
            {conteudo}

            TAREFA:
            No arquivo atual, identifique a linha que começa com uma variação de To-Do (como '{tag_encontrada}') e substitua essa tag/instrução pelo conteúdo criativo expandido, baseando-se estritamente nas instruções fornecidas.
            Retorne o texto completo do arquivo original, mantendo a formatação e as partes intocadas, alterando apenas a seção indicada pela tag.
            """

            try:
                # Salva o prompt enviado para debug
                with open("Prompts.txt", 'w', encoding='utf-8') as f:
                    f.write(f"Alterando Arquivo: {arquivo.name}\n")
                    f.write(prompt + '\n')
                    
                # Geração de conteúdo utilizando o novo cliente
                response = client.models.generate_content(
                    model=MODELO_IA,
                    contents=prompt
                )
                
                texto_expandido = response.text
                novo_arquivo_path = obter_proximo_nome_versao(arquivo)
                
                with open(novo_arquivo_path, 'w', encoding='utf-8') as f:
                    f.write(texto_expandido)
                
                print(f"✅ Nova versão gerada com sucesso: {novo_arquivo_path.name}")
                time.sleep(10)  # Pausa reduzida para 10 segundos para evitar limites sem demorar tanto
                
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo.name}: {e}")
                time.sleep(10)

if __name__ == "__main__":
    processar_arquivos()
    print("\n✅ Processamento concluído!")