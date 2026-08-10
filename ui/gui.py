import os, threading, time, asyncio, sys, pystray, sys, ctypes, json
import core.ai_gemini as ag
import core.cache_gemini as cg
import core.memory as me
import core.ai_utils as au
import engine.compiler as comp
import engine.expander as ex
import engine.wbuilder as wb
import engine.project_utils as pu
import ui.explorer as expl
import ui.gui_logger as gl
import ui.settings as st
import ui.setup_env as se
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
from pystray import MenuItem as item
from PIL import Image

SETTINGS_FILE = pu.PASTA_LOGS / "settings.json"

class SilentDesktopApp:
    def __init__(self, root):
        self.root = root
        self.user_name = "Silent Dungeon Master"
        self.root.title("Silent Multiverse Nexus")
        self.root.geometry("1300x700")
        self.root.minsize(1050, 550)
        self.root.state("zoomed")  # Windows
        self.root.configure(bg="#121212")

        self.current_font_size = 11
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.setup_dark_style()

        # Estados internos das engines de background
        self.discord_running = False
        self.expander_running = False
        self.worldbuilder_running = False
        self.audit_running = False
        self.discord_loop = None

        # Controle de navegação
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = None

        self.setup_ui()
        self.setup_status_bar()
        self.setup_shortcuts()
        self.change_font_size(0)

        # Página inicial ao abrir o programa
        icon_path = pu.BASE_DIR / "icon.ico"
        if icon_path.exists():
            self.root.iconbitmap(str(icon_path))
        self.switch_page("editor")

        self.start_discord_bot_thread()

        # Executa descoberta de modelos em segundo plano para não travar o startup
        threading.Thread(target=ag.findmodel, daemon=True).start()
        
        self.setup_system_tray()

    # ------------------------------------------------------------------
    # SISTEMA DE OPÇÕES
    # ------------------------------------------------------------------
    def get_auto_expander_status(self):
        return self.auto_expander_var.get() == "Habilitado"

    # ------------------------------------------------------------------
    # SISTEMA DE POPUP TOAST FLUTUANTE
    # ------------------------------------------------------------------
    def toast(self, mensagem, duration=3500):
        def _create_toast():
            try:
                popup = tk.Toplevel(self.root)
                popup.overrideredirect(True)
                popup.attributes("-topmost", True)
                popup.configure(bg="#1e1e1e")

                frame = tk.Frame(popup, bg="#1e1e1e", highlightbackground="#10b981", highlightthickness=1)
                frame.pack(fill=tk.BOTH, expand=True)

                lbl = tk.Label(
                    frame,
                    text=mensagem,
                    bg="#1e1e1e",
                    fg="#e3e3e3",
                    font=("Segoe UI", 9, "bold"),
                    padx=14,
                    pady=10,
                    wraplength=360,
                    justify="left"
                )
                lbl.pack()

                popup.update_idletasks()
                w = popup.winfo_width()
                h = popup.winfo_height()

                rx = self.root.winfo_x()
                ry = self.root.winfo_y()
                rw = self.root.winfo_width()
                rh = self.root.winfo_height()

                x = rx + rw - w - 25
                y = ry + rh - h - 35

                x = max(10, x)
                y = max(10, y)

                popup.geometry(f"+{x}+{y}")
                popup.after(duration, popup.destroy)
            except Exception as e:
                print(f"Erro ao exibir Toast: {e}")

        self.root.after(0, _create_toast)

    # ------------------------------------------------------------------
    # ESTILO VISUAL (Dark Mode)
    # ------------------------------------------------------------------
    def setup_dark_style(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.root.option_add('*TCombobox*Listbox.background', '#252526')
        self.root.option_add('*TCombobox*Listbox.foreground', '#ffffff')
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#0f766e')
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))

        self.style.configure('.',
            background='#121212',
            foreground='#e3e3e3',
            fieldbackground='#1e1e1e',
            font=('Segoe UI', 10),
            bordercolor='#2d2d2d',
            lightcolor='#121212',
            darkcolor='#121212'
        )
        self.style.map('.',
            background=[('active', '#2d2d2d'), ('disabled', '#121212')],
            foreground=[('disabled', '#6b6b6b')]
        )

        self.style.configure('TPanedwindow', background='#121212')
        self.style.configure('Sash', background='#2d2d2d', bordercolor='#2d2d2d', sashthickness=3)

        self.style.configure('TLabelframe', background='#1e1e1e', bordercolor='#2d2d2d', borderwidth=1)
        self.style.configure('TLabelframe.Label', background='#1e1e1e', foreground='#10b981', font=('Segoe UI', 10, 'bold'))

        self.style.configure('TButton',
            background='#252526', foreground='#e3e3e3', bordercolor='#2d2d2d',
            lightcolor='#2d2d2d', darkcolor='#121212', borderwidth=1, padding=6
        )
        self.style.map('TButton',
            background=[('active', '#333333'), ('pressed', '#121212')],
            foreground=[('active', '#ffffff')]
        )

        self.style.configure('TEntry', fieldbackground='#252526', foreground='#ffffff', bordercolor='#2d2d2d', lightcolor='#252526', darkcolor='#252526')

        self.style.configure('TCombobox',
            fieldbackground='#252526',
            background='#252526',
            foreground='#ffffff',
            bordercolor='#2d2d2d',
            lightcolor='#252526',
            darkcolor='#252526',
            arrowcolor='#e3e3e3'
        )
        self.style.map('TCombobox',
            fieldbackground=[('readonly', '#252526'), ('focus', '#252526'), ('active', '#252526')],
            foreground=[('readonly', '#ffffff'), ('focus', '#ffffff'), ('active', '#ffffff')],
            selectbackground=[('readonly', '#0f766e'), ('focus', '#0f766e')],
            selectforeground=[('readonly', '#ffffff'), ('focus', '#ffffff')]
        )

        self.style.configure('Treeview', background='#1e1e1e', foreground='#e3e3e3', fieldbackground='#1e1e1e', bordercolor='#2d2d2d', borderwidth=1, rowheight=24)
        self.style.map('Treeview',
            background=[('selected', '#0f766e')],
            foreground=[('selected', '#ffffff')]
        )
        self.style.configure('Heading', background='#121212', foreground='#10b981', bordercolor='#2d2d2d', font=('Segoe UI', 9, 'bold'))
        self.style.map('Heading', background=[('active', '#2d2d2d')])

        self.style.configure('Vertical.TScrollbar', background='#252526', troughcolor='#121212', bordercolor='#2d2d2d', lightcolor='#252526', darkcolor='#252526', arrowcolor='#e3e3e3')
        self.style.map('Vertical.TScrollbar', background=[('active', '#2d2d2d')])

        self.style.configure('Nav.TButton',
            background='#121212', foreground='#cccccc', borderwidth=0,
            anchor='w', padding=(16, 12), font=('Segoe UI', 10)
        )
        self.style.map('Nav.TButton', background=[('active', '#1e1e1e')])

        self.style.configure('NavActive.TButton',
            background='#1e1e1e', foreground='#10b981', borderwidth=0,
            anchor='w', padding=(16, 12), font=('Segoe UI', 10, 'bold')
        )
        self.style.map('NavActive.TButton', background=[('active', '#1e1e1e')])

    # ------------------------------------------------------------------
    # MONTAGEM DA INTERFACE
    # ------------------------------------------------------------------
    def setup_ui(self):
        root_container = ttk.Frame(self.root)
        root_container.pack(fill=tk.BOTH, expand=True)
        root_container.columnconfigure(1, weight=1)
        root_container.rowconfigure(0, weight=1)

        sidebar = tk.Frame(root_container, bg="#0a0a0a", width=200)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="🜂 Silent Console", bg="#0a0a0a", fg="#10b981", font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, padx=16, pady=(22, 26))

        self.setup_project_selector(sidebar)

        # 1. BOTOES NAVEGAÇÃO SUPERIOR
        top_nav_items = [
            ("editor", "Editor"),
            ("worldbuilder", "WorldBuilders"),
            ("chat", "Converse com Ao"),
            ("options", "Opções"),
            ("models", "Performance IA"),
        ]
        for key, label in top_nav_items:
            btn = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda k=key: self.switch_page(k))
            btn.pack(fill=tk.X, padx=8, pady=2)
            self.nav_buttons[key] = btn

        # 2. ESPAÇADOR FLEXÍVEL (Empurra os itens abaixo para o rodapé)
        nav_spacer = tk.Frame(sidebar, bg="#0a0a0a")
        nav_spacer.pack(fill=tk.BOTH, expand=True)

        # 3. BOTOES NAVEGAÇÃO INFERIOR (No rodapé)
        bottom_nav_items = [
            ("log", "Log de Atividades"),
            ("manual", "📖 Manual & Guia"),
        ]
        for key, label in bottom_nav_items:
            btn = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda k=key: self.switch_page(k))
            btn.pack(fill=tk.X, padx=8, pady=2)
            self.nav_buttons[key] = btn

        zoom_frame = tk.Frame(sidebar, bg="#0a0a0a")
        zoom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 6))
        tk.Label(zoom_frame, text="Zoom:", bg="#0a0a0a", fg="#888888", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="A-", width=3, command=lambda: self.change_font_size(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="A+", width=3, command=lambda: self.change_font_size(1)).pack(side=tk.LEFT, padx=2)

        ttk.Separator(sidebar, orient="horizontal").pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=8)
        self.lbl_discord = tk.Label(sidebar, text="Discord: Starting...", bg="#0a0a0a", fg="#e3e3e3", font=("Segoe UI", 8, "bold"), anchor="w", justify="left", wraplength=175)
        self.lbl_discord.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(0, 4))

        content_area = ttk.Frame(root_container)
        content_area.grid(row=0, column=1, sticky="nsew")
        
        self.options_pane = st.OptionsFrame(
            content_area, 
            self.log_activity, 
            self.toast, 
            self._page_header
        )

        self.pages["editor"] = self._build_editor_page(content_area)
        self.pages["worldbuilder"] = self._build_worldbuilder_page(content_area)
        self.pages["chat"] = self._build_chat_page(content_area)
        self.pages["log"] = self._build_log_page(content_area)
        self.pages["options"] = self.options_pane
        self.pages["models"] = self._build_models_page(content_area)
        self.pages["manual"] = self._build_manual_page(content_area)  # 📖 Nova página de Manual

        for page in self.pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _page_header(self, parent, title, subtitle):
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=18, pady=(18, 10))
        ttk.Label(header, text=title, font=("Segoe UI", 14, "bold"), foreground="#10b981").pack(anchor=tk.W)
        ttk.Label(header, text=subtitle, font=("Segoe UI", 9), foreground="#888888").pack(anchor=tk.W, pady=(3, 0))

    def switch_page(self, name):
        if name not in self.pages:
            return
        if name == "models":
            self.refresh_models_cards()
        elif name == "chat":
            self.reload_chat_history() 
        self.pages[name].tkraise()
        self.current_page = name
        for key, btn in self.nav_buttons.items():
            btn.configure(style="NavActive.TButton" if key == name else "Nav.TButton")
            
    def reload_chat_history(self):
        """Carrega e formata as memórias salvas na pasta memories para a tela de chat."""
        guild_id = f"desktop_{pu.PASTA_PROJETO}"  # 🛡️ Isolado por projeto!
        guild_name = f"Console_{pu.PASTA_PROJETO}"
        userid = "999999"
        user_name = self.user_name

        memorias = me.carregar_memorias(guild_id, guild_name, userid, user_name)

        # Evita reprocessar se o texto de memória não sofreu alterações
        if hasattr(self, "_last_loaded_memory") and self._last_loaded_memory == memorias:
            return

        self._last_loaded_memory = memorias

        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)

        if not memorias or not memorias.strip():
            self.chat_display.insert(tk.END, "System: ", "System")
            self.chat_display.insert(tk.END, "Console local conectado. Nenhuma memória anterior encontrada.\n\n")
            self.chat_display.config(state=tk.DISABLED)
            return

        self.chat_display.insert(tk.END, "System: ", "System")
        self.chat_display.insert(tk.END, "--- Histórico de Memórias do Usuário Carregado ---\n\n")

        # Parse dos blocos de diálogo salvos
        import re
        parts = re.split(r'(Prompt Usuário:|Resposta:|Resumo de Memórias:)', memorias)

        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""

            if not content:
                continue

            if header == "Prompt Usuário:":
                self.chat_display.insert(tk.END, "You: ", "You")
                self.chat_display.insert(tk.END, f"{content}\n\n")
            elif header == "Resposta:":
                self.chat_display.insert(tk.END, "Ao: ", "Ao")
                self.chat_display.insert(tk.END, f"{content}\n\n")
            elif header == "Resumo de Memórias:":
                self.chat_display.insert(tk.END, "System: ", "System")
                self.chat_display.insert(tk.END, f"[Resumo de Diálogos Anteriores]: {content}\n\n")

        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # PÁGINAS DA INTERFACE
    # ------------------------------------------------------------------
    def _build_editor_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "Edição de Mundo", "Explore, edite e organize os arquivos do seu projeto.")
        self.explorer_pane = expl.ExplorerFrame(
            frame, 
            self.log_activity, 
            toast_callback=self.toast,
            auto_expander_callback=self.options_pane.is_auto_expander_enabled,
            ask_ao_callback=self.open_chat_with_file_context,
            stats_callback=self.update_editor_stats
        )
        self.explorer_pane.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        return frame

    def _build_worldbuilder_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "WorldBuilder & Expander", "Dispare ou interrompa tarefas de expansão automática do seu mundo.")

        # --- ÁREA DE ROLAGEM DINÂMICA (CANVAS + SCROLLBAR) ---
        self.wb_canvas = tk.Canvas(frame, bg="#121212", highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.wb_canvas.yview)

        self.wb_scroll_frame = ttk.Frame(self.wb_canvas)
        self.wb_scroll_frame.bind(
            "<Configure>",
            lambda e: self.wb_canvas.configure(scrollregion=self.wb_canvas.bbox("all"))
        )

        self.wb_canvas_window = self.wb_canvas.create_window((0, 0), window=self.wb_scroll_frame, anchor="nw")
        self.wb_canvas.configure(yscrollcommand=scrollbar.set)

        self.wb_canvas.bind("<Configure>", self._on_wb_canvas_resize)
        self.wb_canvas.bind_all("<MouseWheel>", lambda e: self.wb_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units") if self.current_page == "worldbuilder" else None)

        self.wb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=(0, 15))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=(0, 15))

        self.wb_boxes = []
        self.wb_last_rendered_cols = 0

        # --- QUADRO 1: Controle de Emergência ---
        stop_box = ttk.LabelFrame(self.wb_scroll_frame, text=" Controle de Emergência ")
        self.btn_stop = ttk.Button(stop_box, text="⛔⛔ PARAR QUALQUER EXECUÇÃO ATUAL ⛔⛔", command=self.stop_all_tasks)
        self.btn_stop.pack(fill=tk.X, padx=10, pady=10)

        # --- QUADRO 2: Expander ---
        expander_box = ttk.LabelFrame(self.wb_scroll_frame, text=" Expander (preenche lacunas marcadas com TO DO) ")
        self.btn_expander = ttk.Button(expander_box, text="▶ Executar Tarefa do Expander", command=self.start_expander_thread)
        self.btn_expander.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.lbl_expander = ttk.Label(expander_box, text="Status: Inativo")
        self.lbl_expander.pack(anchor=tk.W, padx=10, pady=(0, 8))
        self.btn_rebuild_context = ttk.Button(expander_box, text="▶ Reconstruir Contexto do Mundo", command=self.rebuild_world_context)
        self.btn_rebuild_context.pack(fill=tk.X, padx=10, pady=(0, 10))

        # --- QUADRO 3: WorldBuilder ---
        wb_box = ttk.LabelFrame(self.wb_scroll_frame, text=" WorldBuilder (planeja e executa expansão autônoma) ")
        ttk.Label(wb_box, text="Objetivo:").pack(anchor=tk.W, padx=10, pady=(10, 2))
        self.worldbuilder_objective = tk.StringVar(value="Completar o Projeto")
        self.objective_entry = ttk.Entry(wb_box, textvariable=self.worldbuilder_objective)
        self.objective_entry.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.btn_worldbuilder = ttk.Button(wb_box, text="▶ Executar WorldBuilder", command=self.start_worldbuilder_thread)
        self.btn_worldbuilder.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.lbl_worldbuilder = ttk.Label(wb_box, text="Status: Inativo")
        self.lbl_worldbuilder.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # --- QUADRO 4: Auditoria de Lore ---
        audit_box = ttk.LabelFrame(self.wb_scroll_frame, text=" Auditoria e Consistência ")
        self.btn_audit_lore = ttk.Button(
            audit_box, 
            text="▶ Auditar Lore do Mundo (Buscar Incoerências)", 
            command=self.start_lore_audit_thread
        )
        self.btn_audit_lore.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.lbl_audit = ttk.Label(audit_box, text="Status: Inativo")
        self.lbl_audit.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # --- QUADRO 5: Exportação do Cenário ---
        export_box = ttk.LabelFrame(self.wb_scroll_frame, text=" Exportação do Cenário ")
        self.btn_export_book = ttk.Button(export_box, text="▶ Gerar e Abrir Livro do Cenário (HTML/PDF)", command=self.export_sourcebook)
        self.btn_export_book.pack(fill=tk.X, padx=10, pady=10)

        # --- QUADRO 6: Gerenciamento do Projeto ---
        db_box = ttk.LabelFrame(self.wb_scroll_frame, text=" Gerenciamento do Projeto ")
        self.btn_create_backup = ttk.Button(db_box, text="▶ Criar Backup Completo (.zip)", command=self.create_backup)
        self.btn_create_backup.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.btn_delete_memories = ttk.Button(db_box, text="⛔ Excluir Todas as Memórias ⛔", command=self.delete_memories)
        self.btn_delete_memories.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.wb_boxes = [stop_box, audit_box, expander_box, export_box, wb_box, db_box]
        self.render_wb_grid()

        return frame

    def _on_wb_canvas_resize(self, event):
        """Ajusta a largura interna do container de acordo com o tamanho da janela."""
        canvas_width = event.width
        if hasattr(self, "wb_canvas_window"):
            self.wb_canvas.itemconfig(self.wb_canvas_window, width=canvas_width)
        self.render_wb_grid()

    def render_wb_grid(self):
        """Redesenha o grid de caixas em 1 ou 2 colunas conforme a largura disponível."""
        canvas_width = self.wb_canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 800

        num_cols = 2 if canvas_width >= 720 else 1

        if self.wb_last_rendered_cols == num_cols:
            return
        self.wb_last_rendered_cols = num_cols

        for c in range(2):
            self.wb_scroll_frame.columnconfigure(c, weight=1 if c < num_cols else 0)

        for idx, box in enumerate(self.wb_boxes):
            box.grid_forget()
            if num_cols == 2:
                row = idx // 2
                col = idx % 2
            else:
                row = idx
                col = 0
            box.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
    
    def _build_chat_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "Conversa com Ao", "Fale diretamente com Ao sobre o seu mundo.")
        
        # 🛡️ Ancorado no BOTTOM PRIMEIRO para nunca ser empurrado para fora da tela
        input_frame = ttk.Frame(frame)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(0, 15))

        self.input_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda event: self.send_chat_message())
        self.send_button = ttk.Button(input_frame, text="Enviar", command=self.send_chat_message)
        self.send_button.pack(side=tk.RIGHT)

        # O display de texto ocupa o restante do espaço superior
        self.chat_display = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 10),
            bg="#1e1e1e", fg="#e3e3e3", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )

        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        self.chat_display.tag_config("You", foreground="#60a5fa", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("Ao", foreground="#34d399", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("System", foreground="#888888", font=("Segoe UI", 9, "italic"))
        self.chat_display.tag_config("Thinking", foreground="#f59e0b", font=("Segoe UI", 9, "italic"))

        self.append_to_chat("System", "Console local conectado. Digite sua mensagem abaixo.")
        return frame

    def _build_log_page(self, parent):
        frame = ttk.Frame(parent)
        sys.stdout = gl.GuiOutput(self.log_activity)
        sys.stderr = gl.GuiOutput(self.log_activity)
        self._page_header(frame, "Log de Atividade", "Histórico técnico de tudo que está acontecendo em segundo plano.")
        self.log_display = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9),
            bg="#1e1e1e", fg="#cccccc", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        return frame

    # ------------------------------------------------------------------
    # AUDITORIA DE LORE (NÃO-BLOQUEANTE)
    # ------------------------------------------------------------------
    def start_lore_audit_thread(self):
        if self.audit_running:
            messagebox.showwarning("Aviso", "A auditoria de lore já está em execução.")
            return

        pu.reset_cancellation()
        self.audit_running = True
        self.btn_audit_lore.config(state=tk.DISABLED)
        self.lbl_audit.config(text="Status: Auditando e reconstruindo contexto...", foreground="#60a5fa")
        self.toast("Recriando bundle e iniciando Auditoria de Lore...")
        self.log_activity("Iniciando auditoria de lore...")
        
        self.explorer_pane.save_current_file()
        self.start_spinner("Auditando Lore do Mundo")
        threading.Thread(target=self.run_lore_audit_task, daemon=True).start()

    def run_lore_audit_task(self):
        try:
            # 1. Imediatamente refaz o bundle do mundo
            self.log_activity("Reconstruindo bundle do contexto para a auditoria...")
            cg.force_rebuild_world_context()
            self.log_activity("Bundle recriado com sucesso. Enviando para o Gemini...")

            if pu.is_cancelled():
                self.finished_audit_ui_update("Cancelado pelo Usuário")
                return

            # 2. Prompt rigoroso de auditoria
            system_instruction = (
                "Você é um Mestre de RPG veterano, Editor de Worldbuilding e Auditor de Lore meticuloso.\n"
                "Seu objetivo é analisar todo o projeto de lore fornecido no contexto e identificar incoerências, "
                "contradições históricas, furos de roteiro, erros de cronologia e conceitos órfãos."
            )

            prompt_auditoria = f"""
Por favor, realize uma auditoria rigorosa no projeto de lore armazenado no contexto.

ANALISE CUIDADOSAMENTE:
1. CONTRADIÇÕES HISTÓRICAS E CRONOLÓGICAS (ex: personagens ativos em datas posteriores à sua morte ou em locais distantes).
2. CONFLITOS GEOGRÁFICOS E LOCAIS (ex: locais descritos como inóspitos sem justificativa para grandes populações).
3. RELAÇÕES E MOTIVAÇÕES INCOERENTES DE NPCS/FACÇÕES (ex: alianças impossíveis sem contexto).
4. CONCEITOS ÓRFÃOS OU INCOMPLETOS (elementos citados em um arquivo mas nunca desenvolvidos).

FORMATO DA RESPOSTA (Markdown):
# 🛡️ Relatório de Auditoria de Lore - {pu.PASTA_PROJETO}

## ⚠️ Incoerências e Contradições Encontradas
- **[Nome do Arquivo / Tópico]**: Descrição da incoerência e sugestão de correção.

## 🔍 Alertas de Cronologia e Geografia
- **[Nome do Arquivo / Tópico]**: Descrição da inconsistência.

## 💡 Oportunidades de Expansão (Elementos Órfãos)
- **[Nome do Arquivo / Tópico]**: Conceito mencionado que precisa de desenvolvimento.

Se o universo estiver 100% coerente, elogie a consistência da lore!
"""

            # Executa com baixa temperatura (0.2) para ser altamente analítico
            relatorio = au.ask_ai(
                contents=prompt_auditoria,
                system_instruction=system_instruction,
                temperature=0.2,
                use_world_context=True
            )

            if relatorio:
                self.log_activity("Auditoria de Lore concluída!")
                self.root.after(0, lambda: self.show_audit_report_window(relatorio))
                self.finished_audit_ui_update("Concluído")
                self.toast("✅ Auditoria de Lore concluída!")
            else:
                self.log_activity("A auditoria não retornou resultados.")
                self.finished_audit_ui_update("Falhou (Sem resposta)")

        except Exception as e:
            self.log_activity(f"Erro na auditoria de lore: {e}")
            self.finished_audit_ui_update("Falhou (Erro)")
            self.toast("❌ Erro ao auditar a lore.")

    def finished_audit_ui_update(self, status):
        self.stop_spinner(f"Auditoria: {status}")
        self.audit_running = False
        self.root.after(0, lambda: self.btn_audit_lore.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.lbl_audit.config(text=f"Status: {status}", foreground="#e3e3e3"))

    def show_audit_report_window(self, report_text):
        """Abre uma janela modal flutuante estilizada exibindo o relatório de auditoria."""
        popup = tk.Toplevel(self.root)
        popup.title(f"Relatório de Auditoria - {pu.PASTA_PROJETO}")
        popup.geometry("850x650")
        popup.minsize(600, 400)
        popup.configure(bg="#121212")

        header = tk.Frame(popup, bg="#121212")
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="🛡️ Relatório de Auditoria de Lore", font=("Segoe UI", 12, "bold"), bg="#121212", fg="#10b981").pack(anchor=tk.W)

        display = scrolledtext.ScrolledText(
            popup, wrap=tk.WORD, font=("Consolas", 10),
            bg="#1e1e1e", fg="#e3e3e3", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )
        display.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        display.insert("1.0", report_text)

        botoes_frame = tk.Frame(popup, bg="#121212")
        botoes_frame.pack(fill=tk.X, padx=15, pady=10)

        def _salvar_relatorio():
            caminho_export = filedialog.asksaveasfilename(
                initialdir=Path.cwd() / "exports",
                initialfile=f"Auditoria_Lore_{pu.PASTA_PROJETO}.md",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")]
            )
            if caminho_export:
                try:
                    with open(caminho_export, "w", encoding="utf-8") as f:
                        f.write(report_text)
                    self.toast("💾 Relatório salvo com sucesso!")
                except Exception as e:
                    messagebox.showerror("Erro ao Salvar", str(e))

        ttk.Button(botoes_frame, text="💾 Salvar Relatório (.md)", command=_salvar_relatorio).pack(side=tk.LEFT)
        ttk.Button(botoes_frame, text="Fechar", command=popup.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # CHAT CONTEXTUAL
    # ------------------------------------------------------------------
    def open_chat_with_file_context(self, caminho):
        try:
            nome_arq = os.path.basename(caminho)
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
                
            self.chat_attached_file = {
                "name": nome_arq,
                "content": conteudo
            }


            self.switch_page("chat")
            
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, f"Analise o arquivo '{nome_arq}' e me ajude com o seguinte: ")
            self.input_entry.focus_set()

            self.toast(f"Contexto de '{nome_arq}' carregado na conversa!")
            self.log_activity(f"Carregado arquivo '{nome_arq}' para o chat com Ao.")
        except Exception as e:
            self.log_activity(f"Erro ao carregar arquivo no chat: {e}")
            self.toast("❌ Falha ao carregar o arquivo no chat.")

    def append_to_chat(self, sender, text, tag=None):
        self.chat_display.config(state=tk.NORMAL)
        sender_tag = tag if tag else sender
        self.chat_display.insert(tk.END, f"{sender}: ", sender_tag)
        self.chat_display.insert(tk.END, f"{text}\n\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def show_thinking(self):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "Ao: ", "Ao")
        self.chat_display.insert(tk.END, "Pensando... 🧠\n\n", "Thinking")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def remove_thinking_and_respond(self, text):
        self.chat_display.config(state=tk.NORMAL)
        try:
            ranges = self.chat_display.tag_ranges("Thinking")
            if ranges:
                start = ranges[0]
                line_start = self.chat_display.index(f"{start} linestart")
                self.chat_display.delete(line_start, tk.END)
        except Exception as e:
            print(f"Erro ao remover indicador de pensamento: {e}")

        self.chat_display.config(state=tk.DISABLED)
        self.append_to_chat("Ao", text)

    def send_chat_message(self):
        prompt = self.input_entry.get().strip()
        if not prompt:
            return
        self.input_entry.delete(0, tk.END)
        self.append_to_chat("You", prompt)
        self.show_thinking()
        self.explorer_pane.save_current_file()
        threading.Thread(target=self.query_ao_api, args=(prompt,), daemon=True).start()

    def query_ao_api(self, prompt):
        try:
            guild_id = f"desktop_{pu.PASTA_PROJETO}"  
            guild_name = f"Console_{pu.PASTA_PROJETO}"
            userid = "999999"
            user_name = self.user_name

            persona = (
                "- Você é um mestre de mesa chamado Ao, focado em aventuras de D&D.\n"
                "- Você se diverte criando situações e aventuras engajantes para jogadores e aventureiros.\n"
                "- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas."
            )
            regras = (
                "- Não faça julgamentos de valor;\n"
                "- Pode criar histórias e lugares fictícios, mas não altere informações já definidas, exceto se isso for pedido diretamente;\n"
            )

            memorias = me.carregar_memorias(guild_id, guild_name, userid, user_name)
            self.log_activity("Consultando Gemini...")

            system_instruction = f"{persona}\n\n{regras}"
            conteudo_prompt = ""
            
            # 🛡️ Injeta o conteúdo do arquivo anexado no prompt enviado ao Gemini
            if hasattr(self, "chat_attached_file") and self.chat_attached_file:
                arq = self.chat_attached_file
                conteudo_prompt += f"--- ARQUIVO ANEXADO PELO USUÁRIO ({arq['name']}) ---\n{arq['content']}\n\n"
                self.chat_attached_file = None  # Reseta o anexo após o envio
            
            
            if memorias:
                conteudo_prompt += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
            conteudo_prompt += f"--- MENSAGEM DO USUÁRIO ---\n{prompt}"

            resposta = ag.ask_ai(
                contents=conteudo_prompt,
                system_instruction=system_instruction,
                temperature=0.6,
                use_world_context=True
            )

            if resposta:
                finalz = [".", "!", "?"]
                if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
                    resposta = me.trim_incomplete_sentences(resposta)

                self.root.after(0, lambda: self.remove_thinking_and_respond(resposta))
                me.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta)
                self.log_activity("Interação salva na memória.")
            else:
                self.root.after(0, lambda: self.remove_thinking_and_respond("Não foi possível obter resposta."))

        except Exception as e:
            self.root.after(0, lambda err=str(e): self.remove_thinking_and_respond(f"Erro de execução: {err}"))

    # ------------------------------------------------------------------
    # TAREFAS DE BACKGROUND E EVENTOS
    # ------------------------------------------------------------------
    def start_expander_thread(self):
        if self.expander_running:
            messagebox.showwarning("Aviso", "O Expander já está em execução.")
            return
        pu.reset_cancellation()
        self.expander_running = True
        self.btn_expander.config(state=tk.DISABLED)
        self.lbl_expander.config(text="Status: Executando...", foreground="#60a5fa")
        self.toast("▶️ Expander iniciado em segundo plano...")
        self.log_activity("Iniciando tarefa do Expander...")

        self.explorer_pane.save_current_file()
        self.start_spinner("Expander em execução")
        threading.Thread(target=self.run_expander_task, daemon=True).start()

    def run_expander_task(self):
        try:
            ex.processar_arquivos()
            self.log_activity("Processo do Expander concluído.")
            self.finished_expander_ui_update("Tarefa Concluída")
            self.toast("✅ Expander finalizado com sucesso!")
        except Exception as e:
            self.log_activity(f"Erro no Expander: {e}")
            self.finished_expander_ui_update("Falhou (Erro)")
            self.toast("❌ Erro na execução do Expander.")

    def finished_expander_ui_update(self, status):
        self.expander_running = False
        self.stop_spinner(f"Expander: {status}")
        self.root.after(0, self._safe_finished_expander, status)

    def _safe_finished_expander(self, status):
        self.btn_expander.config(state=tk.NORMAL)
        self.lbl_expander.config(text=f"Status: {status}", foreground="#e3e3e3")
        self.explorer_pane.refresh_tree()

    def rebuild_world_context(self):
        self.toast("🌐 Reconstruindo contexto do mundo...")
        threading.Thread(target=self._rebuild_world_context_worker, daemon=True).start()

    def _rebuild_world_context_worker(self):
        try:
            self.log_activity("Reconstruindo contexto do mundo...")
            contexto = cg.force_rebuild_world_context()
            self.log_activity(f"Contexto recriado com sucesso: {contexto['id']}")
            self.toast("✅ Contexto do Mundo reconstruído!")
        except Exception as e:
            self.log_activity(f"Falha ao reconstruir contexto: {e}")
            self.toast("❌ Erro ao recriar contexto.")

    def start_worldbuilder_thread(self):
        self.worldbuilder_objective_value = self.worldbuilder_objective.get().strip()
        if not self.worldbuilder_objective_value:
            self.worldbuilder_objective_value = "Completar o Projeto"

        if self.worldbuilder_running:
            messagebox.showwarning("Aviso", "O WorldBuilder já está em execução.")
            return
        pu.reset_cancellation()
        self.worldbuilder_running = True
        self.btn_worldbuilder.config(state=tk.DISABLED)
        self.lbl_worldbuilder.config(text="Status: Executando...", foreground="#60a5fa")
        self.toast("WorldBuilder iniciado...")
        self.log_activity("Iniciando WorldBuilder autônomo...")

        self.explorer_pane.save_current_file()
        self.start_spinner("WorldBuilder em execução")
        threading.Thread(target=self.run_worldbuilder_task, daemon=True).start()

    def run_worldbuilder_task(self):
        try:
            objective = self.worldbuilder_objective_value
            
            wb.taskplanner(objective)

            self.log_activity("WorldBuilder concluído com sucesso.")
            self.finished_worldbuilder_ui_update("Tarefa Concluída")
            self.toast("✅ WorldBuilder finalizou todas as etapas!")
        except Exception as e:
            self.log_activity(f"Erro no WorldBuilder: {e}")
            self.finished_worldbuilder_ui_update("Falhou (Erro)")
            self.toast("❌ Erro na execução do WorldBuilder.")

    def finished_worldbuilder_ui_update(self, status):
        self.worldbuilder_running = False
        self.stop_spinner(f"WorldBuilder: {status}")
        self.root.after(0, self._safe_finished_worldbuilder, status)

    def _safe_finished_worldbuilder(self, status):
        self.btn_worldbuilder.config(state=tk.NORMAL)
        self.lbl_worldbuilder.config(text=f"Status: {status}", foreground="#e3e3e3")
        self.explorer_pane.refresh_tree()

    def delete_memories(self):
        resposta = messagebox.askyesno("Confirmar", "Deseja realmente excluir todas as memórias?")
        if not resposta:
            return
        try:
            me.delete_all_memories()
            
            # 🛡️ Limpa a memória interna e força a atualização do chat
            if hasattr(self, "_last_loaded_memory"):
                self._last_loaded_memory = None
            self.reload_chat_history()

            self.log_activity("Todas as memórias foram removidas.")
            self.toast("🗑️ Memórias apagadas com sucesso.")
            messagebox.showinfo("Concluído", "Todas as memórias foram excluídas.")
        except Exception as e:
            self.log_activity(f"Erro ao excluir memórias: {e}")
            messagebox.showerror("Erro", str(e))

    # ------------------------------------------------------------------
    # CONTROLE DE LOGS E ZOOM
    # ------------------------------------------------------------------
    def setup_shortcuts(self):
        self.root.bind("<Control-KeyPress-equal>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-plus>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-minus>", lambda e: self.change_font_size(-1))
        self.root.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.root.bind("<Control-Button-4>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-Button-5>", lambda e: self.change_font_size(-1))

    def _on_ctrl_mousewheel(self, event):
        if event.delta > 0:
            self.change_font_size(1)
        elif event.delta < 0:
            self.change_font_size(-1)

    def change_font_size(self, delta):
        self.current_font_size = max(8, min(24, self.current_font_size + delta))
        self.chat_display.configure(font=("Segoe UI", self.current_font_size))
        self.explorer_pane.update_editor_font(self.current_font_size)

    def log_activity(self, message):
        self.root.after(0, self._safe_log_activity, message)

    def _safe_log_activity(self, message):
        self.log_display.config(state=tk.NORMAL)
        self.log_display.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_display.see(tk.END)
        self.log_display.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # BOT DO DISCORD
    # ------------------------------------------------------------------
    def start_discord_bot_thread(self):
        threading.Thread(target=self.run_discord_bot, daemon=True).start()

    def run_discord_bot(self):
        loop = None
        try:
            token = os.getenv("DISCORD_TOKEN", "").strip()
            if not token:
                self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Desativado", fg="#888888"))
                return

            self.log_activity("Iniciando bot do Discord em segundo plano...")
            from bot.dbot import discordclient

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.discord_loop = loop

            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Online", fg="#10b981"))
            self.log_activity("Instância do Discord online.")

            loop.run_until_complete(discordclient.start(token))

        except Exception as e:
            self.log_activity(f"Exceção no Discord: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Offline/Erro", fg="#ef4444"))

    def on_closing(self):
        self.log_activity("Encerrando aplicativo... salvando arquivos...")
        self.explorer_pane.save_current_file()
        try:
            if hasattr(self, "discord_loop") and self.discord_loop and self.discord_loop.is_running():
                from bot.dbot import discordclient
                future = asyncio.run_coroutine_threadsafe(discordclient.close(), self.discord_loop)
                try:
                    future.result(timeout=3)
                except Exception:
                    pass
        except Exception as e:
            print(f"Encerramento do Discord: {e}")
        finally:
            self.root.destroy()

    # ------------------------------------------------------------------
    # PARAR EXECUÇÕES
    # ------------------------------------------------------------------
    def stop_all_tasks(self):
        pu.request_cancellation()
        self.log_activity("🛑 Solicitação de interrupção enviada pelo usuário...")
        self.toast("🛑 Interrompendo tarefas em execução...")

    # ------------------------------------------------------------------
    # COMPILADOR DE LIVRO (HTML/PDF)
    # ------------------------------------------------------------------
    def export_sourcebook(self):
        def _run_compile():
            self.start_spinner("Compilador em execução")
            try:
                self.log_activity("Iniciando compilação do Livro do Cenário...")
                self.toast("Compilando Livro do Cenário...")
                
                
                caminho_html = comp.compilar_livro_cenario()
                if caminho_html and caminho_html.exists():
                    self.log_activity(f"Livro gerado em: {caminho_html.name}")
                    self.toast("✅ Livro compilado com sucesso! Abrindo...")
                    self.stop_spinner(f"Compilador: Concluído!")
                    os.startfile(str(caminho_html))
                else:
                    self.toast("❌ Falha ao compilar o livro.")
            except Exception as e:
                self.log_activity(f"Erro na compilação do livro: {e}")
                self.toast("❌ Erro ao compilar o livro.")

        threading.Thread(target=_run_compile, daemon=True).start()

    # ------------------------------------------------------------------
    # Backup full do projeto
    # ------------------------------------------------------------------
    def create_backup(self):
        def _run_backup():
            try:
                self.log_activity("Iniciando criação de backup completo do projeto...")
                self.toast("Compactando arquivos em backup.zip...")
                caminho_zip, num_arquivos = pu.criar_backup_projeto()
                msg = (
                    f"Backup concluído com sucesso!\n\n"
                    f"Total de arquivos incluídos: {num_arquivos}\n"
                    f"Salvo em: {caminho_zip}")
                self.log_activity(f"Backup gerado: {caminho_zip} ({num_arquivos} arquivos)")
                self.toast(f"✅ Backup salvo em: {caminho_zip.name}")
                self.root.after(0, lambda: messagebox.showinfo("Backup Concluído", msg))
            except Exception as e:
                self.log_activity(f"Erro ao criar backup: {e}")
                self.toast("Erro ao criar o backup.")
                self.root.after(0, lambda err=str(e): messagebox.showerror("Erro no Backup", err))
        threading.Thread(target=_run_backup, daemon=True).start()
    
    # ------------------------------------------------------------------
    # Seletor de projetos secundários
    # ------------------------------------------------------------------
    def setup_project_selector(self, parent_frame):
        """Cria a caixa de seleção de projetos na barra lateral."""
        project_frame = tk.Frame(parent_frame, bg="#0a0a0a")
        project_frame.pack(fill=tk.X, padx=12, pady=(0, 15))

        tk.Label(
            project_frame, 
            text="PROJETO ATIVO:", 
            bg="#0a0a0a", 
            fg="#888888", 
            font=("Segoe UI", 8, "bold")
        ).pack(anchor=tk.W, pady=(0, 2))

        select_row = tk.Frame(project_frame, bg="#0a0a0a")
        select_row.pack(fill=tk.X)

        self.recentes_map = {Path(p).name: p for p in pu.obter_projetos_recentes()}
        
        self.combo_projetos = ttk.Combobox(
            select_row, 
            state="readonly", 
            values=list(self.recentes_map.keys()),
            font=("Segoe UI", 9)
        )
        if pu.PASTA_PROJETO in self.recentes_map:
            self.combo_projetos.set(pu.PASTA_PROJETO)
        else:
            self.combo_projetos.set(pu.PASTA_PROJETO)
            
        self.combo_projetos.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.combo_projetos.bind("<<ComboboxSelected>>", self._on_project_selected)

        btn_browse = ttk.Button(
            select_row, 
            text="📁", 
            width=3, 
            command=self.browse_open_project
        )
        btn_browse.pack(side=tk.RIGHT)

    def _on_project_selected(self, event):
        nome_sel = self.combo_projetos.get()
        caminho_completo = self.recentes_map.get(nome_sel)
        if caminho_completo:
            self.switch_to_project(caminho_completo)

    def browse_open_project(self):
        pasta_escolhida = filedialog.askdirectory(
            title="Selecione ou Crie a Pasta de um Projeto de Lore",
            initialdir=str(pu.CAMINHO_PROJETO.parent)
        )
        if pasta_escolhida:
            self.switch_to_project(pasta_escolhida)

    def switch_to_project(self, caminho_novo):
        try:
            self.explorer_pane.save_current_file()
            pu.definir_projeto_ativo(caminho_novo)
            
            # Recarrega mapa de recentes no dropdown
            self.recentes_map = {Path(p).name: p for p in pu.obter_projetos_recentes()}
            self.combo_projetos["values"] = list(self.recentes_map.keys())
            self.combo_projetos.set(pu.PASTA_PROJETO)

            # Atualiza a árvore do Explorer e recria o cache da IA para o novo mundo
            self.explorer_pane.refresh_tree()
            self.rebuild_world_context()

            self.log_activity(f"Projeto alternado para: {pu.CAMINHO_PROJETO}")
            self.lbl_status_project.config(text=f"Projeto: {pu.PASTA_PROJETO}")
            self.toast(f"🌐 Mundo alterado para '{pu.PASTA_PROJETO}'!")
        except Exception as e:
            self.log_activity(f"Erro ao alternar de projeto: {e}")
            messagebox.showerror("Erro de Projeto", f"Falha ao abrir projeto: {e}")

    # ------------------------------------------------------------------
    # Spinner + Barra de Status
    # ------------------------------------------------------------------
    def setup_status_bar(self):
        """Cria a barra de status fixa na base do aplicativo."""
        self.status_bar = tk.Frame(self.root, bg="#0a0a0a", height=28)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Esquerda: Projeto Ativo
        self.lbl_status_project = tk.Label(
            self.status_bar, 
            text=f"Projeto: {pu.PASTA_PROJETO}", 
            bg="#0a0a0a", fg="#10b981", font=("Segoe UI", 9)
        )
        self.lbl_status_project.pack(side=tk.LEFT, padx=12)

        ttk.Separator(self.status_bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, pady=4)

        # Centro: Estatísticas de Palavras / Linhas
        self.lbl_status_stats = tk.Label(
            self.status_bar, 
            text="NENHUM ARQUIVO SELECIONADO", 
            bg="#0a0a0a", fg="#888888", font=("Segoe UI", 9)
        )
        self.lbl_status_stats.pack(side=tk.LEFT, padx=12)

        # Direita: Indicador Dinâmico de Tarefas (Spinner)
        self.lbl_status_task = tk.Label(
            self.status_bar, 
            text="PRONTO", 
            bg="#0a0a0a", fg="#10b981", font=("Segoe UI", 9, "bold")
        )
        self.lbl_status_task.pack(side=tk.RIGHT, padx=12)

    def start_spinner(self, task_name="Executando..."):
        """Inicia a animação do círculo giratório."""
        self.spinner_running = True
        # Animação em círculos geométricos suaves
        self.spinner_frames = ["◐", "◓", "◑", "◒"]
        self.spinner_idx = 0
        self._animate_spinner(task_name)

    def _animate_spinner(self, task_name):
        if not getattr(self, "spinner_running", False):
            return
        char = self.spinner_frames[self.spinner_idx % len(self.spinner_frames)]
        self.spinner_idx += 1
        self.lbl_status_task.config(
            text=f"{char} {task_name.upper()}", 
            fg="#60a5fa"
        )
        self.root.after(90, lambda: self._animate_spinner(task_name))

    def stop_spinner(self, final_msg="PRONTO", is_error=False):
        """Para a animação do círculo."""
        self.spinner_running = False
        color = "#ef4444" if is_error else "#10b981"
        self.lbl_status_task.config(text=final_msg.upper(), fg=color)

    def update_editor_stats(self, words, chars, lines, tokens):
        """Atualiza a contagem de palavras da barra de status."""
        self.lbl_status_stats.config(
            text=f"PALAVRAS: {words:,}  |  CARACTERES: {chars:,}  |  LINHAS: {lines:,}  |  ~TOKENS: {tokens:,}",
            fg="#e3e3e3"
        )

    # ------------------------------------------------------------------
    # Reduzindo Uso de memória para o Bot
    # ------------------------------------------------------------------
    def trim_memory(self):
        """Força o Windows a liberar a memória RAM inativa do programa."""
        if sys.platform == 'win32':
            try:
                # Obtém o identificador do processo do programa no Windows
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                # Esvazia a memória de trabalho inativa
                ctypes.windll.psapi.EmptyWorkingSet(handle)
            except Exception as e:
                print(f"Erro ao otimizar RAM: {e}")

    # ------------------------------------------------------------------
    # BANDEJA DO SISTEMA (SYSTEM TRAY)
    # ------------------------------------------------------------------
    def setup_system_tray(self):
        """Inicializa o ícone oculto ao lado do relógio do Windows."""
        try:
            icon_path = pu.BASE_DIR / "icon.ico"
            if icon_path.exists():
                image = Image.open(icon_path)
            else:
                image = Image.new('RGB', (64, 64), color=(16, 185, 129))

            # Menu de contexto ao clicar com o botão direito no ícone do relógio
            menu = pystray.Menu(
                item('Abrir Silent Console', self.restore_from_tray, default=True),
                pystray.Menu.SEPARATOR,
                item('Encerrar Completamente', self.quit_app_completely)
            )

            self.tray_icon = pystray.Icon(
                "SilentMultiverse",
                image,
                "Silent Multiverse Nexus (Bot Ativo)",
                menu
            )

            # Executa o ícone da bandeja em uma thread separada
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"Erro ao inicializar System Tray: {e}")

    def minimize_to_tray(self):
        """Oculta a janela principal para a bandeja em vez de encerrar o programa."""
        self.explorer_pane.save_current_file()
        self.root.withdraw()  # Esconde a janela do Tkinter da barra de tarefas
        self.toast("O bot continua rodando minimizado!")
        self.trim_memory()

    def restore_from_tray(self, icon=None, item=None):
        """Restaura a janela principal a partir da bandeja."""
        self.root.after(0, self._safe_restore)

    def _safe_restore(self):
        self.root.deiconify()  # Exibe a janela novamente
        self.root.state("zoomed")
        self.root.lift()
        self.root.focus_force()

    def quit_app_completely(self, icon=None, item=None):
        """Encerra o programa e o bot do Discord definitivamente."""
        self.log_activity("Encerrando aplicativo definitivamente via System Tray...")
        
        # Para o ícone da bandeja
        if hasattr(self, "tray_icon") and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # Para o bot do Discord e limpa recursos
        try:
            if hasattr(self, "discord_loop") and self.discord_loop and self.discord_loop.is_running():
                from bot.dbot import discordclient
                future = asyncio.run_coroutine_threadsafe(discordclient.close(), self.discord_loop)
                try:
                    future.result(timeout=3)
                except Exception:
                    pass
        except Exception as e:
            print(f"Encerramento do Discord: {e}")
        finally:
            self.root.after(0, self.root.destroy)
            
    # ------------------------------------------------------------------
    # ABA DE PERFORMANCE DE MODELOS GEMINI (RESPONSIVE DASHBOARD)
    # ------------------------------------------------------------------
    def _build_models_page(self, parent):
        frame = ttk.Frame(parent)
        
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, padx=18, pady=(18, 10))
        
        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="Performance dos Modelos IA", font=("Segoe UI", 14, "bold"), foreground="#10b981").pack(anchor=tk.W)
        ttk.Label(title_box, text="Dashboard responsivo dos modelos Gemini testados e classificados por eficiência.", font=("Segoe UI", 9), foreground="#888888").pack(anchor=tk.W, pady=(3, 0))
        
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)

        btn_run_test = ttk.Button(btn_frame, text="⚡ Testar Modelos Agora", command=self.run_findmodel_thread)
        btn_run_test.pack(side=tk.LEFT, padx=(0, 5))

        btn_refresh = ttk.Button(btn_frame, text="🔄 Atualizar Tela", command=self.refresh_models_cards)
        btn_refresh.pack(side=tk.LEFT)

        # Área de rolagem vertical (Canvas + Scrollbar)
        self.models_canvas = tk.Canvas(frame, bg="#121212", highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.models_canvas.yview)
        
        self.models_scroll_frame = ttk.Frame(self.models_canvas)
        self.models_scroll_frame.bind(
            "<Configure>",
            lambda e: self.models_canvas.configure(scrollregion=self.models_canvas.bbox("all"))
        )
        
        self.models_canvas_window = self.models_canvas.create_window((0, 0), window=self.models_scroll_frame, anchor="nw")
        self.models_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.models_canvas.bind("<Configure>", self._on_models_canvas_resize)
        self.models_canvas.bind_all("<MouseWheel>", lambda e: self.models_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units") if self.current_page == "models" else None)

        self.models_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=(0, 15))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=(0, 15))

        self.current_models_list = []
        self.last_rendered_cols = 0

        return frame

    def _on_models_canvas_resize(self, event):
        """Redimensiona o container e recalcula o grid quando a janela muda de tamanho."""
        canvas_width = event.width
        if hasattr(self, "models_canvas_window"):
            self.models_canvas.itemconfig(self.models_canvas_window, width=canvas_width)
        if hasattr(self, "current_models_list") and self.current_models_list:
            self.render_models_grid(force=False)

    def run_findmodel_thread(self):
        """Executa o teste de pings e capacidade nos modelos em segundo plano."""
        if not os.getenv("GOOGLE_API_KEY", "").strip():
            self.toast("⚠️ Cadastre a GOOGLE_API_KEY nas Opções primeiro!")
            return

        self.toast("⚡ Testando e ranqueando modelos do Gemini...")
        self.log_activity("Iniciando benchmark de modelos da API...")
        self.start_spinner("Testando Modelos IA")

        def _worker():
            try:
                ag.findmodel()
                self.log_activity("Benchmark de modelos concluído com sucesso!")
                self.toast("✅ Teste de modelos concluído!")
                self.root.after(0, self.refresh_models_cards)
            except Exception as e:
                self.log_activity(f"Erro ao testar modelos: {e}")
                self.toast("❌ Erro ao testar modelos.")
            finally:
                self.stop_spinner("Modelos Prontos")

        threading.Thread(target=_worker, daemon=True).start()

    def refresh_models_cards(self):
        file_path = pu.log_path("models.json")
        has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())

        if not has_key:
            self._show_models_message(
                "🔑 Nenhuma chave de API (GOOGLE_API_KEY) cadastrada.\n\n"
                "Para visualizar e ranquear os modelos disponíveis do Gemini,\n"
                "acesse a aba 'Opções' no menu lateral e salve sua chave de API."
            )
            return

        self.current_models_list = pu.ler_json_seguro(file_path, pu.LOCK_MODELS, padrao=[])

        if not self.current_models_list:
            self._show_models_message(
                "⏳ Nenhum teste de modelos foi executado ainda.\n\n"
                "Clique no botão '⚡ Testar Modelos Agora' no topo direito\n"
                "para disparar o benchmark dos modelos disponíveis do Gemini."
            )
            return

        self.render_models_grid(force=True)

    def _show_models_message(self, mensagem):
        for widget in self.models_scroll_frame.winfo_children():
            widget.destroy()
        lbl = tk.Label(
            self.models_scroll_frame, 
            text=mensagem, 
            bg="#121212", 
            fg="#888888", 
            font=("Segoe UI", 10), 
            justify="center",
            pady=40
        )
        lbl.pack(fill=tk.BOTH, expand=True)

    def render_models_grid(self, force=False):
        """Calcula dinamicamente a quantidade de colunas e posiciona os cartões."""
        if not self.current_models_list:
            return

        canvas_width = self.models_canvas.winfo_width() - 15
        if canvas_width < 100:
            canvas_width = 800

        CARD_MIN_WIDTH = 340
        num_cols = max(1, canvas_width // CARD_MIN_WIDTH)

        if not force and self.last_rendered_cols == num_cols:
            return
        self.last_rendered_cols = num_cols

        for widget in self.models_scroll_frame.winfo_children():
            widget.destroy()

        for c in range(num_cols):
            self.models_scroll_frame.columnconfigure(c, weight=1, minsize=CARD_MIN_WIDTH)

        for idx, model in enumerate(self.current_models_list, start=1):
            row = (idx - 1) // num_cols
            col = (idx - 1) % num_cols
            self._render_model_card_grid(self.models_scroll_frame, model, rank=idx, row=row, col=col)

    def _render_model_card_grid(self, parent, model_data, rank, row, col):
        """Constrói um cartão individual formatado para o layout em Grid."""
        try:
            is_top = (rank == 1)
            border_color = "#10b981" if is_top else "#2d2d2d"
            card_bg = "#18181c"

            card = tk.Frame(parent, bg=card_bg, highlightbackground=border_color, highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

            accent_bar = tk.Frame(card, bg="#10b981" if is_top else "#0f766e", width=4)
            accent_bar.pack(side=tk.LEFT, fill=tk.Y)

            content = tk.Frame(card, bg=card_bg)
            content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

            header_row = tk.Frame(content, bg=card_bg)
            header_row.pack(fill=tk.X)

            rank_text = "#1 PRINCIPAL" if is_top else f"#{rank} FALLBACK"
            rank_fg = "#10b981" if is_top else "#888888"
            tk.Label(header_row, text=rank_text, bg=card_bg, fg=rank_fg, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)

            display_name = model_data.get("display_name") or model_data.get("name", "Modelo")
            tk.Label(content, text=display_name, bg=card_bg, fg="#ffffff", font=("Segoe UI", 11, "bold"), anchor="w").pack(fill=tk.X, pady=(2, 0))
            
            name_id = model_data.get("name", "")
            tk.Label(content, text=name_id, bg=card_bg, fg="#666666", font=("Consolas", 8), anchor="w").pack(fill=tk.X, pady=(0, 8))

            metrics_grid = tk.Frame(content, bg=card_bg)
            metrics_grid.pack(fill=tk.X, pady=(4, 0))
            metrics_grid.columnconfigure(0, weight=1)
            metrics_grid.columnconfigure(1, weight=1)

            # Tempo Médio
            resp_time = model_data.get("responsetime") or 0.0
            try:
                resp_str = f"{float(resp_time):.2f}s"
            except Exception:
                resp_str = "0.00s"

            col1 = tk.Frame(metrics_grid, bg=card_bg)
            col1.grid(row=0, column=0, sticky="w", pady=2)
            tk.Label(col1, text="⚡ Tempo Médio", bg=card_bg, fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor=tk.W)
            tk.Label(col1, text=resp_str, bg=card_bg, fg="#60a5fa", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

            # Taxa de Sucesso
            attempts = model_data.get("attempts") or 1
            success = model_data.get("success") or 0
            try:
                attempts = int(attempts)
                success = int(success)
                rate = (success / max(1, attempts) * 100)
            except Exception:
                rate = 0.0

            rate_color = "#10b981" if rate >= 80 else "#f59e0b" if rate >= 50 else "#ef4444"

            col2 = tk.Frame(metrics_grid, bg=card_bg)
            col2.grid(row=0, column=1, sticky="w", pady=2)
            tk.Label(col2, text="Sucesso", bg=card_bg, fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor=tk.W)
            tk.Label(col2, text=f"{rate:.0f}% ({success}/{attempts})", bg=card_bg, fg=rate_color, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

            # Max Tokens
            tokens = model_data.get("maxinputtokens") or 0
            try:
                tokens_str = f"{int(tokens):,}"
            except Exception:
                tokens_str = "0"

            col3 = tk.Frame(metrics_grid, bg=card_bg)
            col3.grid(row=1, column=0, sticky="w", pady=2)
            tk.Label(col3, text="Max Tokens", bg=card_bg, fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor=tk.W)
            tk.Label(col3, text=tokens_str, bg=card_bg, fg="#e3e3e3", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

            # Busca Online
            supports_tools = bool(model_data.get("supports_tools", False))
            tools_str = "Sim" if supports_tools else "Não"
            tools_fg = "#34d399" if supports_tools else "#666666"

            col4 = tk.Frame(metrics_grid, bg=card_bg)
            col4.grid(row=1, column=1, sticky="w", pady=2)
            tk.Label(col4, text="Busca Online", bg=card_bg, fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor=tk.W)
            tk.Label(col4, text=tools_str, bg=card_bg, fg=tools_fg, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        except Exception as e:
            print(f"Erro ao renderizar cartão de modelo: {e}")

    # ------------------------------------------------------------------
    # ABA Do Manual sobre o programa
    # ------------------------------------------------------------------
    def _build_manual_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "📖 Manual de Operações & Guia Prático", "Documentação oficial de recursos, sintaxe do editor, atalhos, segredos e automações.")

        display = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("Segoe UI", 10),
            bg="#1e1e1e", fg="#e3e3e3", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )
        display.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Estilos do Manual
        display.tag_config("h1", font=("Segoe UI", 13, "bold"), foreground="#10b981", spacing1=14, spacing3=6)
        display.tag_config("h2", font=("Segoe UI", 11, "bold"), foreground="#38bdf8", spacing1=10, spacing3=4)
        display.tag_config("bold", font=("Segoe UI", 10, "bold"), foreground="#ffffff")
        display.tag_config("code", font=("Consolas", 10, "bold"), foreground="#f97316", background="#2a1205")
        display.tag_config("kbd", font=("Consolas", 9, "bold"), foreground="#ffffff", background="#333333")
        display.tag_config("bullet", font=("Segoe UI", 10), foreground="#cccccc", lmargin1=15, lmargin2=25)
        display.tag_config("note", font=("Segoe UI", 9, "italic"), foreground="#34d399", lmargin1=15)

        def add_p(text, tags=None):
            display.insert(tk.END, text + "\n", tags)

        # CONTEÚDO DO MANUAL
        add_p("SILENT MULTIVERSE NEXUS", "h1")
        add_p("  - Maneje todos os arquivos .md dentro de um projeto de forma fácil, rápida e segura.", "bullet")
        add_p("  - Exporte seu projeto inteiro como um arquivo HTML com índice, hiperlinks navegáveis e na ordem que você configurar.", "bullet")
        add_p("  - Use IA como achar melhor, onde quiser, sob suas ordens, respondendo como você quiser.", "bullet")
        add_p("  - Converse com Ao para tirar dúvidas, pedir variações de idéias e brainstorming.", "bullet")
        add_p("  - Crie um bot no Discord para seus jogadores e amigos perguntarem qualquer coisa sobre o projeto.", "bullet")
        add_p("  - Faça arquivos com regras de servidor para o Bot também responder quaisquer dúvidas.", "bullet")
        
        add_p("1. INÍCIO RÁPIDO & ESTRUTURA DO PROJETO", "h1")
        add_p("• Projeto Atual: O projeto ativo fica selecionado no topo do menu lateral. Você pode criar ou alternar entre projetos a qualquer momento clicando no ícone de pasta 📁.", "bullet")
        add_p("  - Estrutura de Pastas:", "bullet")
        add_p("  - Pasta do Projeto: Guarda as pastas e os arquivos em Markdown (.md). Pode ter quantos projetos quiser!", "bullet")
        add_p("  - Templates/: Armazena modelos de criação (ex: cidade.md, npc.md, reinado.md). O programa já vem com modelos prontos, mas você pode editá-los e adicionar novos diretamente nesta pasta.", "bullet")
        add_p("  - Style/: Armazena diretrizes de escrita e clima (ex: Tom_e_Clima.md). O arquivo base é alterado de acordo a opção selecionada na aba de Opções, mas você pode inserir outros documentos dentro da pasta que eles também serão usados para melhorar e focar as respostas de IA.", "bullet")
        add_p("  - memories/: Guarda o histórico recente de conversas locais e do Discord. Na aba Converse com Ao, a conversa só é apagada se usar o botão Excluir Memórias na Aba Worldbuilders.", "bullet")
        add_p("  - exports/: Guarda os livros do cenário em HTML compilados e relatórios. Só aparece algo aqui ao usar a opção Gerar e Abrir Livro do cenário na aba Worldbuilders.", "bullet")

        add_p("2. SINTAXE DO EDITOR & REGRAS DE ESCRITA", "h1")
        add_p("• Wikilinks [[Nome Do Arquivo]]:", "h2")
        add_p("  Sempre que quiser citar outra entidade do seu mundo, use colchetes duplos (ex: [[Reino de Phaeton]]). Clique no link no editor para navegar direto até ele. Se o documento não existir, o programa perguntará se deseja criá-lo!", "bullet")
        add_p("• Tags de Expansão (<-- TODO: Motivo):", "h2")
        add_p("  Com o botão direito do Mouse dentro do editor, exista a opção de inserir a tag <-- TODO:, você também pode digitar manualmente, após os dois pontos, insira o que é para ser feito em uma frase, pode ser uma ordem simples ou complexa.", "bullet")
        add_p("  A função Expander detectará a tag e usará a IA para preencher o trecho automaticamente seguindo suas direções.", "bullet")
        add_p("• Segredos do Mestre vs Jogadores:", "h2")
        add_p("  - Função interna que serve para manejar o Bot do Discord quando ele estiver respondendo perguntas de jogadores.", "bullet")
        add_p("  - Para ocultar um arquivo inteiro dos jogadores no Discord, coloque status: segredo ou tags: [segredo] no cabeçalho.", "bullet")
        add_p("  - Para ocultar uma seção específica em um arquivo público, insira o título com [segredo] (ex: ### O Culto Oculto [segredo]).", "bullet")
        add_p("  - Se nunca usar a tag segredo, o projeto continuará funcionando normalmente.", "bullet")
        
        add_p("3. CONVERSA COM AO & BOT DO DISCORD", "h1")
        add_p("• Chat Local:", "h2")
        add_p("  - Ao, dentro do programa, é uma simulação de como seria o Bot do Discord se ele estiver configurado, a conversa com ele é para ser um brainstorming, tirar dúvidas e discutir sobre o projeto em si.", "bullet")
        add_p("  - É possível focar a resposta no chat para um arquivo específico, Clique com o botão direito em qualquer arquivo no Explorer e escolha 'Perguntar sobre este arquivo ao Ao' para anexar o documento completo na conversa!", "bullet")
        add_p("• Bot do Discord:", "h2")
        add_p("  Na aba de opções, existem vários campos para configurar o Bot:", "bullet")
        add_p("  - Gatilho de Comunicação(Prefixo): é a forma que os jogadores acionam o bot dentro do servidor Discord. ex: !ao, $ao, &ao, %João, &Supremo. O que estiver configurado nessa caixa, é como o Bot é acionado.", "bullet")
        add_p("  - Cargos de Mestre: Aqui você coloca o título de cargos do Discord que quem possuir, receberá respostas do Bot com o projeto inteiro, incluindo as partes marcadas como Segredo. Quem não tiver esses cargos, recebe respostas com os segredos removidos.", "bullet")
        add_p("  - Canais Permitidos/Proibidos: O nome exato de canais onde você quer que o Bot possa ou não enviar respostas. Útil para focar o bot em um único chat ou permitir comunicação secreta.", "bullet")
        add_p("  - Tempo de Espera: Limite de cooldown para cada usuário poder falar com o Bot, para impedir Spam.", "bullet")

        add_p("4. WORLDBUILDERS (EXPANDER, TAREFAS E AUDITORIA)", "h1")
        add_p("• Expander - Executar Tarefa: varre todos os arquivos na pasta do projeto buscando por tags <-- TODO:, ao encontrar uma, ele inicia o processo da IA e gera o conteúdo respeitando a coesão do mundo e do arquivo, então gera um novo arquivo de versão acima(ex:Reino_Lucian_v03.md) e salva o anterior(ex:Reino_Lucian_v02.md) na pasta Logs/history.", "bullet")
        add_p("• Expander - Executar Tarefa: Essa ação pode ser automatizada na aba Opções, onde ao deixar um arquivo com essa Tag, o expander já irá ser acionado no momento que o arquivo for salvo.", "bullet")
        add_p("• Expander - Reconstruir Contexto: acesso interno do programa ao estado atual do seu projeto, perguntas ao Ao e ao Bot do Discord usam esse contexto para gerar respostas, ao realizar muitas mudanças, esse botão as força para o estado atual. É como um botão Salvar para o projeto inteiro. O contexto dura 12h de sua criação, passado esse tempo, ele é recriado automaticamente. O botão é apenas para acelerar o processo.", "bullet")
        add_p("• WorldBuilder: Executa um plano autônomo completo (cria pastas, arquivos e expande a lore) com base no objetivo que você definir.", "bullet")
        add_p("• WorldBuilder: A criação de pastas, arquivos e melhoria de arquivos podem ser habilitadas ou desabilitadas na aba Opções, para melhor controlar o que o Worldbuilder irá fazer.", "bullet")
        add_p("• Auditoria de Lore: Analisa todo o universo do seu projeto em busca de incoerências históricas, furos de cronologia ou contradições geográficas.", "bullet")
        add_p("• Gerar e Abrir Livro do Cenário:  Compila todos os arquivos Markdown, cria um arquivo HTML de todo o projeto com índice e links, e já abre ele no seu Browser padrão, esse documento pode ser salvo como PDF.", "bullet")
        add_p("• Backup do Projeto: Gera um arquivo .zip completo com todas as suas pastas e memórias gravado na raiz do disco onde o executável está rodando, pode dar erro se tentar no C:/, mas funciona bem em outros volumes.", "bullet")
        add_p("• Excluir todas as Memórias: Deleta todos os arquivos da pasta memories, que contém a conversa local da aba Converse com Ao e todas as conversas do Bot do Discord com qualquer usuário em qualquer servidor.", "bullet")
        add_p("• Excluir todas as Memórias: É possível deletar esses arquivos manualmente direto na pasta.", "bullet")

        add_p("5. ATALHOS DE TECLADO & NAVEGAÇÃO", "h1")
        add_p("  [F2]                 : Renomear o arquivo ou pasta selecionada no Explorer.", "bullet")
        add_p("  [Ctrl + Scroll Mouse]: Aumentar ou diminuir o zoom da tela.", "bullet")
        add_p("  [Alt + Seta Esquerda]: Voltar para o documento anterior no histórico.", "bullet")
        add_p("  [Alt + Seta Direita] : Avançar no histórico de documentos.", "bullet")
        add_p("  [Ctrl + Z]           : Desfazer edições no texto.", "bullet")
        add_p("  [Botão Lateral Mouse]: Voltar / Avançar na navegação entre arquivos.(Talvez funcione)", "bullet")
        
        add_p("6. COMANDOS MARKDOWN(.md)", "h1")
        add_p("• Guia Completo: https://github.com/mende1/guia-definitivo-de-markdown\n", "bullet")
        md_cheatsheet = (
            "# Título 1\n"
            "## Título 2\n"
            "### Título 3\n\n"
            "- Item de lista 1\n"
            "- Item de lista 2\n\n"
            "**texto em negrito**\n"
            "*texto em itálico*\n"
            "~~texto riscado~~\n\n"
            "Linhas separadoras:\n"
            "--- ou *** ou ___\n\n"
            "Citação / Caixa de Lore:\n"
            "> texto de citação\n"
            "> - item dentro de citação\n"
            ">> citação aninhada"
        )
        add_p(md_cheatsheet, "code")

        display.config(state=tk.DISABLED)
        return frame
    
    # ------------------------------------------------------------------
    # Próxima evolução
    # ------------------------------------------------------------------
    #


def main():
    root = tk.Tk()
    app = SilentDesktopApp(root)
    root.mainloop()
    
if __name__ == "__main__":
    main()