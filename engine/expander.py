import os, re, shutil
from pathlib import Path
import core.ai_utils as au
import engine.project_utils as pu

ARQUIVOS_EM_PROCESSAMENTO = set()

def arquivar_versao_antiga(caminho_original):
    """
    Move a versão antiga/original de um arquivo para a pasta logs/history/,
    preservando a estrutura de subpastas.
    """
    try:
        caminho_original = Path(caminho_original)
        if not caminho_original.exists():
            return

        pasta_historico = pu.PASTA_LOGS / "history"
        try:
            relativo = caminho_original.relative_to(pu.CAMINHO_PROJETO)
            destino_dir = pasta_historico / relativo.parent
        except ValueError:
            destino_dir = pasta_historico

        destino_dir.mkdir(parents=True, exist_ok=True)
        destino_arquivo = destino_dir / caminho_original.name

        # 🛡️ Se o arquivo já existir no histórico, remove antes para o shutil.move não falhar no Windows
        if destino_arquivo.exists():
            try:
                destino_arquivo.unlink()
            except Exception:
                pass

        shutil.move(str(caminho_original), str(destino_arquivo))
    except Exception as e:
        print(f"Erro ao arquivar versão antiga ({caminho_original.name}): {e}")

def obter_arquivos_relacionados(titulo):
    relacionados = []
    for arquivo in Path(pu.PASTA_PROJETO).rglob("*.md"):
        if any(part in pu.IGNORELIST for part in arquivo.parts):
            continue
        try:
            with open(arquivo, encoding="utf-8", errors="ignore") as f:
                conteudo = f.read()
        except Exception:
            continue
        if (
            arquivo.stem.lower() == titulo
            or any(tag in conteudo for tag in pu.TAG_ALVO)
            or any(ignore in conteudo for ignore in pu.IGNORELIST)
        ):
            continue
        titulo = re.sub(r'_v\d+$', '', titulo.lower())
        titulo = re.sub(r'_',' ', titulo)
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
                    titulo = arquivo.stem.replace(" ", "_").replace("-", "_").lower()
                    conteudo_estilo.append(f"\n<diretrizes_de_{titulo}>\n{f.read().strip()}\n</diretrizes_de_{titulo}>\n")
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

def carregar_diretrizes_estilo():
    pasta_estilo = pu.CAMINHO_ESTILO
    conteudo_estilo = []
    if pasta_estilo.exists() and pasta_estilo.is_dir():
        for arquivo in sorted(pasta_estilo.glob("*.md")):
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    titulo = arquivo.stem.replace(" ", "_").replace("-", "_").lower()
                    conteudo_estilo.append(f"\n<diretrizes_de_{titulo}>\n{f.read().strip()}\n</diretrizes_de_{titulo}>\n")
            except Exception as e:
                print(f"Erro ao carregar diretriz {arquivo.name}: {e}")
    return "".join(conteudo_estilo)

def nome_base(path):
    return re.sub(r'_v\d+$', '', path.stem.lower())

def remover_markdown_fences(texto: str) -> str:
    linhas = texto.strip().splitlines()
    if not linhas:
        return texto

    if linhas[0].strip().startswith("```"):
        linhas.pop(0)
        
    if linhas and linhas[-1].strip().startswith("```"):
        linhas.pop()
        
    return "\n".join(linhas).strip()

def processar_arquivo_unico(path):
    caminho_abs = str(Path(path).resolve())
    
    # 🛡️ Trava de Segurança contra execução em duplicidade / loop
    if caminho_abs in ARQUIVOS_EM_PROCESSAMENTO:
        print(f"⚠️ Arquivo {Path(path).name} já está sendo processado pelo Expander. Pulando...")
        return

    ARQUIVOS_EM_PROCESSAMENTO.add(caminho_abs)

    try:
        estilo_contexto = carregar_diretrizes_estilo()
        instrucoes_globais = f"""
    Você é um Mestre de Mesa (DM) de D&D experiente e escritor de fantasia sombria (Dark Fantasy).
    Seu objetivo é preencher lacunas de desenvolvimento do cenário de {pu.PASTA_PROJETO}.
    # Diretrizes e Regras Adicionais do Projeto:
    {estilo_contexto}
    """
        arquivo = Path(path)
        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
            conteudo = "".join(linhas)
            titulo = arquivo.stem
            titulo = re.sub(r'_v\d+$', '', titulo.lower())

        tag_encontrada = next((tag for tag in pu.TAG_ALVO if tag in conteudo), None)
        if tag_encontrada:
            print(f"\n=====\nTag encontrada no arquivo:\n{arquivo.name}\n=====")
            info_locais = ""
            grupos_locais = {}
            for arq_p in arquivo.parent.glob("*.md"):
                base = nome_base(arq_p)
                if base != nome_base(arquivo):
                    if base not in grupos_locais:
                        grupos_locais[base] = []
                    grupos_locais[base].append(arq_p)

            for base, lista_vers in grupos_locais.items():
                def _ver(p):
                    m = re.search(r'_v(\d+)$', p.stem, flags=re.IGNORECASE)
                    return int(m.group(1)) if m else 0
                lista_vers.sort(key=_ver, reverse=True)
                arq_mais_recente = lista_vers[0]
                
                try:
                    with open(arq_mais_recente, "r", encoding="utf-8") as f:
                        conteudo_local = f.read()
                        if not any(tag in conteudo_local for tag in pu.TAG_ALVO) and "status: rascunho" not in conteudo_local.lower():
                            info_locais += conteudo_local + "\n\n"
                except Exception:
                    pass

            info_importante = obter_arquivos_relacionados(titulo)
            prompt_conteudo = f"""
<contexto_local>
{info_locais}
</contexto_local>

<arquivos_relacionados>
{info_importante}
</arquivos_relacionados>

<arquivo_alvo nome="{arquivo.name}">
{conteudo}
</arquivo_alvo>

<instrucao_tarefa>
Identifique a tag '{tag_encontrada}' dentro da tag <arquivo_alvo>.
Substitua essa tag pelo conteúdo expandido, mantendo total coesão com <contexto_local> e <arquivos_relacionados>.
</instrucao_tarefa>

<regras_de_resposta>
1. Retorne APENAS o conteúdo final do arquivo editado em Markdown.
2. Não inclua comentários, prefácios nem tags XML na sua resposta final.
</regras_de_resposta>
"""
            try:
                with open(pu.log_path("Prompts.txt"), 'w', encoding='utf-8') as f:
                    f.write(f"Alterando Arquivo: {arquivo.name}\n")
                    f.write(prompt_conteudo + '\n')
                
                texto_bruto = au.ask_ai(contents=prompt_conteudo, system_instruction=instrucoes_globais, temperature=0.7)

                prompt_revisao = f"""
Você é o Editor de Lore de {pu.PASTA_PROJETO}.
Revise o texto gerado abaixo e garanta que ele NÃO contradiga a história já estabelecida no cache.
Se encontrar incoerências com o tom ou com a lore existente, corrija-as. Caso contrário, devolva o texto exato.

TEXTO GERADO:
{texto_bruto}
"""
                texto_final = au.ask_ai(
                    contents=prompt_revisao,
                    system_instruction="Você é um editor de texto rigoroso focado em consistência de worldbuilding.",
                    temperature=0.2,
                    use_world_context=True
                )
                
                if texto_final:
                    texto_limpo = remover_markdown_fences(texto_final)
                    novo_arquivo_path = obter_proximo_nome_versao(arquivo)
                    
                    with open(novo_arquivo_path, 'w', encoding='utf-8') as f:
                        f.write(texto_limpo)
                    arquivar_versao_antiga(arquivo)
                    print(f"Nova versão gerada com sucesso: {novo_arquivo_path.name}")
                else:
                    print(f"O retorno do modelo para {arquivo.name} foi vazio.")
                
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo.name}: {e}")

    finally:
        # Libera o arquivo do set ao finalizar
        ARQUIVOS_EM_PROCESSAMENTO.discard(caminho_abs)

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