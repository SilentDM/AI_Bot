import os
from pathlib import Path

if getattr(os, 'frozen', False):
    BASE_DIR = Path(os.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

ENV_PATH = (BASE_DIR / ".env").resolve()

DEFAULT_ENV_CONTENT = """AI_PROVIDER=gemini
GOOGLE_API_KEY=
PRO_API_KEY=
CLAUDE_TOKEN=
DISCORD_TOKEN=
MESTRE_DISCORD_ID=0
PASTA_PROJETO=Projeto
PASTA_ESTILO=Style
"""

def garantir_env():
    """Garante a existência do arquivo .env silenciosamente, sem exibir janela modal."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text(DEFAULT_ENV_CONTENT, encoding="utf-8")

def atualizar_env(novos_valores: dict):
    """
    Atualiza as chaves no arquivo .env e no ambiente ativo (os.environ).
    """
    garantir_env()
    
    env_dict = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str and not line_str.startswith("#") and "=" in line_str:
                    k, v = line_str.split("=", 1)
                    env_dict[k.strip()] = v.strip()

    for k, v in novos_valores.items():
        if v is not None:
            val_str = str(v).strip()
            env_dict[k] = val_str
            os.environ[k] = val_str  # Atualiza as variáveis de ambiente ativas no programa

    linhas = [f"{k}={v}" for k, v in env_dict.items()]
    ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")