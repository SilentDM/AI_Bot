import json, os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QGroupBox, QCheckBox, QRadioButton, QScrollArea
)
from PySide6.QtCore import Signal
import engine.project_utils as pu
from ui.setup_env import atualizar_env

SETTINGS_FILE = pu.PASTA_LOGS / "settings.json"

SISTEMAS_RPG = {
    "D&D 5e": "DnD5e.md",
    "Tormenta20": "Tormenta20.md",
    "Pathfinder 2e": "Pathfinder2e.md",
    "Generic / Regras Livres": "Generico.md"
}

PERFIS_TOM = {
    "Dark Fantasy (Grimdark)": "# DIRETRIZ DE TOM: DARK FANTASY (GRIMDARK)\n- Atmosfera sombria...",
    "High Fantasy Épico": "# DIRETRIZ DE TOM: HIGH FANTASY ÉPICO\n- Grandioso e mágico...",
    "Mistério & Investigação": "# DIRETRIZ DE TOM: MISTÉRIO\n- Suspense...",
    "Cyberpunk / Sci-Fi": "# DIRETRIZ DE TOM: CYBERPUNK\n- Alta tecnologia...",
    "Nenhum / Neutro": "# DIRETRIZ DE TOM: NEUTRO\n- Descritivo básico."
}

DEFAULT_SETTINGS = {
    "auto_expander": False,
    "wb_allow_create_folder": True,
    "wb_allow_create_file": True,
    "wb_allow_improve_file": True,
    "tom_clima_perfil": "Dark Fantasy (Grimdark)",
    "rpg_sistema_ativo": "D&D 5e",
    "discord_prefix": "!ao",
    "discord_channels_allowed": "",
    "discord_channels_blocked": "",
    "discord_roles_dm": "Mestre, DM, GM",
    "discord_cooldown_seconds": 15,
    "ai_provider_ativo": "Gemini",
    "idioma_ativo": "pt_br"
}

PROVEDORES_IA = {
    "Gemini": "gemini",
    "Pro (OpenAI)": "pro",
    "Claude (Anthropic)": "claude"
}

def carregar_configuracoes():
    config = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception: pass
    return config

def salvar_configuracoes(config):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

def escrever_arquivo_estilo_tom(nome_perfil):
    try:
        pasta_estilo = pu.CAMINHO_ESTILO
        pasta_estilo.mkdir(parents=True, exist_ok=True)
        caminho_arquivo = pasta_estilo / "Tom_e_Clima.md"
        conteudo = PERFIS_TOM.get(nome_perfil, PERFIS_TOM["Nenhum / Neutro"])
        with open(caminho_arquivo, "w", encoding="utf-8") as f: f.write(conteudo)
    except Exception as e:
        print(f"Erro ao escrever arquivo de tom em Style: {e}")

class OptionsWidget(QWidget):
    signal_toast = Signal(str)
    signal_log = Signal(str)

    def __init__(self, parent, log_cb, toast_cb):
        super().__init__(parent)
        self.log_callback = log_cb
        self.toast_callback = toast_cb

        if self.log_callback: self.signal_log.connect(self.log_callback)
        if self.toast_callback: self.signal_toast.connect(self.toast_callback)

        self.settings = carregar_configuracoes()

        main_layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        self.grid = QGridLayout(container)
        self._build_boxes()

    def _build_boxes(self):
        # 0. IDIOMA DO SISTEMA (i18n)
        box_lang = QGroupBox(pu.tr("options.language_box"))
        l_lang = QVBoxLayout(box_lang)
        l_lang.addWidget(QLabel(pu.tr("options.select_language")))
        self.combo_lang = QComboBox()
        idiomas_disponiveis = pu.obter_idiomas_disponiveis()
        self.combo_lang.addItems([i.upper() for i in idiomas_disponiveis])
        idioma_atual = self.settings.get("idioma_ativo", "pt_br").upper()
        self.combo_lang.setCurrentText(idioma_atual)
        self.combo_lang.currentTextChanged.connect(self._on_idioma_change)
        l_lang.addWidget(self.combo_lang)

        # 1. CREDENCIAIS (.env)
        box_cred = QGroupBox(pu.tr("options.cred_box"))
        l_cred = QVBoxLayout(box_cred)

        l_cred.addWidget(QLabel(pu.tr("options.provider_label")))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(list(PROVEDORES_IA.keys()))
        provider_atual = self.settings.get("ai_provider_ativo", "Gemini")
        self.combo_provider.setCurrentText(provider_atual)
        self.combo_provider.currentTextChanged.connect(self._on_provider_change)
        l_cred.addWidget(self.combo_provider)

        l_cred.addWidget(QLabel("Gemini API Key:"))
        self.txt_gemini = QLineEdit(); self.txt_gemini.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_gemini)

        l_cred.addWidget(QLabel("Claude Token:"))
        self.txt_claude = QLineEdit(); self.txt_claude.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_claude)

        l_cred.addWidget(QLabel("OpenAI Key:"))
        self.txt_openai = QLineEdit(); self.txt_openai.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_openai)

        l_cred.addWidget(QLabel("Token Discord:"))
        self.txt_discord = QLineEdit(); self.txt_discord.setEchoMode(QLineEdit.Password)
        l_cred.addWidget(self.txt_discord)

        l_cred.addWidget(QLabel("ID Mestre Discord:"))
        self.txt_discord_dmid = QLineEdit()
        l_cred.addWidget(self.txt_discord_dmid)

        btn_salvar_env = QPushButton(pu.tr("options.save_env"))
        btn_salvar_env.clicked.connect(self.salvar_env)
        l_cred.addWidget(btn_salvar_env)

        # 2. DISCORD
        box_disc = QGroupBox(pu.tr("options.discord_box"))
        l_disc = QVBoxLayout(box_disc)
        l_disc.addWidget(QLabel(pu.tr("options.prefix_label")))
        self.txt_prefix = QLineEdit(self.settings.get("discord_prefix", "!ao"))
        self.txt_prefix.textChanged.connect(self._salvar_campos_discord)
        l_disc.addWidget(self.txt_prefix)

        l_disc.addWidget(QLabel(pu.tr("options.roles_label")))
        self.txt_roles = QLineEdit(self.settings.get("discord_roles_dm", "Mestre, DM"))
        self.txt_roles.textChanged.connect(self._salvar_campos_discord)
        l_disc.addWidget(self.txt_roles)

        # 3. TOM E CLIMA
        box_tom = QGroupBox(pu.tr("options.tone_box"))
        l_tom = QVBoxLayout(box_tom)
        self.combo_tom = QComboBox()
        self.combo_tom.addItems(list(PERFIS_TOM.keys()))
        self.combo_tom.setCurrentText(self.settings.get("tom_clima_perfil", "Dark Fantasy (Grimdark)"))
        self.combo_tom.currentTextChanged.connect(self._on_tom_change)
        l_tom.addWidget(self.combo_tom)

        # 4. SISTEMA DE REGRAS
        box_sis = QGroupBox(pu.tr("options.system_box"))
        l_sis = QVBoxLayout(box_sis)
        self.combo_sis = QComboBox()
        self.combo_sis.addItems(list(SISTEMAS_RPG.keys()))
        self.combo_sis.setCurrentText(self.settings.get("rpg_sistema_ativo", "D&D 5e"))
        self.combo_sis.currentTextChanged.connect(self._on_sistema_change)
        l_sis.addWidget(self.combo_sis)

        # 5. AUTOMAÇÃO EXPANDER
        box_exp = QGroupBox(pu.tr("options.expander_auto_box"))
        l_exp = QHBoxLayout(box_exp)
        self.rb_exp_off = QRadioButton("Desabilitado")
        self.rb_exp_on = QRadioButton("Habilitado")
        if self.settings.get("auto_expander", False): self.rb_exp_on.setChecked(True)
        else: self.rb_exp_off.setChecked(True)
        self.rb_exp_on.toggled.connect(self._on_auto_expander_change)
        l_exp.addWidget(self.rb_exp_off); l_exp.addWidget(self.rb_exp_on)

        # 6. PERMISSÕES WORLDBUILDER
        box_wb = QGroupBox(pu.tr("options.wb_permissions_box"))
        l_wb = QVBoxLayout(box_wb)
        self.chk_wb_folder = QCheckBox("Criar Pastas (CreateFolder)")
        self.chk_wb_folder.setChecked(self.settings.get("wb_allow_create_folder", True))
        self.chk_wb_folder.toggled.connect(lambda v: self._salvar_perm_wb("wb_allow_create_folder", v))

        self.chk_wb_file = QCheckBox("Criar Arquivos (CreateFile)")
        self.chk_wb_file.setChecked(self.settings.get("wb_allow_create_file", True))
        self.chk_wb_file.toggled.connect(lambda v: self._salvar_perm_wb("wb_allow_create_file", v))

        self.chk_wb_improve = QCheckBox("Melhorar Arquivos (ImproveFile)")
        self.chk_wb_improve.setChecked(self.settings.get("wb_allow_improve_file", True))
        self.chk_wb_improve.toggled.connect(lambda v: self._salvar_perm_wb("wb_allow_improve_file", v))

        l_wb.addWidget(self.chk_wb_folder); l_wb.addWidget(self.chk_wb_file); l_wb.addWidget(self.chk_wb_improve)

        self.grid.addWidget(box_lang, 0, 0)
        self.grid.addWidget(box_cred, 0, 1)
        self.grid.addWidget(box_disc, 1, 0)
        self.grid.addWidget(box_tom, 1, 1)
        self.grid.addWidget(box_sis, 2, 0)
        self.grid.addWidget(box_exp, 2, 1)
        self.grid.addWidget(box_wb, 3, 0, 1, 2)

    def _on_idioma_change(self, text):
        cod = text.lower().strip()
        self.settings["idioma_ativo"] = cod
        salvar_configuracoes(self.settings)
        pu.carregar_idioma(cod)
        self.signal_toast.emit(f"🌐 Idioma alterado para '{text}'!")

    def _salvar_perm_wb(self, chave, valor):
        self.settings[chave] = bool(valor)
        salvar_configuracoes(self.settings)

    def _on_provider_change(self, text):
        val = PROVEDORES_IA.get(text, "gemini")
        self.settings["ai_provider_ativo"] = text
        salvar_configuracoes(self.settings)
        atualizar_env({"AI_PROVIDER": val})
        self.signal_toast.emit(f"🤖 Provedor '{text}' salvo!")

    def salvar_env(self):
        novos = {}
        if self.txt_gemini.text(): novos["GOOGLE_API_KEY"] = self.txt_gemini.text().strip()
        if self.txt_claude.text(): novos["CLAUDE_TOKEN"] = self.txt_claude.text().strip()
        if self.txt_openai.text(): novos["PRO_API_KEY"] = self.txt_openai.text().strip()
        if self.txt_discord.text(): novos["DISCORD_TOKEN"] = self.txt_discord.text().strip()
        if self.txt_discord_dmid.text(): novos["MESTRE_DISCORD_ID"] = self.txt_discord_dmid.text().strip()

        atualizar_env(novos)
        self.txt_gemini.clear(); self.txt_claude.clear(); self.txt_openai.clear(); self.txt_discord.clear(); self.txt_discord_dmid.clear()
        self.signal_toast.emit("💾 Credenciais salvas no .env!")

    def _salvar_campos_discord(self):
        self.settings["discord_prefix"] = self.txt_prefix.text().strip() or "!ao"
        self.settings["discord_roles_dm"] = self.txt_roles.text().strip()
        self.settings["discord_channels_allowed"] = self.txt_allowed.text().strip()
        self.settings["discord_channels_blocked"] = self.txt_blocked.text().strip()
        try: self.settings["discord_cooldown_seconds"] = int(self.txt_cooldown.text().strip())
        except ValueError: self.settings["discord_cooldown_seconds"] = 15
        salvar_configuracoes(self.settings)

    def _on_tom_change(self, text):
        self.settings["tom_clima_perfil"] = text
        salvar_configuracoes(self.settings)
        escrever_arquivo_estilo_tom(text)
        self.signal_toast.emit(f"🎨 Estilo '{text}' salvo em Style!")

    def _on_sistema_change(self, text):
        self.settings["rpg_sistema_ativo"] = text
        salvar_configuracoes(self.settings)
        self.signal_toast.emit(f"⚔️ Sistema '{text}' ativado!")

    def is_auto_expander_enabled(self): return self.rb_exp_on.isChecked()
    def _on_auto_expander_change(self):
        hab = self.rb_exp_on.isChecked()
        self.settings["auto_expander"] = hab
        salvar_configuracoes(self.settings)
        self.signal_toast.emit(f"⚙️ Expander Automático {'Habilitado' if hab else 'Desabilitado'}!")