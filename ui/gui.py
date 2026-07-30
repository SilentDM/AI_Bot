import os, threading, time, asyncio, sys, json
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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
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
        self.setup_shortcuts()
        self.change_font_size(0)

        # Página inicial ao abrir o programa
        self.switch_page("editor")

        self.start_discord_bot_thread()

        # Executa descoberta de modelos em segundo plano para não travar o startup
        threading.Thread(target=ag.findmodel, daemon=True).start()

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

        nav_items = [
            ("editor", "Edição do Mundo"),
            ("worldbuilder", "WorldBuilder"),
            ("chat", "Converse com Ao"),
            ("log", "Atividades"),
            ("options", "Opções"),
        ]
        for key, label in nav_items:
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
        self.pages[name].tkraise()
        self.current_page = name
        for key, btn in self.nav_buttons.items():
            btn.configure(style="NavActive.TButton" if key == name else "Nav.TButton")

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
            ask_ao_callback=self.open_chat_with_file_context
        )
        self.explorer_pane.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        return frame

    def _build_worldbuilder_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "WorldBuilder & Expander", "Dispare ou interrompa tarefas de expansão automática do seu mundo.")
        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # BARRA DE EMERGÊNCIA
        stop_box = ttk.LabelFrame(body, text=" Controle de Emergência ")
        stop_box.pack(fill=tk.X, pady=(0, 15))
        self.btn_stop = ttk.Button(stop_box, text="⛔⛔PARAR QUALQUER EXECUÇÃO ATUAL⛔⛔", command=self.stop_all_tasks)
        self.btn_stop.pack(fill=tk.X, padx=10, pady=10)

        # AUDITORIA DE LORE
        audit_box = ttk.LabelFrame(body, text=" Auditoria e Consistência ")
        audit_box.pack(fill=tk.X, pady=(0, 15))
        self.btn_audit_lore = ttk.Button(
            audit_box, 
            text="Auditar Lore do Mundo (Buscar Incoerências e Furos)", 
            command=self.start_lore_audit_thread
        )
        self.btn_audit_lore.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_audit = ttk.Label(audit_box, text="Status: Inativo")
        self.lbl_audit.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # Expander Box
        expander_box = ttk.LabelFrame(body, text=" Expander (preenche lacunas marcadas com TO DO) ")
        expander_box.pack(fill=tk.X, pady=(0, 15))
        self.btn_expander = ttk.Button(expander_box, text="▶ Executar Tarefa do Expander", command=self.start_expander_thread)
        self.btn_expander.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_expander = ttk.Label(expander_box, text="Status: Inativo")
        self.lbl_expander.pack(anchor=tk.W, padx=10, pady=(0, 10))
        self.btn_rebuild_context = ttk.Button(expander_box, text="▶ Reconstruir Contexto do Mundo", command=self.rebuild_world_context)
        self.btn_rebuild_context.pack(fill=tk.X, padx=10, pady=5)
        
        # WorldBuilder Box
        wb_box = ttk.LabelFrame(body, text=" WorldBuilder (planeja e executa expansão autônoma) ")
        wb_box.pack(fill=tk.X)
        ttk.Label(wb_box, text="Objetivo:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.worldbuilder_objective = tk.StringVar(value="Completar o Projeto")
        self.objective_entry = ttk.Entry(wb_box, textvariable=self.worldbuilder_objective)
        self.objective_entry.pack(fill=tk.X, padx=10, pady=5)
        self.btn_worldbuilder = ttk.Button(wb_box, text="▶ Executar WorldBuilder", command=self.start_worldbuilder_thread)
        self.btn_worldbuilder.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.lbl_worldbuilder = ttk.Label(wb_box, text="Status: Inativo")
        self.lbl_worldbuilder.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Exportação do Livro
        export_box = ttk.LabelFrame(body, text=" Exportação do Cenário ")
        export_box.pack(fill=tk.X, pady=(15, 0))
        self.btn_export_book = ttk.Button(export_box, text="▶ Gerar e Abrir Livro do Cenário (HTML/PDF)", command=self.export_sourcebook)
        self.btn_export_book.pack(fill=tk.X, padx=10, pady=10)

        # Gerenciamento de Memórias
        db_box = ttk.LabelFrame(body, text=" Gerenciamento ")
        db_box.pack(fill=tk.X, pady=(15, 0))
        
        self.btn_create_backup = ttk.Button(db_box, text="▶ Criar Backup Completo do Projeto (.zip)", command=self.create_backup)
        self.btn_create_backup.pack(fill=tk.X, padx=10, pady=5)        
        
        self.btn_delete_memories = ttk.Button(db_box, text="⛔Excluir Todas as Memórias⛔", command=self.delete_memories)
        self.btn_delete_memories.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(body, text="Acompanhe o andamento detalhado no Log de Atividades.", foreground="#666666", wraplength=560, justify="left").pack(anchor=tk.W, pady=(15, 0))
        return frame
    
    def _build_chat_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "💬 Conversa com Ao", "Fale diretamente com Ao sobre o seu mundo.")

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

        input_frame = ttk.Frame(frame)
        input_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        self.input_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda event: self.send_chat_message())
        self.send_button = ttk.Button(input_frame, text="Enviar", command=self.send_chat_message)
        self.send_button.pack(side=tk.RIGHT)

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
        self.toast("🔍 Recriando bundle e iniciando Auditoria de Lore...")
        self.log_activity("Iniciando auditoria de lore...")

        self.explorer_pane.save_current_file()
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

            self.switch_page("chat")
            
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, f"Analise o arquivo '{nome_arq}' e me ajude com o seguinte: ")
            self.input_entry.focus_set()

            self.toast(f"💬 Contexto de '{nome_arq}' carregado na conversa!")
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
            guild_id = "desktop_env"
            guild_name = "Desktop_Console"
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
            self.log_activity("Iniciando bot do Discord em segundo plano...")
            from bot.dbot import discordclient, TOKEN

            if not TOKEN:
                self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Desativado", fg="#888888"))
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.discord_loop = loop

            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Online", fg="#10b981"))
            self.log_activity("Instância do Discord online.")

            loop.run_until_complete(discordclient.start(TOKEN))

        except Exception as e:
            self.log_activity(f"Exceção no Discord: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Offline/Erro", fg="#ef4444"))
        finally:
            if loop and not loop.is_closed():
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception as e:
                    print(f"Limpeza de tarefas do Discord: {e}")
                finally:
                    loop.close()
                    self.discord_loop = None

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
            try:
                self.log_activity("Iniciando compilação do Livro do Cenário...")
                self.toast("📖 Compilando Livro do Cenário...")
                
                caminho_html = comp.compilar_livro_cenario()
                if caminho_html and caminho_html.exists():
                    self.log_activity(f"Livro gerado em: {caminho_html.name}")
                    self.toast("✅ Livro compilado com sucesso! Abrindo...")
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


def main():
    root = tk.Tk()
    app = SilentDesktopApp(root)
    root.mainloop()
    
if __name__ == "__main__":
    main()