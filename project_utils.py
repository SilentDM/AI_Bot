import os,re, json
from pathlib import Path
from datetime import datetime


PASTA_PHAETON = os.path.join(os.getcwd(), os.getenv("PASTA_PROJETO", "Phaeton"))

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

def currentdate():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gerar_indice(root=None):
    if root is None:
        root = os.getenv("PASTA_PROJETO", "Phaeton")
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
        root = os.getenv("PASTA_PROJETO", "Phaeton")
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

def carregar_estrutura_phaeton():
    raiz = Path(os.getenv("PASTA_PROJETO", "Phaeton"))
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

def carregar_phaeton():
    pasta_phaeton = Path(os.getcwd()) / os.getenv("PASTA_PROJETO", "Phaeton")
    if not pasta_phaeton.exists():
        print(f"⚠️ Alerta: Pasta '{pasta_phaeton}' não encontrada.")
        return ""
    
    # Retrieve all Markdown files recursively
    all_files = list(pasta_phaeton.rglob("*.md"))
    
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