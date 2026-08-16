import sys, shutil, traceback, ctypes
from pathlib import Path
from datetime import datetime


# ----------------------------------------------------------------------
# 1. DETERMINA A PASTA RAIZ DO PROJETO (ONDE O MAIN.PY / EXE ESTÁ)
# ----------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # Se compilado como .exe pelo PyInstaller
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # Se rodando como script .py
    BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    myappid = "silent.multiverse.nexus.v1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

def capturar_erros_fatais(exc_type, exc_value, exc_traceback):
    """Salva qualquer travamento não tratado em um arquivo crash_log.txt no logs/."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    pasta_logs = BASE_DIR / "logs"
    pasta_logs.mkdir(exist_ok=True, parents=True)
    caminho_crash = pasta_logs / "crash_log.txt"
    
    with open(caminho_crash, "a", encoding="utf-8") as f:
        f.write(f"\n==================== CRASH EM {datetime.now()} ====================\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    
    print(f"❌ Ocorreu um erro fatal! Log salvo em: {caminho_crash}")

def configurar_ambiente():
    """Garante o .env e carrega variáveis."""
    from ui.setup_env import garantir_env, garantir_icones_svg
    garantir_env()
    garantir_icones_svg()
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

def criar_pastas():
    """Cria todas as pastas necessárias para o funcionamento do app."""
    import engine.project_utils as pu
    import os
    nome_estilo = os.getenv("PASTA_ESTILO", "Style").strip() or "Style"
    pu.CAMINHO_PROJETO.mkdir(parents=True, exist_ok=True)
    pastas_obrigatorias = {
        "Logs": BASE_DIR / "logs",
        "Memories": BASE_DIR / "memories",
        "Exports": BASE_DIR / "exports",
        "Templates": BASE_DIR / "Templates",
        "Style": BASE_DIR / nome_estilo,
        "Projeto Ativo": pu.CAMINHO_PROJETO
    }

    for nome, caminho in pastas_obrigatorias.items():
        caminho.mkdir(parents=True, exist_ok=True)
        print(f"  └─ ✅ {nome}: {caminho}")
    if getattr(sys, 'frozen', False):
        meipass_templates = Path(getattr(sys, '_MEIPASS', '')) / "Templates"
        target_templates = BASE_DIR / "Templates"
        if meipass_templates.exists() and meipass_templates.is_dir():
            for src_file in meipass_templates.rglob("*"):
                if src_file.is_file():
                    rel = src_file.relative_to(meipass_templates)
                    dest = target_templates / rel
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dest)
    print("Pastas e configurações foram verificadas com sucesso!")

def main():
    sys.excepthook = capturar_erros_fatais
    configurar_ambiente()
    criar_pastas()
    from ui.gui import main as start_gui
    start_gui()

if __name__ == "__main__":
    main()
