import sys, os, traceback
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


def bootstrap():
    """
    Ponto único de verificação e criação de todo o ecossistema de pastas e arquivos.
    Roda ANTES de carregar a interface gráfica ou qualquer outro módulo.
    """
    print("Iniciando Silent Multiverse Console...")
    print(f"Diretório Raiz: {BASE_DIR}")

    # A. Garante o arquivo .env na mesma pasta do main.py
    from ui.setup_env import garantir_env
    garantir_env()

    # B. Carrega o .env explicitamente da raiz
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    load_dotenv(env_path)

    # C. Obtém nomes das pastas dinâmicas do .env (com valores padrão)
    nome_projeto = os.getenv("PASTA_PROJETO", "Phaeton").strip() or "Phaeton"
    nome_estilo = os.getenv("PASTA_ESTILO", "Style").strip() or "Style"

    # D. Dicionário de todas as pastas que OBRIGATORIAMENTE devem existir
    pastas_obrigatorias = {
        "Logs": BASE_DIR / "logs",
        "Memories": BASE_DIR / "memories",
        "Exports": BASE_DIR / "exports",
        "Templates": BASE_DIR / "Templates",
        "Style": BASE_DIR / nome_estilo,
        "Projeto": BASE_DIR / nome_projeto
    }

    # E. Verifica e cria cada pasta
    for nome, caminho in pastas_obrigatorias.items():
        if not caminho.exists():
            caminho.mkdir(parents=True, exist_ok=True)
            print(f"  └─ 📁 Pasta criada: {nome} -> {caminho.name}")
        else:
            print(f"  └─ ✅ Pasta verificada: {nome} -> {caminho.name}")

    print("Pastas e configurações foram verificadas com sucesso!")


def main():
    # 1. Registra hook de crash global
    sys.excepthook = capturar_erros_fatais

    # 2. Prepara o ambiente e pastas
    bootstrap()

    # 3. Carrega e inicia a interface gráfica
    from ui.gui import main as start_gui
    start_gui()


if __name__ == "__main__":
    main()