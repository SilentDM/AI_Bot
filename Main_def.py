from email.mime import message
from encodings import aliases
import unicodedata, re
import requests


def normalize_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r"([^a-zA-Z0-9])", ' ', text)
    return text

def kobold_online():
    try:
        r = requests.get("http://localhost:5001", timeout=2)
        return True
    except:
        return False

def trim_incomplete_sentences(texto):
    texto = texto.strip()
    if texto.endswith((".", "!", "?")):
        return texto

    # Divide por finais de frase
    frases = re.split(r'(?<=[.!?])\s+', texto)

    # Se só tem uma frase, não dá pra salvar muito
    if len(frases) <= 1:
        return frases[0] if frases else texto

    # Remove última frase (provavelmente incompleta)
    frases = frases[:-1]

    resultado = " ".join(frases).strip()

    # Garantir que termina corretamente
    if not resultado.endswith((".", "!", "?")):
        resultado += "."

    return resultado


def carregar_phaeton():
    with open("Phaeton.txt", "r", encoding="latin1") as f:
        return f.read()

def carregar_aliases():
    aliases = {}

    with open("aliases.txt", "r", encoding="latin1") as f:
        for linha in f:
            linha = linha.strip()

            if not linha or linha.startswith("#"):
                continue

            chave, valores = linha.split(":")
            alias_list = [v.strip() for v in valores.split(",")]

            aliases[chave.strip()] = alias_list
    return aliases

def detectar_intencao(pergunta):
    pergunta = normalize_text(pergunta)
    if "onde" in pergunta:
        return "Foque na localização"
    elif "quando" in pergunta:
        return "Foque no histórico ou cronologia"
    elif "quem" in pergunta:
        return "Foque na entidade ou pessoa"
    elif "como" in pergunta:
        return "Foque no método ou processo"
    elif "por que" in pergunta or "porque" in pergunta:
        return "Foque na causa"
    else:
        return ""

def remover_conectores(pergunta):
    conectores_simples = {
        "!ao","e","é","o","ou","os","mas","se","a","te","de","da","do","em",
        "que","seu","vc","voce","você","eu","nos","nós",
        "porém","entretanto","todavia","contudo",
        "portanto","logo","assim","porque","pois",
        "pra","para","com","sobre","isso","esse","essa",
        "qual","quais","quem","quando"
    }
    palavras = pergunta.split()  # ✅ AGORA sim divide corretamente
    palavras_encontradas = []
    resultado = []
    for palavra in palavras:
        if palavra in conectores_simples:
            palavras_encontradas.append(palavra)
    resultado = [palavra for palavra in palavras if palavra not in palavras_encontradas]
    resultado = normalize_text(" ".join(resultado)).split()
    return resultado


def dividir_texto(texto):
    chunks = {}
    secao_atual = None

    for linha in texto.split("\n"):
        linha = linha.strip()

        # detectar títulos tipo === TITULO ===
        if linha.startswith("===") and linha.endswith("==="):
            secao_atual = linha.strip("=").strip().lower()
            chunks[secao_atual] = ""

        elif secao_atual:
            chunks[secao_atual] += linha + "\n"

    return chunks


def aplicar_aliases(pergunta, titulo, aliases):
    score = 0

    for chave, sinonimos in aliases.items():
        for s in sinonimos:
            if s in pergunta:
                if chave in titulo:
                    score += 15

    return score


def calcular_score(pergunta, titulo, conteudo):
    pergunta = pergunta.lower()
    titulo = titulo.lower()
    conteudo = conteudo.lower()
    aliases = carregar_aliases()
    score = 0
    palavras = remover_conectores(pergunta)
    for palavra in palavras:
        if palavra in titulo:
            score += 15  # título é muito importante
        if palavra in conteudo:
            score += 3  # conteúdo ainda importa
        else:
            score += 1
    score += aplicar_aliases(palavras, titulo, aliases)    
    return score


def rankear_chunks(chunks, pergunta):
    resultados = []

    for titulo, conteudo in chunks.items():
        score = calcular_score(pergunta, titulo, conteudo)
        tokens = len(conteudo)/4  # estimativa de tokens (1 token ~ 4 caracteres)
        resultados.append((score, titulo, conteudo, tokens))

    # ordenar do maior score para menor
    resultados.sort(key=lambda x: x[0], reverse=True)
    
    #print("\n=== ORDEM FINAL ===")
    #for score, titulo, _ in resultados:
    #    print(f"{score} -> {titulo}")

    return resultados


def montar_info(chunks, pergunta, limite_chars=7500):
    ranked = rankear_chunks(chunks, pergunta)

    info = ""

    for score, titulo, conteudo, tokens in ranked:
        if score == 0:
            continue  # ignora irrelevantes

        bloco = f"[{titulo.upper()}]\n{conteudo}\n\n"

        if len(info) + len(bloco) > limite_chars:
            break

        info += bloco

    return info.strip()

def gerar_info(pergunta):
    texto = carregar_phaeton()
    chunks = dividir_texto(texto)
    info = montar_info(chunks, pergunta)
    return info
