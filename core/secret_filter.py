import re

TAGS_SEGREDO = ["[segredo]", "<!-- segredo -->", "<-- segredo", "status: segredo"]

def filtrar_conteudo_por_permissao(texto_markdown: str, is_dm: bool = True) -> str:
    """
    Se is_dm=True: Retorna o texto 100% completo com todos os segredos.
    Se is_dm=False: Remove mecanicamente seções secretas marcadas com [SEGREDO].
    """
    if is_dm or not texto_markdown:
        return texto_markdown

    linhas = texto_markdown.splitlines()
    linhas_limpas = []

    ocultando_secao = False
    nivel_secao_oculta = 0

    # Estado para o bloco YAML "tags:" em formato de lista:
    # tags:
    #   - segredo
    #   - outra-tag
    dentro_de_tags_lista = False

    for linha in linhas:
        linha_str = linha.strip()
        linha_lower = linha_str.lower()

        # --- BLOCO YAML: tags em formato de lista (multi-linha) ---
        # Detecta o início do bloco: uma linha "tags:" sozinha (sem valor na mesma linha)
        if re.match(r'^tags:\s*$', linha_lower):
            dentro_de_tags_lista = True
            continue  # a própria linha "tags:" nunca precisa ocultar o arquivo sozinha

        if dentro_de_tags_lista:
            # Enquanto estivermos dentro do bloco, itens de lista têm este formato:
            # "  - segredo"  ou  "- segredo"
            item_lista = re.match(r'^-\s*(.+)$', linha_str)
            if item_lista:
                valor_item = item_lista.group(1).strip().strip('"\'').lower()
                if valor_item == "segredo":
                    return ""  # Oculta o arquivo inteiro
                continue  # outro item de lista qualquer, segue no bloco
            elif linha_str == "":
                # linha em branco dentro do bloco: ainda pode haver mais itens depois
                continue
            else:
                # Qualquer linha que não seja "- item" nem em branco encerra o bloco de tags
                dentro_de_tags_lista = False
                # (não faz "continue" aqui: deixa a linha atual seguir o processamento normal abaixo)

        # --- Formatos já cobertos: status: segredo, e tags inline (tags: [segredo, x] / tags: segredo) ---
        if "status: segredo" in linha_lower:
            return ""

        if "tags:" in linha_lower and "segredo" in linha_lower:
            return ""  # Oculta o arquivo inteiro se o YAML tiver tag 'segredo' na mesma linha

        match_header = re.match(r'^(#{1,6})\s+(.*)$', linha_str)

        if match_header:
            nivel_atual = len(match_header.group(1))
            header_texto = match_header.group(2).lower()

            if ocultando_secao and nivel_atual <= nivel_secao_oculta:
                ocultando_secao = False

            if any(tag in header_texto for tag in TAGS_SEGREDO):
                ocultando_secao = True
                nivel_secao_oculta = nivel_atual
                continue

        elif any(tag in linha_lower for tag in TAGS_SEGREDO):
            continue

        if not ocultando_secao:
            linhas_limpas.append(linha)

    return "\n".join(linhas_limpas).strip()