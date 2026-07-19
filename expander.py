import os, re, time
from pathlib import Path
from google import genai  # Utilizando o SDK moderno
from ai_utils import ask_gemini
PASTA_PHAETON = os.path.join(os.getcwd(), "Phaeton")
ARQUIVO_REGRAS = "vision.md"

TAG_ALVO = [
    "<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo",
    "<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do",
    "<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", 
    "<-- To-do", "<-- Todo:"
]
IGNORELIST = ["Templates", "status: rascunho"]

def obter_arquivos_relacionados(titulo):
    relacionados = []
    titulo = re.sub(r'_v\d+$', '', titulo.lower())
    for arquivo in Path(PASTA_PHAETON).rglob("*.md"):
        if any(part in IGNORELIST for part in arquivo.parts):
            continue
        with open(arquivo, encoding="utf-8") as f:
            conteudo = f.read()

        if (
            arquivo.stem.lower() == titulo
            or any(tag in conteudo for tag in TAG_ALVO)
            or any(ignore in conteudo for ignore in IGNORELIST)
        ):
            print(f"Arquivo relacionado ignorado por conter tag ou rascunho: {arquivo}")
            continue
        score = conteudo.lower().count(titulo)
        if score > 0:
            relacionados.append((arquivo.name, conteudo, score))

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

def nome_base(path):
    return re.sub(r'_v\d+$', '', path.stem.lower())

def remover_markdown_fences(texto: str) -> str:
    """
    Remove marcações de bloco de código (```markdown ... ```) 
    que o Gemini costuma adicionar nas pontas da resposta.
    """
    linhas = texto.strip().splitlines()
    if not linhas:
        return texto

    # Se a primeira linha começar com as crases, nós a removemos
    if linhas[0].strip().startswith("```"):
        linhas.pop(0)
        
    # Se a última linha terminar com as crases, nós a removemos
    if linhas and linhas[-1].strip().startswith("```"):
        linhas.pop()
        
    return "\n".join(linhas).strip()

# Certifique-se de que a função ask_gemini desenvolvida anteriormente está importada ou declarada no escopo deste arquivo.

def processar_arquivos():
    # As diretrizes estáticas do cenário funcionam melhor fixadas no System Instruction
    instrucoes_globais = """
    Você é um Mestre de Mesa (DM) de D&D experiente e escritor de fantasia sombria (Dark Fantasy).
    Seu objetivo é preencher lacunas de desenvolvimento do cenário de Phaeton.
    
    # O tema central do cenário e das aventuras em Phaeton
    - Caos x Ordem.
    - É melhor viver em um mundo de ordem perfeita, mas sem liberdade e sem consequências ou em um mundo de caos imperfeito, com sofrimento, mas repleto de oportunidades?
    - É possível eliminar o caos de um ambiente caótico e ordenar, das pessoas até a natureza?

    # Verdades Fundamentais de Phaeton
    - A magia simples e fraca é comum, grandes poderes mágicos são raros.
    - Os deuses são reais.
    - O mundo já viveu uma era de glória perdida.
    - Existem segredos ancestrais que jamais deveriam ser descobertos.
    - O heroísmo existe, mas raramente vence sem sacrifícios.
    - Monstros gigantes, titãs e seres lendários rondam pelo mundo, em sua superfície, nos céus, no subsolo e pelos oceanos

    # Estilo Narrativo de Phaeton
    - Phaeton é um cenário de Dark Fantasy épico.
    - A sensação predominante deve ser de grandiosidade e mistério.
    - Ruínas antigas são mais impressionantes que construções modernas.
    - Quase toda cidade, castelo e forte estão construídos acima de uma civilização antiga que foi extinta e esquecida.
    - A magia é majestosa, mas perigosa.
    - Heróis podem mudar o destino do mundo, mas quase sempre pagam um preço por isso.

    # O que evitar
    - Não criar humor moderno.
    - Não usar nomes excessivamente caricatos.
    - Não criar sociedades completamente boas.
    - Não criar sociedades completamente malignas.
    - Evitar conflitos simplistas.

    # O que criar quando necessário
    - Foque em nomes criativos e relacionados ao assunto.
    - Dê descrições à lugares seguindo o estilo e verdades de Phaeton.
    - Invente cenários, lugares e pessoas onde necessário.
    - Não altere informações já existentes e faça uso delas ao criar coisas novas.

    ## O que realmente importa para esse cenário
    ### O conflito central do mundo
    - A expansão do Império Draco-Divino Branoth;
    - A influência dos Antigos e de Mythos na mente dos mortais;
    - A eterna disputa territorial entre Dragões, Reinados e Impérios;

    ### Facções com objetivos legítimos
    - Não existe o bem e o mal;
    - Todos possuem seus objetivos por motivo real e em prol de seus próprios pontos de vista, corretos;
    - Toda escolha nesse cenário, irá fazer os aventureiros ganharem algo e perder algo;

    ### Perguntas sem resposta
    - Problemas são criados que não existe resposta pronta para uma solução;
    - Mistérios e situações causadas por forças não explicadas nem apresentadas, até que alguém resolva investigar a fundo;

    ### Consequências em escala
    - Situações e problemas devem representar situações amplas que afetam uma grande área ou uma grande população;
    - Decisões dos aventureiros irão causar grandes mudanças e efeitos;
    """

    caminho_phaeton = Path(PASTA_PHAETON)
    print(f"🔍 Analisando arquivos em: {caminho_phaeton.resolve()}")
    
    for arquivo in caminho_phaeton.rglob("*.md"):
        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
            conteudo = "".join(linhas)
            titulo = Path(arquivo).stem
            titulo = re.sub(r'_v\d+$', '', titulo.lower())

        tag_encontrada = next((tag for tag in TAG_ALVO if tag in conteudo), None)
        
        if tag_encontrada:
            print(f"\n📄 Tag encontrada no arquivo: {arquivo.name}")
            info_locais = ""
            for arquivo_local in arquivo.parent.glob("*.md"):
                if nome_base(arquivo_local) != nome_base(arquivo):
                    with open(arquivo_local, "r", encoding="utf-8") as f:
                        conteudo_local = f.read()
                        if (
                            any(tag in conteudo_local for tag in TAG_ALVO)
                            or "status: rascunho" in conteudo_local.lower()
                            ):
                            print(f"Arquivo relacionado ignorado por conter tag ou rascunho: {arquivo_local}")
                            continue
                        else:
                            with open(arquivo_local, "r", encoding="utf-8") as f:
                                print(f" -> Adicionar ao contexto local: {arquivo_local.name}")
                                info_locais += f.read() + "\n\n"
            
            info_importante = obter_arquivos_relacionados(titulo)
            
            # Contexto de dados específicos do arquivo a ser modificado
            prompt_conteudo = f"""
Por favor, analise as informações abaixo para preencher as lacunas marcadas no arquivo de destino.

INFORMAÇÕES LOCAIS DO AMBIENTE (Arquivos da mesma pasta para consistência):
{info_locais}

INFORMAÇÕES IMPORTANTES RELACIONADAS:
{info_importante}

CONTEÚDO ORIGINAL DO ARQUIVO ATUAL ({arquivo.name}):
{conteudo}

TAREFA:
No conteúdo do arquivo atual, identifique a linha que começa com a variação de To-Do '{tag_encontrada}'.
Substitua essa linha pelo conteúdo expandido de forma criativa, mantendo total coesão com a história local e as diretrizes de Phaeton.

REGRAS DE RETORNO:
1. Retorne o texto completo do arquivo original, incluindo a modificação feita.
2. Preserve rigorosamente a formatação Markdown existente.
3. Não acrescente prefácios, comentários explicativos ou notas sobre o que você modificou. Retorne apenas o conteúdo final do arquivo editado.
"""

            try:
                # Opcional: Registrar o prompt gerado para fins de depuração
                with open("Prompts.txt", 'w', encoding='utf-8') as f:
                    f.write(f"Alterando Arquivo: {arquivo.name}\n")
                    f.write(prompt_conteudo + '\n')
                    
                # Substituição da chamada nativa pela função estruturada ask_gemini
                # Graças ao ask_gemini, a verificação de fallbacks de modelos e limites de taxa é herdada automaticamente.
                texto_expandido = ask_gemini(
                    contents=prompt_conteudo,
                    system_instruction=instrucoes_globais,
                    temperature=0.7 # Temperatura criativa e coerente
                )
                
                if texto_expandido:
                    texto_limpo = remover_markdown_fences(texto_expandido)
                    novo_arquivo_path = obter_proximo_nome_versao(arquivo)
                    
                    with open(novo_arquivo_path, 'w', encoding='utf-8') as f:
                        f.write(texto_expandido)
                    
                    print(f"✅ Nova versão gerada com sucesso: {novo_arquivo_path.name}")
                else:
                    print(f"⚠️ O retorno do modelo para {arquivo.name} foi vazio.")
                
                time.sleep(10)  # Pausa de segurança entre chamadas
                
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo.name}: {e}")
                time.sleep(10)

if __name__ == "__main__":
    processar_arquivos()
    print("\n✅ Processamento concluído!")