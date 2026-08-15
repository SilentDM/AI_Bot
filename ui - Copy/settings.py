import json
import os
import tkinter as tk
from tkinter import ttk
from pathlib import Path
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
    "Dark Fantasy (Grimdark)": (
        "# DIRETRIZ DE TOM E CLIMA: DARK FANTASY (GRIMDARK)\n\n"
        "- As descrições devem focar em atmosfera sombria, visceral, perigo iminente e decadência.\n"
        "- Evite resoluções fáceis, vilões caricatos ou maniqueísmo puro (bem vs mal absoluto).\n"
        "- Destaque detalhes sensoriais: o frio, o cheiro de ferrugem, o ranger de madeira, a penumbra e o silêncio desconfortável.\n"
        "- A magia e o desconhecido devem parecer perigosos e imprevisíveis."
    ),
    "High Fantasy Épico": (
        "# DIRETRIZ DE TOM E CLIMA: HIGH FANTASY ÉPICO\n\n"
        "- As descrições devem ser grandiosas, vibrantes e solenes, destacando o heroísmo e maravilhas mágicas.\n"
        "- Destaque arquiteturas imponentes, linhagens nobres, relíquias reluzentes e grande profundidade histórica.\n"
        "- A magia é uma força presente e visível no mundo, moldando paisagens e reinos."
    ),
    "Mistério & Investigação": (
        "# DIRETRIZ DE TOM E CLIMA: MISTÉRIO E INVESTIGAÇÃO\n\n"
        "- Foque em pistas sutis, segredos velados, meias-verdades e motivações ocultas.\n"
        "- As descrições devem instigar a curiosidade, deixando lacunas para o leitor ou jogador conectar os pontos.\n"
        "- Mantenha um tom sóbrio, analítico e repleto de suspense."
    ),
    "Cyberpunk / Sci-Fi": (
        "# DIRETRIZ DE TOM E CLIMA: CYBERPUNK / SCI-FI\n\n"
        "- Descrições focadas no contraste entre alta tecnologia e decadência urbana/social.\n"
        "- Use terminologias técnicas, luzes de neon na escuridão, intriga corporativa e atmosferas cínicas."
    ),
    "Nenhum / Neutro": (
        "# DIRETRIZ DE TOM E CLIMA: NEUTRO\n\n"
        "- Mantenha um tom informativo, claro e descritivo padrão para worldbuilding de RPG sem viés de gênero."
    )
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
    "ai_provider_ativo": "Gemini"
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
                dados = json.load(f)
                config.update(dados)
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
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
        
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as e:
        print(f"Erro ao escrever arquivo de tom em Style: {e}")


class OptionsFrame(ttk.Frame):
    def __init__(self, parent, log_callback, toast_callback, page_header_callback):
        super().__init__(parent)
        self.log_callback = log_callback
        self.toast_callback = toast_callback
        self.settings = carregar_configuracoes()

        page_header_callback(self, "Opções do Sistema", "Configure credenciais (.env), comportamentos automáticos e regras do bot do Discord.")

        # --- ÁREA DE ROLAGEM DYNÂMICA (CANVAS + SCROLLBAR) ---
        self.canvas = tk.Canvas(self, bg="#121212", highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        self.scroll_frame = ttk.Frame(self.canvas)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=(0, 15))
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=(0, 15))

        self.boxes = []
        self.last_rendered_cols = 0

        self._build_boxes()
        self._render_grid()

    def _on_mousewheel(self, event):
        if self.winfo_viewable():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_resize(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        self._render_grid()

    def _render_grid(self):
        canvas_width = self.canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 800

        # Se a tela for larga (>= 720px), exibe em 2 colunas responsivas; Senão 1 coluna
        num_cols = 2 if canvas_width >= 720 else 1

        if self.last_rendered_cols == num_cols:
            return
        self.last_rendered_cols = num_cols

        for c in range(2):
            self.scroll_frame.columnconfigure(c, weight=1 if c < num_cols else 0)

        for idx, box in enumerate(self.boxes):
            box.grid_forget()
            if num_cols == 2:
                row = idx // 2
                col = idx % 2
            else:
                row = idx
                col = 0
            box.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

    def _build_boxes(self):
        # 1. Credenciais (.env)
        cred_box = ttk.LabelFrame(self.scroll_frame, text=" Credenciais de API e Discord (.env) ")
        
        ttk.Label(cred_box, text="Provedor de IA Ativo:").pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.combo_provider = ttk.Combobox(
            cred_box, state="readonly",
            values=list(PROVEDORES_IA.keys()), font=("Segoe UI", 10)
        )
        provider_atual_env = os.getenv("AI_PROVIDER", "gemini").strip().lower()
        provider_label = next(
            (label for label, val in PROVEDORES_IA.items() if val == provider_atual_env),
            "Gemini"
        )
        self.combo_provider.set(provider_label)
        self.combo_provider.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.combo_provider.bind("<<ComboboxSelected>>", self._on_provider_change)
        ttk.Label(
            cred_box,
            text="⚠️ Requer reiniciar o programa para o novo provedor ter efeito.",
            foreground="#f59e0b", font=("Segoe UI", 8, "italic")
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        ttk.Separator(cred_box, orient="horizontal").pack(fill=tk.X, padx=10, pady=(0, 8))
        # --- Gemini ---
        ttk.Label(cred_box, text="Gemini", font=("Segoe UI", 9, "bold"), foreground="#10b981").pack(anchor=tk.W, padx=10)
        ttk.Label(cred_box, text="Chave da API Gemini:").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.entry_gemini_key = ttk.Entry(cred_box, show="*", font=("Segoe UI", 10))
        self.entry_gemini_key.pack(fill=tk.X, padx=10, pady=(0, 8))

        # --- Claude ---
        ttk.Label(cred_box, text="Claude (Anthropic)", font=("Segoe UI", 9, "bold"), foreground="#10b981").pack(anchor=tk.W, padx=10)
        ttk.Label(cred_box, text="Token da API Claude:").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.entry_claude_key = ttk.Entry(cred_box, show="*", font=("Segoe UI", 10))
        self.entry_claude_key.pack(fill=tk.X, padx=10, pady=(0, 8))

        # --- OpenAI (Pro) ---
        ttk.Label(cred_box, text="OpenAI (Pro)", font=("Segoe UI", 9, "bold"), foreground="#10b981").pack(anchor=tk.W, padx=10)
        ttk.Label(cred_box, text="Chave da API OpenAI:").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.entry_openai_key = ttk.Entry(cred_box, show="*", font=("Segoe UI", 10))
        self.entry_openai_key.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Separator(cred_box, orient="horizontal").pack(fill=tk.X, padx=10, pady=(0, 8))

        # --- Discord ---
        ttk.Label(cred_box, text="Token Bot Discord:").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.entry_discord_key = ttk.Entry(cred_box, show="*", font=("Segoe UI", 10))
        self.entry_discord_key.pack(fill=tk.X, padx=10, pady=(0, 6))

        ttk.Label(cred_box, text="ID do Mestre no Discord (MESTRE_DISCORD_ID):").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.entry_discord_dmid = ttk.Entry(cred_box, font=("Segoe UI", 10))
        self.entry_discord_dmid.pack(fill=tk.X, padx=10, pady=(0, 10))

        btn_salvar_env = ttk.Button(cred_box, text="Salvar Credenciais", command=self._salvar_credenciais_env)
        btn_salvar_env.pack(anchor=tk.E, padx=10, pady=(0, 10))

        # 2. Bot do Discord - Regras e Gatilho
        discord_box = ttk.LabelFrame(self.scroll_frame, text=" Bot do Discord - Regras e Gatilho ")
        ttk.Label(discord_box, text="Gatilho de Comunicação (Prefixo):").pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.var_prefix = tk.StringVar(value=self.settings.get("discord_prefix", "!ao"))
        entry_prefix = ttk.Entry(discord_box, textvariable=self.var_prefix, font=("Segoe UI", 10))
        entry_prefix.pack(fill=tk.X, padx=10, pady=(0, 6))
        entry_prefix.bind("<KeyRelease>", self._salvar_campos_discord)

        ttk.Label(discord_box, text="Cargos de Mestre (Acesso com Segredos):").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.var_roles = tk.StringVar(value=self.settings.get("discord_roles_dm", "Mestre, DM, GM"))
        entry_roles = ttk.Entry(discord_box, textvariable=self.var_roles, font=("Segoe UI", 10))
        entry_roles.pack(fill=tk.X, padx=10, pady=(0, 6))
        entry_roles.bind("<KeyRelease>", self._salvar_campos_discord)

        ttk.Label(discord_box, text="Canais Permitidos (deixe em branco para TODOS):").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.var_allowed = tk.StringVar(value=self.settings.get("discord_channels_allowed", ""))
        entry_allowed = ttk.Entry(discord_box, textvariable=self.var_allowed, font=("Segoe UI", 10))
        entry_allowed.pack(fill=tk.X, padx=10, pady=(0, 6))
        entry_allowed.bind("<KeyRelease>", self._salvar_campos_discord)

        ttk.Label(discord_box, text="Canais Proibidos/Ignorados:").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.var_blocked = tk.StringVar(value=self.settings.get("discord_channels_blocked", ""))
        entry_blocked = ttk.Entry(discord_box, textvariable=self.var_blocked, font=("Segoe UI", 10))
        entry_blocked.pack(fill=tk.X, padx=10, pady=(0, 6))
        entry_blocked.bind("<KeyRelease>", self._salvar_campos_discord)

        ttk.Label(discord_box, text="Tempo de espera por usuário (segundos):").pack(anchor=tk.W, padx=10, pady=(4, 2))
        self.var_cooldown = tk.StringVar(value=str(self.settings.get("discord_cooldown_seconds", 5)))
        entry_cooldown = ttk.Entry(discord_box, textvariable=self.var_cooldown, font=("Segoe UI", 10))
        entry_cooldown.pack(fill=tk.X, padx=10, pady=(0, 10))
        entry_cooldown.bind("<KeyRelease>", self._salvar_campos_discord)

        # 3. Tom e Clima
        tom_box = ttk.LabelFrame(self.scroll_frame, text=" Tom e Clima do Cenário (Style/*.md) ")
        ttk.Label(tom_box, text="Escolha o tom do cenário. Atualiza 'Tom_e_Clima.md' em Style:").pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.combo_tom = ttk.Combobox(tom_box, state="readonly", values=list(PERFIS_TOM.keys()), font=("Segoe UI", 10))
        perfil_atual = self.settings.get("tom_clima_perfil", "Dark Fantasy (Grimdark)")
        self.combo_tom.set(perfil_atual)
        self.combo_tom.pack(fill=tk.X, padx=10, pady=(0, 12))
        self.combo_tom.bind("<<ComboboxSelected>>", self._on_tom_change)
        escrever_arquivo_estilo_tom(perfil_atual)

        # 4. Sistema de Regras RPG
        sistem_box = ttk.LabelFrame(self.scroll_frame, text=" Sistema de Regras de RPG ")
        ttk.Label(sistem_box, text="Selecione o sistema de regras ativo do seu cenário:").pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.combo_sistema = ttk.Combobox(sistem_box, state="readonly", values=list(SISTEMAS_RPG.keys()), font=("Segoe UI", 10))
        sistema_atual = self.settings.get("rpg_sistema_ativo", "D&D 5e")
        self.combo_sistema.set(sistema_atual)
        self.combo_sistema.pack(fill=tk.X, padx=10, pady=(0, 12))
        self.combo_sistema.bind("<<ComboboxSelected>>", self._on_sistema_change)

        # 5. Automação do Expander
        expander_opt_box = ttk.LabelFrame(self.scroll_frame, text=" Automação do Expander ")
        ttk.Label(expander_opt_box, text="Executar o Expander automaticamente ao salvar um arquivo com a tag <-- TODO:").pack(anchor=tk.W, padx=10, pady=(10, 8))
        valor_inicial = bool(self.settings.get("auto_expander", False))
        self.auto_expander_var = tk.BooleanVar(value=valor_inicial)

        radio_frame = ttk.Frame(expander_opt_box)
        radio_frame.pack(anchor=tk.W, padx=10, pady=(0, 12))
        ttk.Radiobutton(radio_frame, text="Desabilitado", value=False, variable=self.auto_expander_var, command=self._on_auto_expander_change).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(radio_frame, text="Habilitado", value=True, variable=self.auto_expander_var, command=self._on_auto_expander_change).pack(side=tk.LEFT)

        # 6. Permissões WorldBuilder
        wb_opt_box = ttk.LabelFrame(self.scroll_frame, text=" WorldBuilder - Permissões de Ação ")
        ttk.Label(wb_opt_box, text="Ações autorizadas para execução autônoma pelo WorldBuilder:").pack(anchor=tk.W, padx=10, pady=(10, 8))
        self._criar_opcao_wb(wb_opt_box, "Criar Pastas (CreateFolder):", "wb_allow_create_folder")
        self._criar_opcao_wb(wb_opt_box, "Criar Arquivos (CreateFile):", "wb_allow_create_file")
        self._criar_opcao_wb(wb_opt_box, "Melhorar Arquivos (ImproveFile):", "wb_allow_improve_file")

        # Lista organizada dos quadros para o grid responsivo
        self.boxes = [cred_box, discord_box, tom_box, sistem_box, expander_opt_box, wb_opt_box]
    def _on_provider_change(self, event):
        label_escolhido = self.combo_provider.get()
        valor_env = PROVEDORES_IA.get(label_escolhido, "gemini")
        self.settings["ai_provider_ativo"] = label_escolhido
        salvar_configuracoes(self.settings)
        atualizar_env({"AI_PROVIDER": valor_env})

        if self.log_callback:
            self.log_callback(f"Provedor de IA alterado para: {label_escolhido} (AI_PROVIDER={valor_env})")
        if self.toast_callback:
            self.toast_callback(f"🤖 Provedor '{label_escolhido}' salvo! Reinicie o programa para aplicar.")

    def _salvar_credenciais_env(self):
        gemini_key = self.entry_gemini_key.get().strip()
        claude_key = self.entry_claude_key.get().strip()
        openai_key = self.entry_openai_key.get().strip()
        discord_key = self.entry_discord_key.get().strip()
        discord_dmid = self.entry_discord_dmid.get().strip()

        novos_valores = {}

        if gemini_key:
            novos_valores["GOOGLE_API_KEY"] = gemini_key
        if claude_key:
            novos_valores["CLAUDE_TOKEN"] = claude_key
        if openai_key:
            novos_valores["PRO_API_KEY"] = openai_key
        if discord_key:
            novos_valores["DISCORD_TOKEN"] = discord_key
        if discord_dmid:
            novos_valores["MESTRE_DISCORD_ID"] = discord_dmid

        if not novos_valores:
            if self.toast_callback:
                self.toast_callback("⚠️ Nenhum campo de credencial foi preenchido.")
            return

        atualizar_env(novos_valores)

        self.entry_gemini_key.delete(0, tk.END)
        self.entry_claude_key.delete(0, tk.END)
        self.entry_openai_key.delete(0, tk.END)
        self.entry_discord_key.delete(0, tk.END)
        self.entry_discord_dmid.delete(0, tk.END)

        if self.log_callback:
            self.log_callback("✅ Credenciais salvas com sucesso no arquivo .env!")
        if self.toast_callback:
            self.toast_callback("💾 Credenciais atualizadas no .env com sucesso!")

    def _salvar_campos_discord(self, event):
        prefixo = self.var_prefix.get().strip() or "!ao"
        self.settings["discord_prefix"] = prefixo
        self.settings["discord_roles_dm"] = self.var_roles.get().strip()
        self.settings["discord_channels_allowed"] = self.var_allowed.get().strip()
        self.settings["discord_channels_blocked"] = self.var_blocked.get().strip()
        
        try:
            self.settings["discord_cooldown_seconds"] = int(self.var_cooldown.get().strip())
        except ValueError:
            self.settings["discord_cooldown_seconds"] = 5

        salvar_configuracoes(self.settings)

    def _on_tom_change(self, event):
        novo_tom = self.combo_tom.get()
        self.settings["tom_clima_perfil"] = novo_tom
        salvar_configuracoes(self.settings)
        escrever_arquivo_estilo_tom(novo_tom)

        if self.log_callback:
            self.log_callback(f"Tom do Cenário alterado para: {novo_tom}")
        if self.toast_callback:
            self.toast_callback(f"🎨 Estilo '{novo_tom}' salvo na pasta Style!")

    def _on_sistema_change(self, event):
        novo_sis = self.combo_sistema.get()
        self.settings["rpg_sistema_ativo"] = novo_sis
        salvar_configuracoes(self.settings)

        if self.log_callback:
            self.log_callback(f"Sistema de RPG alterado para: {novo_sis}")
        if self.toast_callback:
            self.toast_callback(f"⚔️ Sistema '{novo_sis}' ativado!")

    def is_auto_expander_enabled(self):
        return bool(self.auto_expander_var.get())

    def _on_auto_expander_change(self):
        habilitado = self.is_auto_expander_enabled()
        self.settings["auto_expander"] = habilitado
        salvar_configuracoes(self.settings)

        status_str = "Habilitado" if habilitado else "Desabilitado"
        if self.log_callback:
            self.log_callback(f"Expander Automático ao salvar: {status_str.upper()}")
        if self.toast_callback:
            self.toast_callback(f"⚙️ Expander Automático {status_str}!")

    def _criar_opcao_wb(self, parent_box, titulo, chave_setting):
        frame_linha = ttk.Frame(parent_box)
        frame_linha.pack(fill=tk.X, padx=10, pady=4)

        ttk.Label(frame_linha, text=titulo, width=28, anchor="w").pack(side=tk.LEFT)

        var = tk.BooleanVar(value=bool(self.settings.get(chave_setting, True)))
        setattr(self, f"var_{chave_setting}", var)

        ttk.Radiobutton(
            frame_linha, text="Desabilitado", value=False, variable=var,
            command=lambda: self._on_wb_setting_change(chave_setting, var, titulo)
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            frame_linha, text="Habilitado", value=True, variable=var,
            command=lambda: self._on_wb_setting_change(chave_setting, var, titulo)
        ).pack(side=tk.LEFT)

    def _on_wb_setting_change(self, chave_setting, var, titulo):
        habilitado = bool(var.get())
        self.settings[chave_setting] = habilitado
        salvar_configuracoes(self.settings)
        status_str = "HABILITADO" if habilitado else "DESABILITADO"
        if self.log_callback:
            self.log_callback(f"WorldBuilder -> {titulo} {status_str}")
        if self.toast_callback:
            self.toast_callback(f"⚙️ {titulo.split('(')[0].strip()}: {status_str.title()}!")