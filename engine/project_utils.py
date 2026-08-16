import sys, os, re, json, threading, unicodedata, difflib, zipfile, shutil, subprocess, ctypes
import core.secret_filter as sf
from pathlib import Path
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_LOGS = (BASE_DIR / "logs").resolve()
PASTA_MEMORIES = (BASE_DIR / "memories").resolve()
PASTA_EXPORTS = (BASE_DIR / "exports").resolve()
PASTA_TEMPLATES = (BASE_DIR / "Templates").resolve()
PASTA_LOCALE = (BASE_DIR / "Locale").resolve()
PASTA_ESTILO = os.getenv("PASTA_ESTILO", "Style")
CAMINHO_ESTILO = (BASE_DIR / PASTA_ESTILO).resolve()
PROJECT_ROOT = BASE_DIR

CAMINHO_PROJETO = None
PASTA_PROJETO = None

TAG_ALVO = ["<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo","<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do","<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", "<-- To-do", "<-- Todo:"]
IGNORELIST = ["Templates", "status: rascunho", ".obsidian", ".git", ".trash"]

_CANCEL_EVENT = threading.Event()
STOP_WORDS = {"de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "o", "a", "os", "as", "e", "the", "of", "and", "in", "on", "para", "com"}

ARQUIVO_ORDEM_GLOBAL = PASTA_LOGS / "folder_orders.json"

LOCK_MODELS = threading.Lock()
LOCK_CHANGELOG = threading.Lock()
LOCK_FOLDER_ORDERS = threading.Lock()

# --- MOTOR DE INTERNACIONALIZAÇÃO (i18n) ---
_DADOS_TRADUCAO = {}
_IDIOMA_ATUAL = "pt_br"

# --- MOTOR DE INTERNACIONALIZAÇÃO (i18n) SIMPLIFICADO ---
_DADOS_TRADUCAO = {}
_IDIOMA_ATUAL = "pt_br"

def garantir_arquivos_locale():
    """Garante unicamente a existência da pasta Locale e arquivos .json básicos."""
    PASTA_LOCALE.mkdir(parents=True, exist_ok=True)
    p_pt = PASTA_LOCALE / "pt_br.json"
    p_en = PASTA_LOCALE / "en_us.json"

    if not p_pt.exists():
        with open(p_pt, "w", encoding="utf-8") as f:
            f.write("{}\n")

    if not p_en.exists():
        with open(p_en, "w", encoding="utf-8") as f:
            f.write("{}\n")

def obter_idiomas_disponiveis() -> list[str]:
    """Varre a pasta Locale e retorna a lista de arquivos .json existentes."""
    garantir_arquivos_locale()
    idiomas = [arq.stem for arq in PASTA_LOCALE.glob("*.json")]
    return sorted(idiomas) if idiomas else ["pt_br", "en_us"]

def carregar_idioma(codigo_idioma: str = None):
    """Carrega o arquivo .json ativo direto da pasta Locale."""
    global _DADOS_TRADUCAO, _IDIOMA_ATUAL
    garantir_arquivos_locale()

    if not codigo_idioma:
        config = ler_json_seguro(PASTA_LOGS / "settings.json", LOCK_MODELS, padrao={})
        codigo_idioma = config.get("idioma_ativo", "pt_br")

    _IDIOMA_ATUAL = codigo_idioma.lower().strip().replace("-", "_")

    caminho_json = None
    if PASTA_LOCALE.exists():
        for arq in PASTA_LOCALE.glob("*.json"):
            if arq.stem.lower().strip().replace("-", "_") == _IDIOMA_ATUAL:
                caminho_json = arq
                break

    if not caminho_json:
        caminho_json = PASTA_LOCALE / f"{_IDIOMA_ATUAL}.json"

    if caminho_json and caminho_json.exists():
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                _DADOS_TRADUCAO = json.load(f)
        except Exception as e:
            print(f"Erro ao carregar tradução {caminho_json}: {e}")
            _DADOS_TRADUCAO = {}
    else:
        _DADOS_TRADUCAO = {}

def tr(chave: str, padrao: str = "") -> str:
    """Busca a tradução da chave no JSON ativo. Retorna 'padrao' se não encontrar."""
    if not _DADOS_TRADUCAO:
        carregar_idioma()

    if not _DADOS_TRADUCAO:
        return padrao or chave

    # 1. Busca por Chave Plana (ex: "nav.editor")
    if chave in _DADOS_TRADUCAO:
        val = _DADOS_TRADUCAO[chave]
        if val is not None and str(val).strip():
            return str(val)

    # 2. Busca por Chave Aninhada (ex: _DADOS_TRADUCAO["nav"]["editor"])
    partes = chave.split(".")
    no_atual = _DADOS_TRADUCAO
    encontrado = True
    for p in partes:
        if isinstance(no_atual, dict) and p in no_atual:
            no_atual = no_atual[p]
        else:
            encontrado = False
            break

    if encontrado and no_atual is not None and not isinstance(no_atual, dict):
        return str(no_atual)

    return padrao or chave

def ler_json_seguro(caminho: Path, lock: threading.Lock, padrao=None):
    if padrao is None: padrao = {}
    with lock:
        if not caminho.exists(): return padrao
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao ler JSON {caminho.name}: {e}")
            return padrao

# Inicialização automática de idioma
carregar_idioma()

def obter_projetos_recentes():
    arquivo_settings = PASTA_LOGS / "settings.json"
    if arquivo_settings.exists():
        try:
            with open(arquivo_settings, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados.get("projetos_recentes", [])
        except Exception:
            pass
    return []

def definir_projeto_ativo(caminho_bruto):
    global CAMINHO_PROJETO, PASTA_PROJETO
    caminho_obj = Path(caminho_bruto).resolve()
    caminho_obj.mkdir(parents=True, exist_ok=True)
    
    CAMINHO_PROJETO = caminho_obj
    PASTA_PROJETO = caminho_obj.name

    arquivo_settings = PASTA_LOGS / "settings.json"
    dados = {}
    if arquivo_settings.exists():
        try:
            with open(arquivo_settings, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except Exception:
            pass

    dados["caminho_projeto_ativo"] = str(caminho_obj)
    recentes = dados.get("projetos_recentes", [])
    str_caminho = str(caminho_obj)
    if str_caminho in recentes:
        recentes.remove(str_caminho)
    recentes.insert(0, str_caminho)
    dados["projetos_recentes"] = recentes[:10]

    try:
        with open(arquivo_settings, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar projeto ativo: {e}")

    print(f"🌍 Projeto Ativo configurado para: {CAMINHO_PROJETO}")
    return CAMINHO_PROJETO

arquivo_settings = PASTA_LOGS / "settings.json"
caminho_inicial = None
if arquivo_settings.exists():
    try:
        with open(arquivo_settings, "r", encoding="utf-8") as f:
            caminho_inicial = json.load(f).get("caminho_projeto_ativo")
    except Exception:
        pass

if not caminho_inicial:
    caminho_inicial = os.getenv("PASTA_PROJETO", "Projeto")
    if not os.path.isabs(caminho_inicial):
        caminho_inicial = BASE_DIR / caminho_inicial

definir_projeto_ativo(caminho_inicial)



def salvar_json_seguro(caminho: Path, dados, lock: threading.Lock, indent=4):
    with lock:
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho_tmp = caminho.with_suffix(".tmp")
            with open(caminho_tmp, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=indent)
            caminho_tmp.replace(caminho)
        except Exception as e:
            print(f"❌ Erro ao salvar JSON {caminho.name}: {e}")

def anexar_jsonl_seguro(caminho: Path, registro: dict, lock: threading.Lock):
    with lock:
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            linha = json.dumps(registro, ensure_ascii=False) + "\n"
            with open(caminho, "a", encoding="utf-8") as f:
                f.write(linha)
        except Exception as e:
            print(f"❌ Erro ao anexar em {caminho.name}: {e}")

def obter_caminho_base():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

ROOT_EMBUTIDO = obter_caminho_base()

def normalizar_nome(nome: str) -> str:
    nome = Path(nome).stem
    nome = re.sub(r'_v\d+$', '', nome, flags=re.IGNORECASE)
    nome = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII")
    nome = nome.lower().strip()
    nome = re.sub(r'[_\-+.]', ' ', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

def extrair_palavras_chave(nome: str):
    norm = normalizar_nome(nome)
    palavras = norm.split()
    palavras_relevantes = []
    for p in palavras:
        if len(p) > 2 and p not in STOP_WORDS:
            if p.endswith('s') and len(p) > 3:
                p = p[:-1]
            palavras_relevantes.append(p)
    return norm, palavras_relevantes

def existe_nome_parecido(nome_proposto: str, pasta_destino: Path, limiar: float = 0.65):
    if not pasta_destino.exists(): return None
    alvo_norm, alvo_kw = extrair_palavras_chave(nome_proposto)

    for item in pasta_destino.iterdir():
        existente_norm, existente_kw = extrair_palavras_chave(item.name)
        similaridade = difflib.SequenceMatcher(None, alvo_norm, existente_norm).ratio()
        if similaridade >= limiar: return item.name
        if len(existente_norm) >= 3 and len(alvo_norm) >= 3:
            if existente_norm in alvo_norm or alvo_norm in existente_norm: return item.name
        for kw_alvo in alvo_kw:
            for kw_existente in existente_kw:
                if kw_alvo == kw_existente or kw_alvo in kw_existente or kw_existente in kw_alvo:
                    return item.name
    return None

def log_path(nome):
    return PASTA_LOGS / nome

def detectar_intencao(pergunta):
    pergunta_lower = pergunta.lower()
    if "onde" in pergunta_lower: return "Foque na localização"
    elif "quando" in pergunta_lower: return "Foque no histórico ou cronologia"
    elif "quem" in pergunta_lower: return "Foque na entidade ou pessoa"
    elif "como" in pergunta_lower: return "Foque no método ou processo"
    elif "por que" in pergunta_lower or "porque" in pergunta_lower: return "Foque na causa"
    return ""

def currentdate():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gerar_indice(root=None):
    if root is None: root = CAMINHO_PROJETO
    root = Path(root)
    indice = {}
    if not root.exists(): return "{}"
    for pasta in root.rglob("*"):
        if pasta.is_dir():
            arquivos = [f.name for f in pasta.glob("*.md")]
            relativo = str(pasta.relative_to(root))
            if relativo == ".": relativo = "ROOT"
            indice[relativo] = arquivos
    return json.dumps(indice, ensure_ascii=False, indent=2)

def build_tree(root=None):
    if root is None: root = CAMINHO_PROJETO
    root = Path(root)
    if not root.exists(): return "Pasta não encontrada."
    linhas = [root.name]
    def walk(path, prefix=""):
        itens = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for i, item in enumerate(itens):
            ultimo = i == len(itens) - 1
            branch = "└── " if ultimo else "├── "
            linhas.append(prefix + branch + item.name)
            if item.is_dir():
                novo_prefix = prefix + "    " if ultimo else prefix + "│   "
                walk(item, novo_prefix)
    walk(root)
    return "\n".join(linhas)

def carregar_estrutura_projeto():
    raiz = Path(CAMINHO_PROJETO)
    resultado = []
    for caminho in sorted(raiz.rglob("*")):
        relativo = caminho.relative_to(raiz)
        if caminho.is_dir(): resultado.append(f"[DIR] {relativo}")
        elif caminho.suffix == ".md": resultado.append(f"[FILE] {relativo}")
    return "\n".join(resultado)

def carregar_projeto(is_dm: bool = True):
    caminho = Path(CAMINHO_PROJETO)
    if not caminho.exists(): return ""
    
    all_files = list(caminho.rglob("*.md"))
    groups = {}
    for f in all_files:
        base_name = re.sub(r'_v\d+$', '', f.stem)
        key = (f.parent, base_name)
        if key not in groups: groups[key] = []
        groups[key].append(f)
        
    latest_files = []
    for key, files in groups.items():
        def get_version(path):
            match = re.search(r'_v(\d+)$', path.stem)
            return int(match.group(1)) if match else 0
        files.sort(key=get_version, reverse=True)
        latest_files.append(files[0])

    conteudo_total = []
    for f_path in latest_files:
        try:
            with open(f_path, "r", encoding="utf-8") as file_obj: content = file_obj.read()
        except UnicodeDecodeError:
            try:
                with open(f_path, "r", encoding="latin1") as file_obj: content = file_obj.read()
            except Exception: continue
        
        if (any(tag in content for tag in TAG_ALVO) or any(ignore in content for ignore in IGNORELIST)):
            continue
        content_filtrado = sf.filtrar_conteudo_por_permissao(content, is_dm=is_dm)
        if not content_filtrado: continue            
        conteudo_total.append(f"\n==== {f_path.name} ====\n{content_filtrado}\n")
        
    return "\n\n".join(conteudo_total)

def request_cancellation(): _CANCEL_EVENT.set()
def reset_cancellation(): _CANCEL_EVENT.clear()
def is_cancelled() -> bool: return _CANCEL_EVENT.is_set()

def carregar_mapa_ordens(): return ler_json_seguro(ARQUIVO_ORDEM_GLOBAL, LOCK_FOLDER_ORDERS, padrao={})

def salvar_ordem_pasta(caminho_pasta, lista_nomes_itens):
    try:
        caminho_obj = Path(caminho_pasta).resolve()
        raiz_obj = Path(CAMINHO_PROJETO).resolve()
        rel_key = str(caminho_obj.relative_to(raiz_obj))
    except ValueError: rel_key = "ROOT"
    if rel_key == ".": rel_key = "ROOT"
        
    chave_projeto = f"{PASTA_PROJETO}::{rel_key}"
    mapa = carregar_mapa_ordens()
    mapa[chave_projeto] = lista_nomes_itens
    salvar_json_seguro(ARQUIVO_ORDEM_GLOBAL, mapa, LOCK_FOLDER_ORDERS, indent=2)

def obter_itens_ordenados(caminho_pasta):
    try: todos_itens = [i for i in os.listdir(caminho_pasta) if not i.startswith(".")]
    except Exception: return []

    try:
        caminho_obj = Path(caminho_pasta).resolve()
        raiz_obj = Path(CAMINHO_PROJETO).resolve()
        rel_key = str(caminho_obj.relative_to(raiz_obj))
    except ValueError: rel_key = "ROOT"

    if rel_key == ".": rel_key = "ROOT"
    chave_projeto = f"{PASTA_PROJETO}::{rel_key}"
    mapa = carregar_mapa_ordens()

    if chave_projeto in mapa:
        ordem_salva = mapa[chave_projeto]
        def sort_key(nome_item):
            if nome_item in ordem_salva: return (0, ordem_salva.index(nome_item))
            return (1, nome_item.lower())
        return sorted(todos_itens, key=sort_key)

    return sorted(todos_itens, key=lambda x: x.lower())

def criar_backup_projeto():
    pastas_para_backup = [
        ("exports", PASTA_EXPORTS), ("logs", PASTA_LOGS), ("memories", PASTA_MEMORIES),
        ("Templates", PASTA_TEMPLATES), ("Locale", PASTA_LOCALE),
        (PASTA_ESTILO, CAMINHO_ESTILO), (PASTA_PROJETO, CAMINHO_PROJETO),
    ]

    data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_zip = f"backup_{PASTA_PROJETO}_{data_str}.zip"
    raiz_volume = Path(BASE_DIR.anchor)
    caminho_destino = raiz_volume / nome_zip

    try:
        teste_perm = raiz_volume / f".test_perm_{data_str}"
        teste_perm.touch()
        teste_perm.unlink()
    except (PermissionError, OSError):
        caminho_destino = BASE_DIR / nome_zip

    total_arquivos = 0
    with zipfile.ZipFile(caminho_destino, "w", zipfile.ZIP_DEFLATED) as zipf:
        for nome_pasta_rel, pasta_path in pastas_para_backup:
            if pasta_path.exists() and pasta_path.is_dir():
                for arq in pasta_path.rglob("*"):
                    if arq.is_file():
                        if arq.name.startswith("backup_") and arq.suffix == ".zip": continue
                        rel_path = Path(nome_pasta_rel) / arq.relative_to(pasta_path)
                        zipf.write(arq, arcname=rel_path)
                        total_arquivos += 1

    return caminho_destino, total_arquivos

def encontrar_arquivo_por_wikilink(nome_alvo: str) -> Path | None:
    alvo_norm = normalizar_nome(nome_alvo)
    raiz = Path(CAMINHO_PROJETO)
    candidatos = []
    for arq in raiz.rglob("*.md"):
        if any(part in IGNORELIST for part in arq.parts): continue
        if normalizar_nome(arq.stem) == alvo_norm: candidatos.append(arq.resolve())

    if not candidatos: return None
    def get_version(path_obj):
        match = re.search(r'_v(\d+)$', path_obj.stem, flags=re.IGNORECASE)
        return int(match.group(1)) if match else 0

    candidatos.sort(key=get_version, reverse=True)
    return candidatos[0]

def criar_documento_wikilink(nome_alvo: str, pasta_destino: str, nome_origem: str) -> Path:
    nome_md = nome_alvo if nome_alvo.lower().endswith(".md") else f"{nome_alvo}.md"
    novo_caminho = os.path.join(pasta_destino, nome_md)
    titulo = nome_alvo.replace('.md', '').replace('_', ' ').title()
    conteudo_inicial = f"# {titulo}\n\nDocumento criado a partir de wikilink em [[{nome_origem}]]."
    with open(novo_caminho, "w", encoding="utf-8") as f: f.write(conteudo_inicial)
    return Path(novo_caminho)

def filtrar_caminhos_busca(query: str) -> set[str]:
    query = query.strip().lower()
    if not query: return set()
    matching_paths = set()
    for arq in Path(CAMINHO_PROJETO).rglob("*.md"):
        if any(part in IGNORELIST for part in arq.parts): continue
        try:
            with open(arq, "r", encoding="utf-8", errors="ignore") as f: content = f.read().lower()
            if query in arq.name.lower() or query in content:
                p = arq.resolve()
                matching_paths.add(str(p))
                for parent in p.parents: matching_paths.add(str(parent))
        except Exception: pass
    return matching_paths

def calcular_estatisticas_texto(texto: str) -> tuple[int, int, int, int]:
    if not texto: return 0, 0, 0, 0
    palavras = len(texto.split())
    caracteres = len(texto.replace("\n", ""))
    linhas = len(texto.splitlines())
    tokens = int(palavras / 4)
    return palavras, caracteres, linhas, tokens

def otimizar_memoria_ram():
    if sys.platform == 'win32':
        try:
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.EmptyWorkingSet(handle)
        except Exception as e: print(f"Erro ao otimizar RAM: {e}")

def criar_novo_arquivo(parent_dir: str, nome: str, template_escolhido: str, obter_template_func) -> tuple[bool, str, Path | None]:
    if not nome.lower().endswith(".md"): nome += ".md"
    caminho_arquivo = os.path.join(parent_dir, nome)
    if os.path.exists(caminho_arquivo): return False, "Um arquivo com esse nome já existe.", None

    try:
        titulo = nome.replace('.md', '').replace('_', ' ').title()
        conteudo_template = obter_template_func(template_escolhido)
        conteudo_final = f"# {titulo}\nstatus: rascunho\n---\n<-- TODO: Preencha usando o template.\n{conteudo_template}" if conteudo_template else f"# {titulo}\n\n<-- TODO: Crie informações para {titulo}."
        with open(caminho_arquivo, "w", encoding="utf-8") as f: f.write(conteudo_final)
        return True, "Arquivo criado com sucesso!", Path(caminho_arquivo)
    except Exception as e: return False, f"Falha ao criar arquivo: {e}", None

def criar_nova_pasta(parent_dir: str, nome: str) -> tuple[bool, str, Path | None]:
    caminho_pasta = os.path.join(parent_dir, nome)
    if os.path.exists(caminho_pasta): return False, "Já existe uma pasta com esse nome.", None
    try:
        os.makedirs(caminho_pasta, exist_ok=True)
        return True, f"Pasta '{nome}' criada!", Path(caminho_pasta)
    except Exception as e: return False, f"Falha ao criar pasta: {e}", None

def renomear_item_projeto(caminho: str, novo_nome: str) -> tuple[bool, str, Path | None]:
    diretorio_pai = os.path.dirname(caminho)
    nome_antigo = os.path.basename(caminho)
    novo_nome = novo_nome.strip()
    if os.path.isfile(caminho) and not novo_nome.lower().endswith(".md"): novo_nome += ".md"
    if novo_nome == nome_antigo: return False, "O novo nome é idêntico.", None

    novo_caminho = os.path.join(diretorio_pai, novo_nome)
    if os.path.exists(novo_caminho): return False, "Já existe um item com esse nome.", None
    try:
        os.rename(caminho, novo_caminho)
        return True, f"Renomeado: '{nome_antigo}' -> '{novo_nome}'", Path(novo_caminho)
    except Exception as e: return False, f"Falha ao renomear: {e}", None

def deletar_item_projeto(caminho: str) -> tuple[bool, str]:
    nome = os.path.basename(caminho)
    try:
        if os.path.isdir(caminho): shutil.rmtree(caminho)
        else: os.remove(caminho)
        return True, f"Deletado: '{nome}'"
    except Exception as e: return False, f"Falha ao deletar: {e}"

def duplicar_item_projeto(caminho: str) -> tuple[bool, str, Path | None]:
    try:
        diretorio = os.path.dirname(caminho)
        nome, ext = os.path.splitext(os.path.basename(caminho))
        novo_nome = f"{nome}_copia{ext}"
        novo_caminho = os.path.join(diretorio, novo_nome)

        counter = 1
        while os.path.exists(novo_caminho):
            novo_nome = f"{nome}_copia_{counter}{ext}"
            novo_caminho = os.path.join(diretorio, novo_nome)
            counter += 1

        if os.path.isdir(caminho): shutil.copytree(caminho, novo_caminho)
        else: shutil.copy2(caminho, novo_caminho)
        return True, f"Duplicado: '{os.path.basename(novo_caminho)}'", Path(novo_caminho)
    except Exception as e: return False, f"Falha ao duplicar: {e}", None

def colar_item_clipboard(src_path: str, target_path: str, mode: str) -> tuple[bool, str, Path | None]:
    if not src_path or not os.path.exists(src_path): return False, "Item inválido.", None
    dest_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
    base_name = os.path.basename(src_path)
    dest = os.path.join(dest_dir, base_name)
    if os.path.abspath(src_path) == os.path.abspath(dest): return False, "Origem e destino iguais.", None

    try:
        if mode == "cut":
            shutil.move(src_path, dest)
            msg = f"✂️ Recortado e colado '{base_name}'"
        else:
            if os.path.isdir(src_path): shutil.copytree(src_path, dest, dirs_exist_ok=True)
            else: shutil.copy2(src_path, dest)
            msg = f"📋 Colado '{base_name}'"
        return True, msg, Path(dest)
    except Exception as e: return False, f"Falha ao colar: {e}", None

def abrir_no_explorador_nativo(caminho: str):
    caminho = os.path.normpath(caminho)
    if os.name == 'nt':
        if os.path.isfile(caminho): subprocess.run(['explorer', '/select,', caminho])
        else: os.startfile(caminho)
    elif sys.platform == 'darwin': subprocess.call(['open', '-R' if os.path.isfile(caminho) else '', caminho])
    else:
        pasta = os.path.dirname(caminho) if os.path.isfile(caminho) else caminho
        subprocess.call(['xdg-open', pasta])

def formatar_historico_chat(memorias: str) -> list[tuple[str, str]]:
    if not memorias or not memorias.strip(): return []
    blocos = re.split(r'(Prompt Usuário:|Resposta:|Resumo de Memórias:)', memorias)
    resultado = []
    for i in range(1, len(blocos), 2):
        header = blocos[i].strip()
        content = blocos[i + 1].strip() if i + 1 < len(blocos) else ""
        if not content: continue
        if header == "Prompt Usuário:": resultado.append(("You", content))
        elif header == "Resposta:": resultado.append(("Ao", content))
        elif header == "Resumo de Memórias:": resultado.append(("System", f"[Resumo de Diálogos Anteriores]: {content}"))
    return resultado

def preparar_prompt_conversa_ao(prompt: str, user_name: str, memorias: str, arquivo_anexo: dict = None) -> tuple[str, str]:
    persona = "- Você é um mestre de mesa chamado Ao, focado em aventuras de D&D.\n- Você cria situações engajantes."
    regras = "- Não faça julgamentos de valor;\n- Não altere informações já definidas;\n"
    system_instruction = f"{persona}\n\n{regras}"
    conteudo_prompt = ""
    if arquivo_anexo: conteudo_prompt += f"--- ARQUIVO ANEXADO ({arquivo_anexo['name']}) ---\n{arquivo_anexo['content']}\n\n"
    if memorias: conteudo_prompt += f"--- HISTÓRICO RECENTE ---\n{memorias}\n\n"
    conteudo_prompt += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"
    return system_instruction, conteudo_prompt

def obter_prompts_auditoria_lore() -> tuple[str, str]:
    system_instruction = "Você é um Auditor de Lore de RPG. Identifique incoerências, contradições e furos de roteiro."
    prompt_auditoria = f"Realize uma auditoria rigorosa no projeto de lore {PASTA_PROJETO}."
    return system_instruction, prompt_auditoria

def formatar_markdown_para_chat_html(texto: str) -> str:
    if not texto: return ""
    html = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r'&lt;--\s*(TODO|TO DO|To Do|To-Do|todo):?\s*(.*?)--&gt;', r'<span style="color:#f97316; background:#2a1205; font-weight:bold; padding: 2px 4px; border-radius: 3px;">&lt;-- TODO: \2</span>', html, flags=re.IGNORECASE)
    html = re.sub(r'^###\s+(.*)$', r'<h3 style="color:#60a5fa; margin: 6px 0 2px 0;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^##\s+(.*)$', r'<h2 style="color:#34d399; margin: 8px 0 2px 0;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s+(.*)$', r'<h1 style="color:#10b981; margin: 10px 0 4px 0;">\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^&gt;\s+(.*)$', r'<div style="color:#94a3b8; font-style:italic; border-left: 3px solid #10b981; padding-left: 8px; margin: 4px 0;">\1</div>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color:#ffffff;">\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    html = re.sub(r'\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]', r'<span style="color:#38bdf8; font-weight:bold; text-decoration:underline;">[[\1]]</span>', html)
    html = html.replace("\n", "<br>")
    return html