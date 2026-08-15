import os, json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QGroupBox, QRadioButton, QScrollArea
)
from PySide6.QtCore import Signal
import engine.project_utils as pu
from ui.setup_env import atualizar_env

SETTINGS_FILE = pu.PASTA_LOGS / "settings.json"

SISTEMAS_RPG = {"D&D 5e": "DnD5e.md", "Tormenta20": "Tormenta20.md", "Pathfinder 2e": "Pathfinder2e.md", "Generic": "Generico.md"}
PERFIS_TOM = {
    "Dark Fantasy (Grimdark)": "# DIRETRIZ DE TOM E CLIMA: DARK FANTASY (GRIMDARK)\n- Atmosfera sombria...",
    "High Fantasy Épico": "# DIRETRIZ DE TOM E CLIMA: HIGH FANTASY ÉPICO\n- Grandioso e mágico...",
    "Mistério & Investigação": "# DIRETRIZ DE TOM E CLIMA: MISTÉRIO\n- Suspense e pistas...",
    "Cyberpunk / Sci-Fi": "# DIRETRIZ DE TOM E CLIMA: CYBERPUNK\n- Alta tecnologia...",
    "Nenhum / Neutro": "# DIRETRIZ DE TOM E CLIMA: NEUTRO\n- Descritivo básico."
}

DEFAULT_SETTINGS = {
    "auto_expander": False, "wb_allow_create_folder": True, "wb_allow_create_file": True,
    "wb_allow_improve_file": True, "tom_clima_perfil": "Dark Fantasy (Grimdark)",
    "rpg_sistema_ativo": "D&D 5e", "discord_prefix": "!ao", "discord_roles_dm": "Mestre, DM, GM",
    "discord_cooldown_seconds": 15, "ai_provider_ativo": "gemini"
}

PROVEDORES_IA = {"Gemini": "gemini", "Pro (OpenAI)": "pro", "Claude (Anthropic)": "claude"}

def carregar_configuracoes():
    config = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config

def salvar_configuracoes(config):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

class OptionsWidget(QWidget):
    signal_toast = Signal(str)
    signal_log = Signal(str)

    def __init__(self, parent, log_cb, toast_cb):
        super().__init__(parent)
        self.log_callback = log_cb
        self.toast_callback = toast_cb

        if self.log_callback:
            self.signal_log.connect(self.log_callback)
        if self.toast_callback:
            self.signal_toast.connect(self.toast_callback)

        self.settings = carregar_configuracoes()

        main_layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        self.grid = QGridLayout(container)

        # 1. Credenciais
        box_cred = QGroupBox(" Credenciais de API e Discord (.env) ")
        l_cred = QVBoxLayout(box_cred)

        l_cred.addWidget(QLabel("Provedor de IA Ativo:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(list(PROVEDORES_IA.keys()))
        l_cred.addWidget(self.combo_provider)

        l_cred.addWidget(QLabel("Gemini API Key:"))
        self.txt_gemini = QLineEdit()
        self.txt_gemini.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_gemini)

        l_cred.addWidget(QLabel("Claude Token:"))
        self.txt_claude = QLineEdit()
        self.txt_claude.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_claude)

        l_cred.addWidget(QLabel("OpenAI Key:"))
        self.txt_openai = QLineEdit()
        self.txt_openai.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_openai)

        l_cred.addWidget(QLabel("Token Discord:"))
        self.txt_discord = QLineEdit()
        self.txt_discord.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_discord)

        btn_salvar_env = QPushButton("Salvar Credenciais no .env")
        btn_salvar_env.clicked.connect(self.salvar_env)
        l_cred.addWidget(btn_salvar_env)

        # 2. Discord
        box_disc = QGroupBox(" Bot do Discord ")
        l_disc = QVBoxLayout(box_disc)
        l_disc.addWidget(QLabel("Prefixo:"))
        self.txt_prefix = QLineEdit(self.settings.get("discord_prefix", "!ao"))
        l_disc.addWidget(self.txt_prefix)
        l_disc.addWidget(QLabel("Cargos de Mestre:"))
        self.txt_roles = QLineEdit(self.settings.get("discord_roles_dm", "Mestre, DM"))
        l_disc.addWidget(self.txt_roles)

        # 3. Tom e Clima
        box_tom = QGroupBox(" Tom e Clima ")
        l_tom = QVBoxLayout(box_tom)
        self.combo_tom = QComboBox()
        self.combo_tom.addItems(list(PERFIS_TOM.keys()))
        l_tom.addWidget(self.combo_tom)

        self.grid.addWidget(box_cred, 0, 0)
        self.grid.addWidget(box_disc, 0, 1)
        self.grid.addWidget(box_tom, 1, 0)

    def salvar_env(self):
        novos = {}
        if self.txt_gemini.text(): novos["GOOGLE_API_KEY"] = self.txt_gemini.text().strip()
        if self.txt_claude.text(): novos["CLAUDE_TOKEN"] = self.txt_claude.text().strip()
        if self.txt_openai.text(): novos["PRO_API_KEY"] = self.txt_openai.text().strip()
        if self.txt_discord.text(): novos["DISCORD_TOKEN"] = self.txt_discord.text().strip()
        
        atualizar_env(novos)
        self.signal_toast.emit("💾 Credenciais atualizadas!")

    def is_auto_expander_enabled(self):
        return bool(self.settings.get("auto_expander", False))