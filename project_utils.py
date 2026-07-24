import os, re, json
from pathlib import Path
from datetime import datetime
import unicodedata
import difflib

PASTA_PROJETO = os.getenv("PASTA_PROJETO", "Phaeton")
CAMINHO_PROJETO = os.path.join(os.getcwd(), PASTA_PROJETO)
PASTA_ESTILO = os.getenv("PASTA_ESTILO", "Style")
CAMINHO_ESTILO = os.path.join(os.getcwd(), PASTA_ESTILO)

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

def normalizar_nome(nome: str) -> str:
    """
    Normaliza um nome de arquivo/pasta para comparação:
    - remove acentos (Ruína -> Ruina)
    - deixa tudo minúsculo
    - remove plural simples em 's' no final (aproximação simples, não é perfeita)
    - remove extensão .md, se houver
    Isso permite comparar "Segredos" com "Segredo", "Ruínas" com "Ruina", etc.
    """
    nome = Path(nome).stem  # remove extensão, se houver
    nome = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII")
    nome = nome.lower().strip()
    if nome.endswith("s") and len(nome) > 3:
        nome = nome[:-1]
    return nome

def existe_nome_parecido(nome_proposto: str, pasta_destino: Path, limiar: float = 0.85):
    """
    Verifica se já existe, na pasta_destino, algum arquivo ou subpasta com nome
    muito parecido ao nome_proposto (mesmo que não seja idêntico).
    Retorna o nome existente parecido, ou None se não encontrar nada.

    'limiar' vai de 0 a 1: quanto mais perto de 1, mais exigente é a exigência
    de parecença (0.85 já pega coisas como "Segredos" vs "Segredo").
    """
    if not pasta_destino.exists():
        return None

    alvo = normalizar_nome(nome_proposto)

    for item in pasta_destino.iterdir():
        existente = normalizar_nome(item.name)
        similaridade = difflib.SequenceMatcher(None, alvo, existente).ratio()
        if similaridade >= limiar:
            return item.name

    return None

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