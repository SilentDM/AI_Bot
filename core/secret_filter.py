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
    for linha in linhas:
        linha_str = linha.strip()
        linha_lower = linha_str.lower()
        if "status: segredo" in linha_lower:
            return ""
        if "tags:" in linha_lower and "segredo" in linha_lower:
            return ""  
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