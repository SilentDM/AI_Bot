import os, re, shutil
from pathlib import Path
import core.ai_utils as au
import engine.project_utils as pu

ARQUIVOS_EM_PROCESSAMENTO = set()

def esta_em_processamento(caminho) -> bool:
    caminho_abs = str(Path(caminho).resolve())
    return caminho_abs in ARQUIVOS_EM_PROCESSAMENTO

def marcar_processamento(caminho, ativo: bool):
    caminho_abs = str(Path(caminho).resolve())
    if ativo:
        ARQUIVOS_EM_PROCESSAMENTO.add(caminho_abs)
    else:
        ARQUIVOS_EM_PROCESSAMENTO.discard(caminho_abs)

def salvar_snapshot_historico(caminho_original) -> Path | None:
    """
    Salva uma cópia de backup da versão atual na pasta logs/history/
    com sufixo de versão antes de sobrescrever o arquivo original do projeto.
     Preserva o nome do arquivo original para não quebrar Wikilinks do Obsidian!
    """
    try:
        caminho_obj = Path(caminho_original)
        if not caminho_obj.exists():
            return None

        pasta_historico = pu.PASTA_LOGS / "history"
        try:
            relativo = caminho_obj.relative_to(pu.CAMINHO_PROJETO)
            destino_dir = pasta_historico / relativo.parent
        except ValueError:
            destino_dir = pasta_historico

        destino_dir.mkdir(parents=True, exist_ok=True)

        nome_base = caminho_obj.stem
        ext = caminho_obj.suffix or ".md"

        # Calcula o número da versão para salvar na pasta de histórico
        maior_v = 0
        for arq in destino_dir.glob(f"{nome_base}_v*{ext}"):
            match = re.search(r'_v(\d+)$', arq.stem)
            if match:
                maior_v = max(maior_v, int(match.group(1)))

        nova_v = maior_v + 1
        nome_backup = f"{nome_base}_v{nova_v:02d}{ext}"
        caminho_backup = destino_dir / nome_backup

        shutil.copy2(str(caminho_obj), str(caminho_backup))
        print(f"📦 Backup de histórico salvo em: logs/history/{caminho_backup.name}")
        return caminho_backup
    except Exception as e:
        print(f"Erro ao salvar snapshot de histórico ({caminho_original}): {e}")
        return None

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
        titulo_limpo = re.sub(r'_',' ', titulo.lower())
        score = conteudo.lower().count(titulo_limpo)
        if score > 0:
            relacionados.append((arquivo.name, conteudo, score))

    relacionados.sort(key=lambda x: x[2], reverse=True)
    relacionados = relacionados[:10]
    
    return "\n\n".join(conteudo for _, conteudo, _ in relacionados)

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
    
    if esta_em_processamento(path):
        print(f"⚠️ Arquivo {Path(path).name} já está sendo processado pelo Expander. Pulando...")
        return

    marcar_processamento(path, True)

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
            conteudo = f.read()

        tag_encontrada = next((tag for tag in pu.TAG_ALVO if tag in conteudo), None)
        if tag_encontrada:
            print(f"\n=====\nTag encontrada no arquivo: {arquivo.name}\n=====")
            
            info_importante = obter_arquivos_relacionados(arquivo.stem.lower())
            prompt_conteudo = f"""
<arquivos_relacionados>
{info_importante}
</arquivos_relacionados>

<arquivo_alvo nome="{arquivo.name}">
{conteudo}
</arquivo_alvo>

<instrucao_tarefa>
Identifique a tag '{tag_encontrada}' dentro da tag <arquivo_alvo>.
Substitua essa tag pelo conteúdo expandido, mantendo total coesão com os arquivos do universo.
</instrucao_tarefa>

<regras_de_resposta>
1. Retorne APENAS o conteúdo final do arquivo editado em Markdown.
2. Não inclua comentários, prefácios nem tags XML na sua resposta final.
3. FORMATAÇÃO E WIKILINKS:
    - Organize o texto com títulos (#, ##, ###).
    - Use citações (> texto) para caixas de lore, rumores, manuscritos ou diários.
    - Use negrito (**palavra**) em termos e itens de destaque.
    - CRIE WIKILINKS [[Nome do Conceito]]: Sempre que mencionar personagens, cidades, locais, facções, deuses ou relíquias do universo, envolva o nome em colchetes duplos (ex: [[Reino de Lucius]], [[Mestre Varis]], [[Catedral de Prata]]).
</regras_de_resposta>
"""
            try:
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
                    
                    # 1. Salva o backup da versão atual na pasta logs/history/
                    salvar_snapshot_historico(arquivo)

                    # 2. Atualiza o arquivo ORIGINAL diretamente no projeto (preservando o nome para o Obsidian!)
                    with open(arquivo, 'w', encoding='utf-8') as f:
                        f.write(texto_limpo)

                    print(f"✅ Arquivo atualizado in-place com sucesso: {arquivo.name}")
                else:
                    print(f"O retorno do modelo para {arquivo.name} foi vazio.")
                
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo.name}: {e}")

    finally:
        marcar_processamento(path, False)

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