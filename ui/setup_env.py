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
    """Garante a existência do arquivo .env silenciosamente."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text(DEFAULT_ENV_CONTENT, encoding="utf-8")

def garantir_icones_svg():
    """Garante a criação dos 4 arquivos SVG das setas das pastas."""
    pasta_styles = (BASE_DIR / "ui" / "styles").resolve()
    pasta_styles.mkdir(parents=True, exist_ok=True)

    icones = {
        "arrow_right.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#aaaaaa" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>""",
        "arrow_right_hover.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>""",
        "arrow_down.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#aaaaaa" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>""",
        "arrow_down_hover.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>"""
    }

    for nome_arq, conteudo in icones.items():
        caminho_arq = pasta_styles / nome_arq
        if not caminho_arq.exists():
            caminho_arq.write_text(conteudo, encoding="utf-8")

def atualizar_env(novos_valores: dict):
    """Atualiza as chaves no arquivo .env e no ambiente ativo."""
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
            os.environ[k] = val_str

    linhas = [f"{k}={v}" for k, v in env_dict.items()]
    ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")