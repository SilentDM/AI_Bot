import json, os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QGroupBox, QCheckBox, QRadioButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
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
    "discord_channels_knowledge": "",
    "discord_roles_dm": "Mestre, DM, GM",
    "discord_cooldown_seconds": 15,
    "ai_provider_ativo": "Gemini",
    "idioma_ativo": "pt_br",
    "model_selection_mode": "auto",
    "manual_model_order": [],
    "servers": {}
}

PROVEDORES_IA = {
    "Gemini": "gemini",
    "Pro (OpenAI)": "pro",
    "Claude (Anthropic)": "claude"
}

def carregar_configuracoes():
    config = DEFAULT_SETTINGS.copy()
    precisa_salvar = False

    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, dict):
                    for k in DEFAULT_SETTINGS:
                        if k not in dados:
                            precisa_salvar = True
                    config.update(dados)
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
            precisa_salvar = True
    else:
        precisa_salvar = True

    if precisa_salvar:
        salvar_configuracoes(config)

    return config

def salvar_configuracoes(config):
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

def obter_configuracao_servidor(guild_id: str = None) -> dict:
    config_global = carregar_configuracoes()
    if not guild_id or guild_id in ["global", "dm"]:
        return config_global

    servidores = config_global.get("servers", {})
    config_servidor = servidores.get(str(guild_id), {})

    resultado = config_global.copy()
    resultado.update(config_servidor)
    return resultado

def registrar_servidores_descobertos(lista_guilds):
    if not lista_guilds:
        return

    config = carregar_configuracoes()
    if "servers" not in config or not isinstance(config["servers"], dict):
        config["servers"] = {}

    alterou = False
    for g_id, g_name in lista_guilds:
        str_id = str(g_id)
        if str_id not in config["servers"]:
            config["servers"][str_id] = {
                "name": g_name,
                "discord_prefix": config.get("discord_prefix", "!ao"),
                "discord_roles_dm": config.get("discord_roles_dm", "Mestre, DM, GM"),
                "discord_channels_allowed": config.get("discord_channels_allowed", ""),
                "discord_channels_blocked": config.get("discord_channels_blocked", ""),
                "discord_channels_knowledge": config.get("discord_channels_knowledge", ""),
                "discord_cooldown_seconds": config.get("discord_cooldown_seconds", 15)
            }
            alterou = True
        else:
            if config["servers"][str_id].get("name") != g_name:
                config["servers"][str_id]["name"] = g_name
                alterou = True

    if alterou:
        salvar_configuracoes(config)
        print(f"💾 {len(lista_guilds)} servidores do Discord registrados no settings.json.")

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
        self.selected_guild_id = "global"

        main_layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)

        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        container_layout.addLayout(self.grid)

        self._build_boxes()
        container_layout.addStretch()

    def _popular_combo_servidores(self):
        current_id = self.selected_guild_id or "global"
        
        self.combo_server.blockSignals(True)
        self.combo_server.clear()
        self.combo_server.addItem("🌐 Configurações Padrão (Global)", "global")

        servidores_salvos = self.settings.get("servers", {})
        for g_id, g_data in servidores_salvos.items():
            g_name = g_data.get("name", f"Servidor {g_id}")
            self.combo_server.addItem(f"🛡️ {g_name} (ID: {g_id})", str(g_id))

        idx = self.combo_server.findData(current_id)
        if idx >= 0:
            self.combo_server.setCurrentIndex(idx)
        else:
            self.combo_server.setCurrentIndex(0)

        self.combo_server.blockSignals(False)

    @Slot(list)
    def atualizar_lista_servidores(self, lista_guilds):
        registrar_servidores_descobertos(lista_guilds)
        self.settings = carregar_configuracoes()
        self._popular_combo_servidores()

    def _on_server_selection_changed(self, index):
        self.selected_guild_id = self.combo_server.currentData() or "global"
        self._carregar_campos_servidor()

    def _carregar_campos_servidor(self):
        config_srv = obter_configuracao_servidor(self.selected_guild_id)
        self.txt_prefix.setText(config_srv.get("discord_prefix", "!ao"))
        self.txt_roles.setText(config_srv.get("discord_roles_dm", "Mestre, DM, GM"))
        self.txt_allowed.setText(config_srv.get("discord_channels_allowed", ""))
        self.txt_blocked.setText(config_srv.get("discord_channels_blocked", ""))
        self.txt_knowledge.setText(config_srv.get("discord_channels_knowledge", ""))
        self.txt_cooldown.setText(str(config_srv.get("discord_cooldown_seconds", 15)))

    def _build_boxes(self):
        # 0. IDIOMA DO SISTEMA
        box_lang = QGroupBox(pu.tr("options.language_box"))
        l_lang = QVBoxLayout(box_lang)
        l_lang.setAlignment(Qt.AlignTop); l_lang.setSpacing(6)
        l_lang.addWidget(QLabel(pu.tr("options.select_language")))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems([i.upper() for i in pu.obter_idiomas_disponiveis()])
        self.combo_lang.setCurrentText(self.settings.get("idioma_ativo", "pt_br").upper())
        self.combo_lang.currentTextChanged.connect(self._on_idioma_change)
        l_lang.addWidget(self.combo_lang)

        # 1. CREDENCIAIS (.env)
        box_cred = QGroupBox(pu.tr("options.cred_box"))
        l_cred = QVBoxLayout(box_cred)
        l_cred.setAlignment(Qt.AlignTop); l_cred.setSpacing(6)
        l_cred.addWidget(QLabel(pu.tr("options.provider_label")))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(list(PROVEDORES_IA.keys()))
        self.combo_provider.setCurrentText(self.settings.get("ai_provider_ativo", "Gemini"))
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

        # 2. DISCORD COM SELETOR DE SERVIDOR E BOTAO DE SALVAR
        box_disc = QGroupBox(pu.tr("options.discord_box"))
        l_disc = QVBoxLayout(box_disc)
        l_disc.setAlignment(Qt.AlignTop); l_disc.setSpacing(6)

        l_disc.addWidget(QLabel("Servidor do Discord para Configurar:"))
        self.combo_server = QComboBox()
        self.combo_server.currentIndexChanged.connect(self._on_server_selection_changed)
        l_disc.addWidget(self.combo_server)

        self._popular_combo_servidores()

        l_disc.addWidget(QLabel(pu.tr("options.prefix_label")))
        self.txt_prefix = QLineEdit(self.settings.get("discord_prefix", "!ao"))
        l_disc.addWidget(self.txt_prefix)

        l_disc.addWidget(QLabel(pu.tr("options.roles_label")))
        self.txt_roles = QLineEdit(self.settings.get("discord_roles_dm", "Mestre, DM, GM"))
        l_disc.addWidget(self.txt_roles)

        l_disc.addWidget(QLabel(pu.tr("options.allowed_channels")))
        self.txt_allowed = QLineEdit(self.settings.get("discord_channels_allowed", ""))
        l_disc.addWidget(self.txt_allowed)

        l_disc.addWidget(QLabel(pu.tr("options.blocked_channels")))
        self.txt_blocked = QLineEdit(self.settings.get("discord_channels_blocked", ""))
        l_disc.addWidget(self.txt_blocked)

        l_disc.addWidget(QLabel("Canais de Conhecimento / Crônicas (Regras, Eventos):"))
        self.txt_knowledge = QLineEdit(self.settings.get("discord_channels_knowledge", ""))
        self.txt_knowledge.setPlaceholderText("ex: regras, cronicas-dos-jogadores")
        l_disc.addWidget(self.txt_knowledge)

        l_disc.addWidget(QLabel(pu.tr("options.cooldown_label")))
        self.txt_cooldown = QLineEdit(str(self.settings.get("discord_cooldown_seconds", 15)))
        l_disc.addWidget(self.txt_cooldown)

        # 🟢 BOTAO DE SALVAR CONFIGURAÇÕES DO DISCORD
        btn_salvar_disc = QPushButton("Salvar Configurações do Discord")
        btn_salvar_disc.setStyleSheet("background-color: #0f766e; color: white; font-weight: bold; margin-top: 6px;")
        btn_salvar_disc.clicked.connect(self._salvar_campos_discord)
        l_disc.addWidget(btn_salvar_disc)

        # 3. TOM E CLIMA
        box_tom = QGroupBox(pu.tr("options.tone_box"))
        l_tom = QVBoxLayout(box_tom); l_tom.setAlignment(Qt.AlignTop); l_tom.setSpacing(6)
        self.combo_tom = QComboBox()
        self.combo_tom.addItems(list(PERFIS_TOM.keys()))
        self.combo_tom.setCurrentText(self.settings.get("tom_clima_perfil", "Dark Fantasy (Grimdark)"))
        self.combo_tom.currentTextChanged.connect(self._on_tom_change)
        l_tom.addWidget(self.combo_tom)

        # 4. SISTEMA DE REGRAS
        box_sis = QGroupBox(pu.tr("options.system_box"))
        l_sis = QVBoxLayout(box_sis); l_sis.setAlignment(Qt.AlignTop); l_sis.setSpacing(6)
        self.combo_sis = QComboBox()
        self.combo_sis.addItems(list(SISTEMAS_RPG.keys()))
        self.combo_sis.setCurrentText(self.settings.get("rpg_sistema_ativo", "D&D 5e"))
        self.combo_sis.currentTextChanged.connect(self._on_sistema_change)
        l_sis.addWidget(self.combo_sis)

        # 5. AUTOMAÇÃO EXPANDER
        box_exp = QGroupBox(pu.tr("options.expander_auto_box"))
        l_exp = QHBoxLayout(box_exp); l_exp.setAlignment(Qt.AlignTop); l_exp.setSpacing(10)
        self.rb_exp_off = QRadioButton("Desabilitado")
        self.rb_exp_on = QRadioButton("Habilitado")
        if self.settings.get("auto_expander", False): self.rb_exp_on.setChecked(True)
        else: self.rb_exp_off.setChecked(True)
        self.rb_exp_on.toggled.connect(self._on_auto_expander_change)
        l_exp.addWidget(self.rb_exp_off); l_exp.addWidget(self.rb_exp_on)

        # 6. PERMISSÕES WORLDBUILDER
        box_wb = QGroupBox(pu.tr("options.wb_permissions_box"))
        l_wb = QVBoxLayout(box_wb); l_wb.setAlignment(Qt.AlignTop); l_wb.setSpacing(6)
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

    def _salvar_campos_discord(self):
        prefix = self.txt_prefix.text().strip() or "!ao"
        roles = self.txt_roles.text().strip()
        allowed = self.txt_allowed.text().strip()
        blocked = self.txt_blocked.text().strip()
        knowledge = self.txt_knowledge.text().strip()
        try: cooldown = int(self.txt_cooldown.text().strip())
        except ValueError: cooldown = 15

        nome_alvo = "Padrão (Global)" if self.selected_guild_id == "global" else self.combo_server.currentText()

        if self.selected_guild_id == "global":
            self.settings["discord_prefix"] = prefix
            self.settings["discord_roles_dm"] = roles
            self.settings["discord_channels_allowed"] = allowed
            self.settings["discord_channels_blocked"] = blocked
            self.settings["discord_channels_knowledge"] = knowledge
            self.settings["discord_cooldown_seconds"] = cooldown
        else:
            if "servers" not in self.settings:
                self.settings["servers"] = {}
            if self.selected_guild_id not in self.settings["servers"]:
                self.settings["servers"][self.selected_guild_id] = {}

            self.settings["servers"][self.selected_guild_id].update({
                "discord_prefix": prefix,
                "discord_roles_dm": roles,
                "discord_channels_allowed": allowed,
                "discord_channels_blocked": blocked,
                "discord_channels_knowledge": knowledge,
                "discord_cooldown_seconds": cooldown
            })

        salvar_configuracoes(self.settings)
        self.signal_toast.emit(f"💾 Configurações do Discord salvas ({nome_alvo})!")

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