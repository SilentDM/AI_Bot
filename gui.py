import threading, time, asyncio, explorer, memory, sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import expander as ex
import gemini.ai_gemini as au
import project_utils as pu
import gui_logger as gl
import setup_env as se


class AoDesktopApp:
    def __init__(self, root):
        self.root = root
        self.user_name = "SilentDM"
        self.root.title("Ao Multiverse Console")
        self.root.geometry("1300x700")
        self.root.minsize(1050, 550)
        self.root.state("zoomed")  # Windows
        self.root.configure(bg="#121212")

        self.current_font_size = 11
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_dark_style()
        
        # Estados internos das engines de background.
        # Continuam existindo independente de qual página está visível na tela.
        self.discord_running = False
        self.expander_running = False
        self.worldbuilder_running = False
        self.discord_loop = None

        # Controle de navegação: guarda os frames de cada "página" e os
        # botões correspondentes na sidebar, para saber qual destacar.
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = None

        self.setup_ui()

        self.setup_shortcuts()
        self.change_font_size(0)

        # Página inicial ao abrir o programa
        self.switch_page("editor")

        self.start_discord_bot_thread()

    # ------------------------------------------------------------------
    # ESTILO VISUAL (dark mode compartilhado por toda a interface)
    # ------------------------------------------------------------------
    def setup_dark_style(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

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
        self.style.configure('TLabelframe.Label', background='#1e1e1e', foreground='#10b981',font=('Segoe UI', 10, 'bold'))

        self.style.configure('TButton',
            background='#252526', foreground='#e3e3e3', bordercolor='#2d2d2d',
            lightcolor='#2d2d2d', darkcolor='#121212', borderwidth=1, padding=6
        )
        self.style.map('TButton',
            background=[('active', '#333333'), ('pressed', '#121212')],
            foreground=[('active', '#ffffff')]
        )

        self.style.configure('TEntry', fieldbackground='#252526', foreground='#ffffff',bordercolor='#2d2d2d', lightcolor='#252526', darkcolor='#252526')

        self.style.configure('Treeview', background='#1e1e1e', foreground='#e3e3e3',fieldbackground='#1e1e1e', bordercolor='#2d2d2d', borderwidth=1, rowheight=24)
        self.style.map('Treeview',
            background=[('selected', '#0f766e')],
            foreground=[('selected', '#ffffff')]
        )
        self.style.configure('Heading', background='#121212', foreground='#10b981',bordercolor='#2d2d2d', font=('Segoe UI', 9, 'bold'))
        self.style.map('Heading', background=[('active', '#2d2d2d')])

        self.style.configure('Vertical.TScrollbar', background='#252526', troughcolor='#121212',bordercolor='#2d2d2d', lightcolor='#252526', darkcolor='#252526',arrowcolor='#e3e3e3')
        self.style.map('Vertical.TScrollbar', background=[('active', '#2d2d2d')])

        # --- Estilos exclusivos dos botões de navegação da sidebar ---
        # Nav.TButton: estado normal (não selecionado)
        self.style.configure('Nav.TButton',
            background='#121212', foreground='#cccccc', borderwidth=0,
            anchor='w', padding=(16, 12), font=('Segoe UI', 10)
        )
        self.style.map('Nav.TButton', background=[('active', '#1e1e1e')])

        # NavActive.TButton: estado da página atualmente aberta (destacado em verde)
        self.style.configure('NavActive.TButton',
            background='#1e1e1e', foreground='#10b981', borderwidth=0,
            anchor='w', padding=(16, 12), font=('Segoe UI', 10, 'bold')
        )
        self.style.map('NavActive.TButton', background=[('active', '#1e1e1e')])

    # ------------------------------------------------------------------
    # MONTAGEM GERAL DA INTERFACE (sidebar + área de conteúdo)
    # ------------------------------------------------------------------
    def setup_ui(self):
        root_container = ttk.Frame(self.root)
        root_container.pack(fill=tk.BOTH, expand=True)
        root_container.columnconfigure(1, weight=1)
        root_container.rowconfigure(0, weight=1)

        # --- SIDEBAR (navegação lateral fixa, sempre visível) ---
        sidebar = tk.Frame(root_container, bg="#0a0a0a", width=200)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)  # impede que o conteúdo interno force a largura a mudar

        tk.Label(sidebar, text="🜂 Ao Console", bg="#0a0a0a", fg="#10b981",font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, padx=16, pady=(22, 26))

        # Cada item: (chave interna da página, texto exibido no botão)
        nav_items = [
            ("editor", "Edição do Mundo"),
            ("worldbuilder", "WorldBuilder"),
            ("chat", "Converse com Ao"),
            ("log", "Atividades"),
        ]
        for key, label in nav_items:
            btn = ttk.Button(sidebar, text=label, style="Nav.TButton",command=lambda k=key: self.switch_page(k))
            btn.pack(fill=tk.X, padx=8, pady=2)
            self.nav_buttons[key] = btn

        # Controle de zoom: fica disponível na sidebar, então funciona
        # não importa em qual página o usuário está.
        zoom_frame = tk.Frame(sidebar, bg="#0a0a0a")
        zoom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 6))
        tk.Label(zoom_frame, text="Zoom:", bg="#0a0a0a", fg="#888888",font=("Segoe UI", 8)).pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="A-", width=3,command=lambda: self.change_font_size(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="A+", width=3,command=lambda: self.change_font_size(1)).pack(side=tk.LEFT, padx=2)

        # Status do Discord: é informação global do sistema (não de uma
        # tarefa específica), então fica fixo no rodapé da sidebar,
        # visível em qualquer uma das 4 páginas.
        ttk.Separator(sidebar, orient="horizontal").pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=8)
        self.lbl_discord = tk.Label(sidebar, text="Discord: Starting...", bg="#0a0a0a",fg="#e3e3e3", font=("Segoe UI", 8, "bold"),anchor="w", justify="left", wraplength=175)
        self.lbl_discord.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(0, 4))

        # --- ÁREA DE CONTEÚDO: as 4 páginas ficam empilhadas aqui ---
        content_area = ttk.Frame(root_container)
        content_area.grid(row=0, column=1, sticky="nsew")

        self.pages["editor"] = self._build_editor_page(content_area)
        self.pages["worldbuilder"] = self._build_worldbuilder_page(content_area)
        self.pages["chat"] = self._build_chat_page(content_area)
        self.pages["log"] = self._build_log_page(content_area)

        # Todas ocupam o mesmo espaço, sobrepostas; tkraise() decide qual aparece.
        for page in self.pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _page_header(self, parent, title, subtitle):
        """Cabeçalho padrão (título + descrição) usado no topo de cada página,
        para dar consistência visual entre as 4 abas."""
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=18, pady=(18, 10))
        ttk.Label(header, text=title, font=("Segoe UI", 14, "bold"),foreground="#10b981").pack(anchor=tk.W)
        ttk.Label(header, text=subtitle, font=("Segoe UI", 9),foreground="#888888").pack(anchor=tk.W, pady=(3, 0))

    def switch_page(self, name):
        """Traz a página escolhida para frente e atualiza o destaque
        visual do botão correspondente na sidebar. Nenhuma página é
        destruída ao trocar — todo o estado (chat, editor, campos) é preservado."""
        if name not in self.pages:
            return
        self.pages[name].tkraise()
        self.current_page = name
        for key, btn in self.nav_buttons.items():
            btn.configure(style="NavActive.TButton" if key == name else "Nav.TButton")

    # ------------------------------------------------------------------
    # PÁGINA 1: EDIÇÃO DE MUNDO (explorer de arquivos + editor)
    # ------------------------------------------------------------------
    def _build_editor_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "Edição de Mundo","Explore, edite e organize os arquivos do seu projeto.")
        self.explorer_pane = explorer.ExplorerFrame(frame, self.log_activity)
        self.explorer_pane.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        return frame

    # ------------------------------------------------------------------
    # PÁGINA 2: WORLDBUILDER (Expander + WorldBuilder autônomo)
    # ------------------------------------------------------------------
    def _build_worldbuilder_page(self, parent):
        frame = ttk.Frame(parent)
        self._page_header(frame, "WorldBuilder & Expander","Dispare tarefas de expansão automática do seu mundo em segundo plano.")

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # --- Bloco do Expander ---
        expander_box = ttk.LabelFrame(body, text=" Expander (preenche lacunas marcadas com TO DO) ")
        expander_box.pack(fill=tk.X, pady=(0, 15))
        self.btn_expander = ttk.Button(expander_box, text="▶  Run Expander Task",command=self.start_expander_thread)
        self.btn_expander.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_expander = ttk.Label(expander_box, text="Status: Idle")
        self.lbl_expander.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # --- Bloco do WorldBuilder ---
        wb_box = ttk.LabelFrame(body, text=" WorldBuilder (planeja e executa expansão autônoma) ")
        wb_box.pack(fill=tk.X)
        ttk.Label(wb_box, text="Objetivo:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.worldbuilder_objective = tk.StringVar(value="Completar o Projeto")
        self.objective_entry = ttk.Entry(wb_box, textvariable=self.worldbuilder_objective)
        self.objective_entry.pack(fill=tk.X, padx=10, pady=5)
        self.btn_worldbuilder = ttk.Button(wb_box, text="▶  Run WorldBuilder",command=self.start_worldbuilder_thread)
        self.btn_worldbuilder.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.lbl_worldbuilder = ttk.Label(wb_box, text="Status: Idle")
        self.lbl_worldbuilder.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # --- Bloco do DeleteMemories ---
        db_box = ttk.LabelFrame(body, text="")
        db_box.pack(fill=tk.X, pady=(0, 15))
        self.btn_delete_memories = ttk.Button(db_box,text="X Excluir Memórias",command=self.delete_memories)
        self.btn_delete_memories.pack(fill=tk.X,padx=10,pady=5)

        # Dica visual, lembrando que dá pra navegar livremente enquanto a tarefa roda
        ttk.Label(body,text="Você pode ir para outras abas enquanto uma tarefa roda em segundo ""plano — acompanhe o progresso técnico na aba 'Atividade'.",foreground="#666666", wraplength=560, justify="left").pack(anchor=tk.W, pady=(20, 0))
        return frame

    # ------------------------------------------------------------------
    # PÁGINA 3: CONVERSA COM AO (chat)
    # ------------------------------------------------------------------
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

        input_frame = ttk.Frame(frame)
        input_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        self.input_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda event: self.send_chat_message())
        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_chat_message)
        self.send_button.pack(side=tk.RIGHT)

        self.append_to_chat("System", "Multiverse local console connected. You can start typing below.")
        return frame

    # ------------------------------------------------------------------
    # PÁGINA 4: ATIVIDADE (log técnico)
    # ------------------------------------------------------------------
    def _build_log_page(self, parent):
        frame = ttk.Frame(parent)
        sys.stdout = gl.GuiOutput(self.log_activity)
        sys.stdout = gl.GuiOutput(self.log_activity)
        sys.stderr = gl.GuiOutput(self.log_activity)
        self._page_header(frame, "📋 Log de Atividade","Histórico técnico de tudo que está acontecendo em segundo plano.")
        self.log_display = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9),
            bg="#1e1e1e", fg="#cccccc", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        return frame

    # ------------------------------------------------------------------
    # ATALHOS DE ZOOM
    # ------------------------------------------------------------------
    def setup_shortcuts(self):
        self.root.bind("<Control-KeyPress-equal>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-plus>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-minus>", lambda e: self.change_font_size(-1))
        self.root.bind("<Control-KP_Add>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KP_Subtract>", lambda e: self.change_font_size(-1))

    def change_font_size(self, delta):
        self.current_font_size = max(8, min(24, self.current_font_size + delta))
        self.chat_display.configure(font=("Segoe UI", self.current_font_size))
        self.explorer_pane.update_editor_font(self.current_font_size)
        if delta != 0:
            self.log_activity(f"Font size scaled to: {self.current_font_size}")

    # ------------------------------------------------------------------
    # CHAT COM AO
    # ------------------------------------------------------------------
    def append_to_chat(self, sender, text):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{sender}: ", sender)
        self.chat_display.insert(tk.END, f"{text}\n\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def log_activity(self, message):
        self.root.after(0, self._safe_log_activity, message)

    def _safe_log_activity(self, message):
        self.log_display.config(state=tk.NORMAL)
        self.log_display.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_display.see(tk.END)
        self.log_display.config(state=tk.DISABLED)

    def send_chat_message(self):
        prompt = self.input_entry.get().strip()
        if not prompt:
            return
        self.input_entry.delete(0, tk.END)
        self.append_to_chat("You", prompt)
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

            memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)

            self.log_activity("Querying Gemini on dynamic file contents...")

            system_instruction = f"{persona}\n\n{regras}"
            conteudo_prompt = ""
            if memorias:
                conteudo_prompt += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
            conteudo_prompt += f"--- MENSAGEM DO USUÁRIO ---\n{prompt}"

            resposta = au.ask_ai(
                contents=conteudo_prompt,
                system_instruction=system_instruction,
                temperature=0.6,
                use_world_context=True
            )

            if resposta:
                finalz = [".", "!", "?"]
                if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
                    resposta = memory.trim_incomplete_sentences(resposta)

                self.root.after(0, lambda: self.append_to_chat("Ao", resposta))
                memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta)
                self.log_activity("Interaction registered to memories successfully.")
            else:
                self.root.after(0, lambda: self.append_to_chat("System", "No response received. Check terminal."))

        except Exception as e:
            self.root.after(0,lambda err=str(e):
                self.append_to_chat("System",f"Execution error: {err}"))

    # ------------------------------------------------------------------
    # ENGINE DE DISCORD
    # ------------------------------------------------------------------
    def start_discord_bot_thread(self):
        threading.Thread(target=self.run_discord_bot, daemon=True).start()

    def run_discord_bot(self):
        try:
            self.log_activity("Launching background Discord runner...")
            from dbot import discordclient, TOKEN

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.discord_loop = loop

            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Online", fg="#10b981"))
            self.log_activity("Discord server instance online.")

            loop.run_until_complete(discordclient.start(TOKEN))
        except Exception as e:
            self.log_activity(f"Discord exception occurred: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord: Offline/Error", fg="#ef4444"))
        finally:
            self.discord_loop = None

    # ------------------------------------------------------------------
    # ENGINE DE EXPANSOR
    # ------------------------------------------------------------------
    def start_expander_thread(self):
        if self.expander_running:
            messagebox.showwarning("Warning", "The expander task is currently running.")
            return

        self.expander_running = True
        self.btn_expander.config(state=tk.DISABLED)
        self.lbl_expander.config(text="Status: Working...", foreground="#60a5fa")
        self.log_activity("Spawning child task for file expansion...")

        self.explorer_pane.save_current_file()
        threading.Thread(target=self.run_expander_task, daemon=True).start()

    def run_expander_task(self):
        try:
            import expander
            expander.processar_arquivos()
            self.log_activity("Expansion process completed.")
            self.finished_expander_ui_update("Task Finished")
        except Exception as e:
            self.log_activity(f"Expander encountered an issue: {e}")
            self.finished_expander_ui_update("Failed (Error)")

    def finished_expander_ui_update(self, status):
        self.expander_running = False
        self.root.after(0, self._safe_finished_expander, status)

    def _safe_finished_expander(self, status):
        self.btn_expander.config(state=tk.NORMAL)
        self.lbl_expander.config(text=f"Status: {status}", foreground="#e3e3e3")
        self.explorer_pane.refresh_tree()
    
    
    # ------------------------------------------------------------------
    # ENGINE DE WORLD BUILDER
    # ------------------------------------------------------------------
    def start_worldbuilder_thread(self):
        self.worldbuilder_objective_value = self.worldbuilder_objective.get().strip()
        if not self.worldbuilder_objective_value:
            self.worldbuilder_objective_value = "Completar o Projeto"

        if self.worldbuilder_running:
            messagebox.showwarning("Warning", "The WorldBuilder task is currently running.")
            return

        self.worldbuilder_running = True
        self.btn_worldbuilder.config(state=tk.DISABLED)
        self.lbl_worldbuilder.config(text="Status: Working...", foreground="#60a5fa")
        self.log_activity("Spawning child task for WorldBuilder...")

        self.explorer_pane.save_current_file()
        threading.Thread(target=self.run_worldbuilder_task, daemon=True).start()

    def run_worldbuilder_task(self):
        try:
            import wbuilder
            self.log_activity("Starting autonomous WorldBuilder...")
            objective = self.worldbuilder_objective_value

            iterations = wbuilder.iterationschoice(objective)
            if iterations is None:
                iterations = 1
            self.log_activity(f"Gemini decided on {iterations} iterations.")

            wbuilder.taskplanner(iterations, objective)

            self.log_activity("WorldBuilder completed successfully.")
            self.finished_worldbuilder_ui_update("Task Finished")
        except Exception as e:
            self.log_activity(f"WorldBuilder encountered an issue: {e}")
            self.finished_worldbuilder_ui_update("Failed (Error)")

    def finished_worldbuilder_ui_update(self, status):
        self.worldbuilder_running = False
        self.root.after(0, self._safe_finished_worldbuilder, status)

    def _safe_finished_worldbuilder(self, status):
        self.btn_worldbuilder.config(state=tk.NORMAL)
        self.lbl_worldbuilder.config(text=f"Status: {status}", foreground="#e3e3e3")
        self.explorer_pane.refresh_tree()

    # ------------------------------------------------------------------
    # ENGINE DE EXCLUIR MEMORIAS
    # ------------------------------------------------------------------
    def delete_memories(self):
        resposta = messagebox.askyesno("Confirmar","Deseja realmente excluir todas as memórias?")
        if not resposta:
            return
        try:
            memory.delete_all_memories()
            self.log_activity("Todas as memórias foram removidas.")
            messagebox.showinfo("Concluído","Todas as memórias foram excluídas.")
        except Exception as e:
            self.log_activity(f"Erro ao excluir memórias: {e}")
            messagebox.showerror("Erro",str(e))


    # ------------------------------------------------------------------
    # ENGINE DE Pop-Ups - Sem utilização no momento, não está funcionando corretamente
    # ------------------------------------------------------------------
    def toast(self, mensagem):
            popup = tk.Toplevel(self.root)
            popup.overrideredirect(True)
            popup.attributes("-topmost",True)
            popup.configure(bg="#1e1e1e")
            largura = 350
            altura = 80
            x = popup.winfo_screenwidth() - largura - 20
            y = popup.winfo_screenheight() - altura - 60
            popup.geometry(f"{largura}x{altura}+{x}+{y}")
            tk.Label(
                popup,
                text=mensagem,
                bg="#1e1e1e",
                fg="#10b981",
                font=("Segoe UI", 10, "bold")
            ).pack(expand=True)
            popup.after(2000,popup.destroy)


    # ------------------------------------------------------------------
    # FECHAMENTO SEGURO DO APLICATIVO
    # (única definição de on_closing — antes existiam duas na classe,
    # e a segunda sobrescrevia a primeira silenciosamente, fazendo o
    # bot do Discord nunca ser desconectado corretamente ao fechar.)
    # ------------------------------------------------------------------
    def on_closing(self):
        self.log_activity("Shutting down... saving open files...")
        self.explorer_pane.save_current_file()
        try:
            if hasattr(self, "discord_loop") and self.discord_loop and self.discord_loop.is_running():
                from dbot import discordclient
                self.log_activity("Closing Discord connection...")
                future = asyncio.run_coroutine_threadsafe(discordclient.close(), self.discord_loop)
                future.result(timeout=5)
                self.discord_loop.call_soon_threadsafe(self.discord_loop.stop)
        except Exception as e:
            self.log_activity(f"Warning: Discord close did not finish cleanly: {e}")
        finally:
            self.root.destroy()
            
if __name__ == "__main__":
    root = tk.Tk()
    app = AoDesktopApp(root)
    se.garantir_env()
    au.findmodel()
    root.mainloop()