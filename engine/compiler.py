import os, re, unicodedata
from pathlib import Path
import engine.project_utils as pu

def _limpar_titulo_exibicao(nome: str) -> str:
    """Remove prefixos numéricos (ex: '0.', '01_') e sufixos de versão (_v01) para exibição limpa."""
    nome_limpo = re.sub(r'^\d+[\._\-\s]*', '', nome)
    nome_limpo = re.sub(r'_v\d+$', '', nome_limpo, flags=re.IGNORECASE)
    return nome_limpo.replace("_", " ").strip().title()

def _limpar_conteudo_markdown(texto: str) -> str:
    """Remove metadados de rascunho e tags TODO do texto final do livro."""
    linhas = []
    for linha in texto.splitlines():
        if any(tag in linha for tag in pu.TAG_ALVO):
            continue
        if "status: rascunho" in linha.lower():
            continue
        linhas.append(linha)
    return "\n".join(linhas).strip()

def _markdown_para_html(md_texto: str) -> str:
    """Converte sintaxe básica de Markdown para HTML formatado para RPG."""
    texto = _limpar_conteudo_markdown(md_texto)
    if not texto:
        return ""

    html_linhas = []
    em_lista = False
    em_blockquote = False

    for linha in texto.splitlines():
        linha_str = linha.strip()

        if em_lista and not (linha_str.startswith("- ") or linha_str.startswith("* ")):
            html_linhas.append("</ul>")
            em_lista = False

        if em_blockquote and not linha_str.startswith(">"):
            html_linhas.append("</div>")
            em_blockquote = False

        if linha_str.startswith("### "):
            html_linhas.append(f"<h3>{linha_str[4:]}</h3>")
        elif linha_str.startswith("## "):
            html_linhas.append(f"<h2>{linha_str[3:]}</h2>")
        elif linha_str.startswith("# "):
            html_linhas.append(f"<h1>{linha_str[2:]}</h1>")

        elif linha_str.startswith("---") or linha_str.startswith("***"):
            html_linhas.append("<hr>")

        elif linha_str.startswith(">"):
            if not em_blockquote:
                html_linhas.append('<div class="lore-box">')
                em_blockquote = True
            conteudo_quote = linha_str.lstrip(">").strip()
            html_linhas.append(f"<p><em>{conteudo_quote}</em></p>")

        elif linha_str.startswith("- ") or linha_str.startswith("* "):
            if not em_lista:
                html_linhas.append("<ul>")
                em_lista = True
            html_linhas.append(f"<li>{linha_str[2:]}</li>")

        elif not linha_str:
            continue

        else:
            html_linhas.append(f"<p>{linha_str}</p>")

    if em_lista:
        html_linhas.append("</ul>")
    if em_blockquote:
        html_linhas.append("</div>")

    resultado = "\n".join(html_linhas)
    resultado = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', resultado)
    resultado = re.sub(r'\*(.*?)\*', r'<em>\1</em>', resultado)
    
    def _substituir_wikilink(match):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else target
        slug = f"doc-{re.sub(r'[^a-zA-Z0-9]', '', target.lower())}"
        return f'<a href="#{slug}" class="obsidian-link">{alias}</a>'

    texto = re.sub(r'\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]', _substituir_wikilink, texto)
    
    return resultado

def _obter_estrutura_ordenada(caminho_raiz):
    """
    Percorre a estrutura de pastas respeitando a Ordem Livre salva em logs/folder_orders.json
    e selecionando apenas a versão mais recente de cada arquivo.
    """
    estrutura = []

    def navegar(pasta_atual):
        # Lê os itens na ordem manual definida pelo usuário no Explorer
        itens_ordenados = pu.obter_itens_ordenados(pasta_atual)
        
        arquivos_md = []
        subpastas = []
        
        for item in itens_ordenados:
            item_path = pasta_atual / item
            if item_path.is_dir():
                subpastas.append(item_path)
            elif item_path.is_file() and item.lower().endswith(".md"):
                arquivos_md.append(item_path)

        # Agrupa arquivos por nome base para filtrar apenas a maior versão (ex: _v02 sobrepõe _v01)
        grupos_versao = {}
        for f in arquivos_md:
            nome_base = re.sub(r'_v\d+$', '', f.stem, flags=re.IGNORECASE)
            if nome_base not in grupos_versao:
                grupos_versao[nome_base] = []
            grupos_versao[nome_base].append(f)

        arquivos_finais = []
        visitados = set()
        for f in arquivos_md:
            nome_base = re.sub(r'_v\d+$', '', f.stem, flags=re.IGNORECASE)
            if nome_base not in visitados:
                visitados.add(nome_base)
                versoes = grupos_versao[nome_base]
                def get_version(p):
                    m = re.search(r'_v(\d+)$', p.stem, flags=re.IGNORECASE)
                    return int(m.group(1)) if m else 0
                versoes.sort(key=get_version, reverse=True)
                arquivos_finais.append(versoes[0])

        if arquivos_finais:
            relativo = pasta_atual.relative_to(caminho_raiz)
            nome_capitulo = str(relativo) if str(relativo) != "." else "Visão Geral do Mundo"
            estrutura.append((nome_capitulo, arquivos_finais))

        for sub in subpastas:
            navegar(sub)

    navegar(caminho_raiz)
    return estrutura

def compilar_livro_cenario():
    """Compila todo o projeto de lore em um documento HTML formatado como livro de RPG."""
    caminho = Path(pu.CAMINHO_PROJETO)
    if not caminho.exists():
        print(f"Erro: Pasta do projeto '{pu.PASTA_PROJETO}' não encontrada.")
        return None

    # 1. Obtém a estrutura na ordem manual exata definida no Explorer
    estrutura_capitulos = _obter_estrutura_ordenada(caminho)

    if not estrutura_capitulos:
        print("Nenhum conteúdo válido encontrado para compilar.")
        return None

    # 2. Gerar Sumário (TOC) e Conteúdo HTML
    indice_html = []
    conteudo_html = []
    capitulo_id = 1

    for cap_caminho_rel, lista_arquivos in estrutura_capitulos:
        cap_slug = f"capitulo-{capitulo_id}"
        
        # Limpa o título do capítulo (ex: "0.InTheBeginning" vira "In The Beginning")
        if cap_caminho_rel != "Visão Geral do Mundo":
            partes_cap = [_limpar_titulo_exibicao(p) for p in Path(cap_caminho_rel).parts]
            cap_titulo_limpo = " › ".join(partes_cap)
        else:
            cap_titulo_limpo = "Visão Geral do Mundo"

        # Item do Capítulo no Sumário
        indice_html.append(f'<li><a href="#{cap_slug}"><strong>Capítulo {capitulo_id}: {cap_titulo_limpo}</strong></a><ul>')
        
        # Início do Capítulo no Livro
        conteudo_html.append(f'<section class="capitulo" id="{cap_slug}">')
        conteudo_html.append(f'<h1 class="capitulo-titulo">Capítulo {capitulo_id}<br><span>{cap_titulo_limpo}</span></h1>')

        for arq in lista_arquivos:
            try:
                with open(arq, "r", encoding="utf-8") as f_obj:
                    raw_text = f_obj.read()
            except UnicodeDecodeError:
                continue

            doc_slug = f"doc-{re.sub(r'[^a-zA-Z0-9]', '', arq.stem)}"
            doc_titulo = _limpar_titulo_exibicao(arq.stem)

            # Item do Documento no Sumário
            indice_html.append(f'<li><a href="#{doc_slug}">{doc_titulo}</a></li>')

            # Renderiza o Conteúdo
            html_doc = _markdown_para_html(raw_text)
            if html_doc:
                conteudo_html.append(f'<article class="documento" id="{doc_slug}">')
                conteudo_html.append(f'<h2>{doc_titulo}</h2>')
                conteudo_html.append(html_doc)
                conteudo_html.append('</article>')

        conteudo_html.append('</section>')
        indice_html.append('</ul></li>')
        capitulo_id += 1

    # 3. Template HTML com Estilo Dark Fantasy
    nome_mundo = pu.PASTA_PROJETO.upper()

    documento_completo = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Compêndio de {nome_mundo} - Livro do Cenário</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

        :root {{
            --bg-color: #0f0f11;
            --card-bg: #18181c;
            --text-color: #d1d5db;
            --accent-gold: #d97706;
            --accent-emerald: #10b981;
            --border-color: #374151;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Lora', serif;
            line-height: 1.7;
            margin: 0;
            padding: 0;
        }}

        .page-container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        .cover-page {{
            text-align: center;
            padding: 100px 20px;
            border: 3px double var(--accent-gold);
            background: radial-gradient(circle, #1f1f24 0%, #0f0f11 100%);
            margin-bottom: 60px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
        }}

        .cover-page h1 {{
            font-family: 'Cinzel', serif;
            font-size: 3.5rem;
            color: var(--accent-gold);
            letter-spacing: 4px;
            margin-bottom: 10px;
            text-shadow: 0 0 15px rgba(217, 119, 6, 0.4);
        }}

        .cover-page p {{
            font-size: 1.2rem;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}

        .toc-box {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-left: 5px solid var(--accent-emerald);
            padding: 30px;
            margin-bottom: 60px;
            border-radius: 4px;
        }}

        .toc-box h2 {{
            font-family: 'Cinzel', serif;
            color: var(--accent-emerald);
            margin-top: 0;
        }}

        .toc-box ul {{
            list-style: none;
            padding-left: 15px;
        }}

        .toc-box a {{
            color: #60a5fa;
            text-decoration: none;
            font-size: 1.05rem;
        }}

        .toc-box a:hover {{
            text-decoration: underline;
            color: var(--accent-gold);
        }}

        .capitulo {{
            margin-bottom: 80px;
            page-break-before: always;
        }}

        .capitulo-titulo {{
            font-family: 'Cinzel', serif;
            font-size: 2.5rem;
            color: var(--accent-gold);
            border-bottom: 2px solid var(--accent-gold);
            padding-bottom: 10px;
            text-transform: uppercase;
        }}

        .capitulo-titulo span {{
            font-size: 1.5rem;
            color: #e5e7eb;
        }}

        .documento {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 6px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}

        .documento h2 {{
            font-family: 'Cinzel', serif;
            color: var(--accent-emerald);
            margin-top: 0;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 6px;
        }}

        .lore-box {{
            background-color: #111827;
            border: 1px solid #1f2937;
            border-left: 4px solid var(--accent-gold);
            padding: 15px 20px;
            margin: 20px 0;
            font-style: italic;
            color: #d1d5db;
            border-radius: 0 4px 4px 0;
        }}

        hr {{
            border: None;
            height: 1px;
            background: linear-gradient(to right, transparent, var(--border-color), transparent);
            margin: 30px 0;
        }}

        @media print {{
            body {{
                background-color: #ffffff !important;
                color: #111111 !important;
            }}
            .cover-page, .documento, .toc-box, .lore-box {{
                background: #ffffff !important;
                color: #111111 !important;
                box-shadow: none !important;
                border-color: #cccccc !important;
            }}
            .cover-page h1, .capitulo-titulo, .documento h2 {{
                color: #000000 !important;
            }}
            a {{
                color: #111111 !important;
                text-decoration: none !important;
            }}
            .capitulo {{
                page-break-before: always;
            }}
        }}
        .stat-block {{
            background-color: #fdf1dc;
            border: 2px solid #922610;
            padding: 15px;
            margin: 20px 0;
            box-shadow: 0 0 5px rgba(0,0,0,0.5);
            color: #000000;
            font-family: 'Georgia', serif;
        }}

        .stat-block h2 {{
            color: #7a200d;
            font-family: 'Cinzel', serif;
            margin: 0;
            font-size: 1.6rem;
        }}

        .stat-block h3 {{
            color: #7a200d;
            border-bottom: 1px solid #7a200d;
            font-size: 1.1rem;
            margin-top: 10px;
        }}

        .stat-block hr {{
            border: 0;
            height: 2px;
            background: #922610;
            margin: 8px 0;
        }}
    </style>
</head>
<body>
    <div class="page-container">
        
        <div class="cover-page">
            <h1>{nome_mundo}</h1>
            <p>Compêndio Oficial de Cenário</p>
            <p style="font-size: 0.9rem; margin-top: 40px; color: #6b7280;">Gerado por Ao Multiverse Console</p>
        </div>

        <div class="toc-box">
            <h2>Sumário do Mundo</h2>
            <ul>
                {"".join(indice_html)}
            </ul>
        </div>

        {"".join(conteudo_html)}

    </div>
</body>
</html>
"""

    # 4. Salva o HTML
    pasta_export = pu.PASTA_EXPORTS
    pasta_export.mkdir(exist_ok=True, parents=True)
    caminho_saida = pasta_export / f"Livro_do_Cenario_{pu.PASTA_PROJETO}.html"

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(documento_completo)

    print(f"Livro do Cenário compilado com sucesso em: {caminho_saida}")
    return caminho_saida