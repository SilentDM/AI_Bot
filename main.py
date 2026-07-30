import sys, traceback
from pathlib import Path
from datetime import datetime
import engine.project_utils as pu

# 1. Garante que o diretório raiz do projeto está no PATH
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
def capturar_erros_fatais(exc_type, exc_value, exc_traceback):
    """Salva qualquer travamento não tratado em um arquivo crash_log.txt antes de fechar."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    caminho_crash = pu.PASTA_LOGS / "crash_log.txt"
    with open(caminho_crash, "a", encoding="utf-8") as f:
        f.write(f"\n==================== CRASH EM {datetime.now()} ====================\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    
    print(f"❌ Ocorreu um erro fatal! Log salvo em: {caminho_crash}")

# Registra o hook global de erro



def bootstrap():
    """Prepara todo o ambiente do sistema antes de carregar a interface."""
    print("Iniciando Silent Multiverse Console...")

    # A. Verifica e garante o arquivo .env (roda o Wizard se não existir)
    from ui.setup_env import garantir_env
    garantir_env()

    # B. Carrega as variáveis de ambiente agora que o .env está garantido
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    # C. Garante diretórios essenciais (logs, pasta do projeto, etc.)
    import engine.project_utils as pu
    pu.PASTA_LOGS.mkdir(exist_ok=True, parents=True)
    
    caminho_projeto = Path(pu.CAMINHO_PROJETO)
    if not caminho_projeto.exists():
        caminho_projeto.mkdir(parents=True, exist_ok=True)
        print(f"Pasta do projeto criada: {caminho_projeto}")

    print("Ambiente verificado com sucesso!")

def main():
    # 1. Executa a preparação do sistema
    bootstrap()

    # 2. Importa e inicia a interface gráfica SOMENTE APÓS o bootstrap
    from ui.gui import main as start_gui
    start_gui()
sys.excepthook = capturar_erros_fatais
if __name__ == "__main__":
    main()