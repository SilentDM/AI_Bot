import sys
from pathlib import Path

# 1. Garante que o diretório raiz do projeto está no PATH
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

if __name__ == "__main__":
    main()