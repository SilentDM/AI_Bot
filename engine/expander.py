import os, re, shutil
from pathlib import Path
import core.ai_utils as au
import engine.project_utils as pu

def arquivar_versao_antiga(caminho_original):
    """
    Move a versão antiga/original de um arquivo para a pasta logs/history/,
    preservando a estrutura de subpastas.
    """
    try:
        caminho_original = Path(caminho_original)
        if not caminho_original.exists():
            return

        # Pasta de histórico dentro dos logs do projeto
        pasta_historico = pu.PASTA_LOGS / "history"

        # Mantém a mesma estrutura de subpastas do projeto dentro de logs/history
        try:
            relativo = caminho_original.relative_to(pu.CAMINHO_PROJETO)
            destino_dir = pasta_historico / relativo.parent
        except ValueError:
            destino_dir = pasta_historico

        destino_dir.mkdir(parents=True, exist_ok=True)
        destino_arquivo = destino_dir / caminho_original.name

        # Mover o arquivo original para o histórico
        shutil.move(str(caminho_original), str(destino_arquivo))
        print(f"Versão antiga arquivada em: {destino_arquivo}")
    except Exception as e:
        print(f"Erro ao arquivar versão antiga ({caminho_original.name}): {e}")

def obter_arquivos_relacionados(titulo):
    relacionados = []
    titulo = re.sub(r'_v\d+$', '', titulo.lower())
    titulo = re.sub(r'_',' ', titulo)
    for arquivo in Path(pu.PASTA_PROJETO).rglob("*.md"):
        if any(part in pu.IGNORELIST for part in arquivo.parts):
            continue
        with open(arquivo, encoding="utf-8") as f:
            conteudo = f.read()
        if (
            arquivo.stem.lower() == titulo
            or any(tag in conteudo for tag in pu.TAG_ALVO)
            or any(ignore in conteudo for ignore in pu.IGNORELIST)
        ):
            continue
        score = conteudo.lower().count(titulo)
        if score > 0:
            relacionados.append((arquivo.name, conteudo, score))

    relacionados.sort(
        key=lambda x: x[2],
        reverse=True
    )
    
    relacionados = relacionados[:10]
    if relacionados:
        print("\n==== Arquivos relacionados encontrados:====")
        for name, _, score in relacionados:
            print(f"{name}: {score} ocorrências")
    
    return "\n\n".join(
        conteudo for _, conteudo, _ in relacionados
    )

def obter_proximo_nome_versao(caminho_original):
    diretorio = caminho_original.parent
    nome_base = re.sub(r'_v\d+$','',caminho_original.stem)
    extensao = caminho_original.suffix
    maior_versao = 0
    for arquivo in diretorio.glob(f"{nome_base}_v*{extensao}"):
        match = re.search(r'_v(\d+)$',arquivo.stem)
        if match:
            maior_versao = max(maior_versao,int(match.group(1)))
    nova_versao = maior_versao + 1
    return (diretorio /f"{nome_base}_v{nova_versao:02d}{extensao}")
    
def carregar_diretrizes_estilo():
    """Carrega e unifica as diretrizes de estilo contidas na pasta designada."""
    pasta_estilo = pu.CAMINHO_ESTILO
    conteudo_estilo = []
    if pasta_estilo.exists() and pasta_estilo.is_dir():
        for arquivo in sorted(pasta_estilo.glob("*.md")):
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    conteudo_estilo.append(f"\n# DIRETRIZ ({arquivo.name}):\n{f.read()}")
            except Exception as e:
                print(f"Erro ao carregar diretriz {arquivo.name}: {e}")
    return "".join(conteudo_estilo)

def nome_base(path):
    return re.sub(r'_v\d+$', '', path.stem.lower())

def remover_markdown_fences(texto: str) -> str:
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

def processar_arquivo_unico(path):
    estilo_contexto = carregar_diretrizes_estilo()
    instrucoes_globais = f"""
    Você é um Mestre de Mesa (DM) de D&D experiente e escritor de fantasia sombria (Dark Fantasy).
    Seu objetivo é preencher lacunas de desenvolvimento do cenário de {pu.PASTA_PROJETO}.
    # Diretrizes e Regras Adicionais do Projeto:
    {estilo_contexto}
    """
    arquivo=Path(path)
    with open(arquivo, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
        conteudo = "".join(linhas)
        titulo = arquivo.stem
        titulo = re.sub(r'_v\d+$', '', titulo.lower())
    tag_encontrada = next((tag for tag in pu.TAG_ALVO if tag in conteudo), None)
    if tag_encontrada:
        print(f"\n=====\nTag encontrada no arquivo:\n{arquivo.name}\n=====")
        tagx=1
        info_locais = ""
        for arquivo_local in arquivo.parent.glob("*.md"):
            if nome_base(arquivo_local) != nome_base(arquivo):
                with open(arquivo_local, "r", encoding="utf-8") as f:
                    conteudo_local = f.read()
                    if (
                        any(tag in conteudo_local for tag in pu.TAG_ALVO)
                        or "status: rascunho" in conteudo_local.lower()
                        ):
                        continue
                    else:
                        with open(arquivo_local, "r", encoding="utf-8") as f:
                            info_locais += f.read() + "\n\n"
        info_importante = obter_arquivos_relacionados(titulo)
        prompt_conteudo = f"""
Por favor, analise as informações completas armazenadas no cache e as informações locais e importantes abaixo para preencher as lacunas marcadas no arquivo de destino.
INFORMAÇÕES LOCAIS DO AMBIENTE (Arquivos da mesma pasta para consistência):
{info_locais}

INFORMAÇÕES IMPORTANTES RELACIONADAS:
{info_importante}

CONTEÚDO ORIGINAL DO ARQUIVO ATUAL ({arquivo.name}):
{conteudo}

TAREFA:
No conteúdo do arquivo atual, identifique a linha que começa com a variação de To-Do '{tag_encontrada}'.
Substitua essa linha pelo conteúdo expandido de forma criativa, mantendo total coesão com a história local e as diretrizes de {pu.PASTA_PROJETO}.

REGRAS DE RETORNO:
1. Retorne o texto completo do arquivo original, incluindo a modificação feita.
2. Preserve rigorosamente a formatação Markdown existente.
3. Não acrescente prefácios, comentários explicativos ou notas sobre o que você modificou. Retorne apenas o conteúdo final do arquivo editado.
"""
        try:
            # Opcional: Registrar o prompt gerado para fins de depuração
            with open(pu.log_path("Prompts.txt"), 'w', encoding='utf-8') as f:
                f.write(f"Alterando Arquivo: {arquivo.name}\n")
                f.write(prompt_conteudo + '\n')
                
            # Substituição da chamada nativa pela função estruturada ask_ai
            # Graças ao ask_ai, a verificação de fallbacks de modelos e limites de taxa é herdada automaticamente.
            texto_expandido = au.ask_ai(
                contents=prompt_conteudo,
                system_instruction=instrucoes_globais,
                temperature=0.7,
                use_world_context=True
            )
            
            if texto_expandido:
                texto_limpo = remover_markdown_fences(texto_expandido)
                novo_arquivo_path = obter_proximo_nome_versao(arquivo)
                
                with open(novo_arquivo_path, 'w', encoding='utf-8') as f:
                    f.write(texto_limpo)
                arquivar_versao_antiga(arquivo)
                print(f"✅ Nova versão gerada com sucesso: {novo_arquivo_path.name}")
            else:
                print(f"⚠️ O retorno do modelo para {arquivo.name} foi vazio.")
            
        except Exception as e:
            print(f"❌ Erro ao processar {arquivo.name}: {e}")

def processar_arquivos():
    caminho_projeto = Path(pu.PASTA_PROJETO)
    encontrou_tag = False
    
    for arquivo in caminho_projeto.rglob("*.md"):
        if pu.is_cancelled():
            print("\n🛑 Processamento do Expander interrompido pelo usuário!")
            return
        with open(arquivo, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            
        if any(tag in conteudo for tag in pu.TAG_ALVO):
            encontrou_tag = True
            processar_arquivo_unico(arquivo)
            
    if not encontrou_tag:
        print("Nenhuma tag encontrada.")

if __name__ == "__main__":
    processar_arquivos()
    print("\n✅ Processamento concluído!")