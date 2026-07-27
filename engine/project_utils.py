import os, re, json, threading, unicodedata, difflib
from pathlib import Path
from datetime import datetime


PASTA_PROJETO = os.getenv("PASTA_PROJETO", "Phaeton")
CAMINHO_PROJETO = os.path.join(os.getcwd(), PASTA_PROJETO)
PASTA_ESTILO = os.getenv("PASTA_ESTILO", "Style")
CAMINHO_ESTILO = (Path.cwd()/PASTA_ESTILO)
PASTA_LOGS = Path.cwd() / "logs"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASTA_LOGS.mkdir(exist_ok=True,parents=True)
TAG_ALVO = [
    "<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo",
    "<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do",
    "<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", 
    "<-- To-do", "<-- Todo:"
]
IGNORELIST = [
    "Templates", 
    "status: rascunho"
]
# Sinalizador global de cancelamento
_CANCEL_EVENT = threading.Event()

STOP_WORDS = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", 
    "o", "a", "os", "as", "e", "the", "of", "and", "in", "on", "para", "com"
}
ARQUIVO_ORDEM_GLOBAL = PASTA_LOGS / "folder_orders.json"

def normalizar_nome(nome: str) -> str:
    """Normaliza o nome removendo extensão, sufixos de versão, acentos e separadores."""
    nome = Path(nome).stem  # Remove extensão .md se houver
    nome = re.sub(r'_v\d+$', '', nome, flags=re.IGNORECASE)  # Remove sufixos como _v01
    nome = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII")
    nome = nome.lower().strip()
    # Substitui separadores comuns (underlines, hífens, pontos) por espaços
    nome = re.sub(r'[_\-+.]', ' ', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

def extrair_palavras_chave(nome: str):
    """Retorna o nome normalizado completo e uma lista com suas palavras-chave relevantes."""
    norm = normalizar_nome(nome)
    palavras = norm.split()
    
    # Filtra palavras curtas (<=2 letras) e stop words (de, da, do...)
    # Também remove 's' do final para tratar singular/plural simples
    palavras_relevantes = []
    for p in palavras:
        if len(p) > 2 and p not in STOP_WORDS:
            if p.endswith('s') and len(p) > 3:
                p = p[:-1]
            palavras_relevantes.append(p)
            
    return norm, palavras_relevantes

def existe_nome_parecido(nome_proposto: str, pasta_destino: Path, limiar: float = 0.65):
    """
    Verifica se já existe na pasta_destino um arquivo/pasta com nome igual,
    parecido, contido ou compartilhando palavras-chave principais.
    Retorna o nome do item existente se encontrar, ou None caso contrário.
    """
    if not pasta_destino.exists():
        return None

    alvo_norm, alvo_kw = extrair_palavras_chave(nome_proposto)

    for item in pasta_destino.iterdir():
        existente_norm, existente_kw = extrair_palavras_chave(item.name)

        # 1. Comparação Direta por Porcentagem de Similaridade (ex: Segredo vs Segreod)
        similaridade = difflib.SequenceMatcher(None, alvo_norm, existente_norm).ratio()
        if similaridade >= limiar:
            return item.name

        # 2. Inclusão por Substring (ex: "Eras" em "Eras_de_Phaeton" ou vice-versa)
        if len(existente_norm) >= 3 and len(alvo_norm) >= 3:
            if existente_norm in alvo_norm or alvo_norm in existente_norm:
                return item.name

        # 3. Interseção de Palavras-Chave Principais (ex: "Eras" compartilhada como token)
        for kw_alvo in alvo_kw:
            for kw_existente in existente_kw:
                if kw_alvo == kw_existente or kw_alvo in kw_existente or kw_existente in kw_alvo:
                    return item.name

    return None

def log_path(nome):
    return PASTA_LOGS / nome

def detectar_intencao(pergunta):
    pergunta_lower = pergunta.lower()
    if "onde" in pergunta_lower:
        return "Foque na localização"
    elif "quando" in pergunta_lower:
        return "Foque no histórico ou cronologia"
    elif "quem" in pergunta_lower:
        return "Foque na entidade ou pessoa"
    elif "como" in pergunta_lower:
        return "Foque no método ou processo"
    elif "por que" in pergunta_lower or "porque" in pergunta_lower:
        return "Foque na causa"
    return ""

def currentdate():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gerar_indice(root=None):
    if root is None:
        root = CAMINHO_PROJETO
    root = Path(root)
    indice = {}
    if not root.exists():
        return "{}"
    for pasta in root.rglob("*"):
        if pasta.is_dir():
            arquivos = [
                f.name
                for f in pasta.glob("*.md")
            ]
            relativo = str(
                pasta.relative_to(root)
            )
            if relativo == ".":
                relativo = "ROOT"
            indice[relativo] = arquivos
    return json.dumps(
        indice,
        ensure_ascii=False,
        indent=2
    )

def build_tree(root=None):
    if root is None:
        root = CAMINHO_PROJETO
    root = Path(root)
    if not root.exists():
        return "Pasta não encontrada."
    linhas = [root.name]
    def walk(path, prefix=""):
        itens = sorted(
            path.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower())
        )
        for i, item in enumerate(itens):
            ultimo = i == len(itens) - 1
            branch = "└── " if ultimo else "├── "
            linhas.append(
                prefix + branch + item.name
            )
            if item.is_dir():
                novo_prefix = (
                    prefix + "    "
                    if ultimo
                    else prefix + "│   "
                )
                walk(item, novo_prefix)
    walk(root)
    return "\n".join(linhas)

def carregar_estrutura_projeto():
    raiz = Path(CAMINHO_PROJETO)
    resultado = []
    for caminho in sorted(raiz.rglob("*")):
        relativo = caminho.relative_to(raiz)
        if caminho.is_dir():
            resultado.append(
                f"[DIR] {relativo}"
            )
        elif caminho.suffix == ".md":
            resultado.append(
                f"[FILE] {relativo}"
            )
    return "\n".join(resultado)

def carregar_projeto():
    caminho=Path(CAMINHO_PROJETO)
    if not caminho.exists():
        print(f"⚠️ Alerta: Pasta '{PASTA_PROJETO}' não encontrada.")
        return ""
    
    # Retrieve all Markdown files recursively
    all_files = list(caminho.rglob("*.md"))
    
    # Group files by parent directory and base name (ignoring version suffixes like _v1, _v2)
    groups = {}
    for f in all_files:
        base_name = re.sub(r'_v\d+$', '', f.stem)
        key = (f.parent, base_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(f)
        
    # Isolate the highest available version of each document
    latest_files = []
    for key, files in groups.items():
        def get_version(path):
            match = re.search(r'_v(\d+)$', path.stem)
            return int(match.group(1)) if match else 0
        
        files.sort(key=get_version, reverse=True)
        latest_files.append(files[0]) # Newest/expanded revision goes first

    conteudo_total = []
    for f_path in latest_files:
        try:
            with open(f_path, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
        except UnicodeDecodeError:
            try:
                with open(f_path, "r", encoding="latin1") as file_obj:
                    content = file_obj.read()
            except Exception:
                continue
        
        # Verify if the file is clean of TODO markers
        if (any(tag in content for tag in TAG_ALVO)
            or any(ignore in content for ignore in IGNORELIST)
            ):
            #print(f"Excluindo '{f_path.name}' do conhecimento por possuir tags TODO ou Rascunho ou Template.")
            continue
            
        conteudo_total.append(f"\n==== {f_path.name} ====\n{content}\n")
        
    return "\n\n".join(conteudo_total)

def request_cancellation():
    """Dispara a solicitação de parada para todas as threads em execução."""
    _CANCEL_EVENT.set()

def reset_cancellation():
    """Reseta o sinalizador antes de iniciar uma nova tarefa."""
    _CANCEL_EVENT.clear()

def is_cancelled() -> bool:
    """Verifica se o usuário pediu para interromper a execução."""
    return _CANCEL_EVENT.is_set()

def carregar_mapa_ordens():
    """Lê o arquivo central de ordenação em logs/folder_orders.json."""
    if ARQUIVO_ORDEM_GLOBAL.exists():
        try:
            with open(ARQUIVO_ORDEM_GLOBAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_ordem_pasta(caminho_pasta, lista_nomes_itens):
    """Salva a lista ordenada de uma pasta específica no JSON central da pasta logs."""
    try:
        caminho_obj = Path(caminho_pasta).resolve()
        raiz_obj = Path(CAMINHO_PROJETO).resolve()
        rel_key = str(caminho_obj.relative_to(raiz_obj))
    except ValueError:
        rel_key = "ROOT"

    if rel_key == ".":
        rel_key = "ROOT"

    mapa = carregar_mapa_ordens()
    mapa[rel_key] = lista_nomes_itens

    try:
        with open(ARQUIVO_ORDEM_GLOBAL, "w", encoding="utf-8") as f:
            json.dump(mapa, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar mapa de ordens central: {e}")

def obter_itens_ordenados(caminho_pasta):
    """Retorna a lista de itens da pasta ordenados de acordo com a preferência salva."""
    try:
        todos_itens = [i for i in os.listdir(caminho_pasta) if not i.startswith(".")]
    except Exception:
        return []

    try:
        caminho_obj = Path(caminho_pasta).resolve()
        raiz_obj = Path(CAMINHO_PROJETO).resolve()
        rel_key = str(caminho_obj.relative_to(raiz_obj))
    except ValueError:
        rel_key = "ROOT"

    if rel_key == ".":
        rel_key = "ROOT"

    mapa = carregar_mapa_ordens()

    if rel_key in mapa:
        ordem_salva = mapa[rel_key]
        
        # Itens já mapeados ficam na posição gravada; novos arquivos vão para o final
        def sort_key(nome_item):
            if nome_item in ordem_salva:
                return (0, ordem_salva.index(nome_item))
            return (1, nome_item.lower())

        return sorted(todos_itens, key=sort_key)

    # Caso não tenha ordem gravada ainda, usa ordem alfabética padrão
    return sorted(todos_itens, key=lambda x: x.lower())