import threading
import time
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from main import detectar_intencao, ask_gemini
import project_utils as pu
import explorer
import memory

class AoDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ao Multiverse Console")
        self.root.geometry("1250x650")
        self.root.minsize(1000, 500)
        self.root.state("zoomed")  # Windows
        
        # Define o plano de fundo da janela mestre para combinar com o Dark Mode moderno
        self.root.configure(bg="#121212")
        
        # Seta a fonte padrão inicial de controle
        self.current_font_size = 11
        
        # Vincula o evento de fechamento seguro da janela para realizar auto-salvamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Aplica a paleta moderna de Dark Mode usando o baseline 'clam'
        self.setup_dark_style()
        
        # Estados internos das engines de background
        self.discord_running = False
        self.expander_running = False
        self.worldbuilder_running = False
        
        # Constrói o layout de 3 colunas principais
        self.setup_ui()
        
        # Mapeia os atalhos universais de Zoom de teclado (Ctrl + e Ctrl -)
        self.setup_shortcuts()
        
        # Inicializa o tamanho de fonte unificado em toda a interface
        self.change_font_size(0)
        
        # Inicializa a sincronização do Discord Bot em segundo plano
        self.discord_loop = None
        self.start_discord_bot_thread()

    def setup_dark_style(self):
        """Configura uma paleta dark mode moderna e minimalista nos elementos ttk."""
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
        
        self.style.configure('TLabelframe', 
            background='#1e1e1e', 
            bordercolor='#2d2d2d',
            borderwidth=1
        )
        self.style.configure('TLabelframe.Label', 
            background='#1e1e1e', 
            foreground='#10b981',  # Emerald green para os títulos de caixas
            font=('Segoe UI', 10, 'bold')
        )
        
        self.style.configure('TButton', 
            background='#252526', 
            foreground='#e3e3e3', 
            bordercolor='#2d2d2d',
            lightcolor='#2d2d2d',
            darkcolor='#121212',
            borderwidth=1,
            padding=4
        )
        self.style.map('TButton', 
            background=[('active', '#333333'), ('pressed', '#121212')],
            foreground=[('active', '#ffffff')]
        )
        
        self.style.configure('TEntry', 
            fieldbackground='#252526', 
            foreground='#ffffff',
            bordercolor='#2d2d2d',
            lightcolor='#252526',
            darkcolor='#252526'
        )
        
        self.style.configure('Treeview', 
            background='#1e1e1e', 
            foreground='#e3e3e3', 
            fieldbackground='#1e1e1e',
            bordercolor='#2d2d2d',
            borderwidth=1,
            rowheight=24
        )
        self.style.map('Treeview', 
            background=[('selected', '#0f766e')],  # Teal escuro para seleções
            foreground=[('selected', '#ffffff')]
        )
        self.style.configure('Heading', 
            background='#121212', 
            foreground='#10b981', 
            bordercolor='#2d2d2d',
            font=('Segoe UI', 9, 'bold')
        )
        self.style.map('Heading',
            background=[('active', '#2d2d2d')]
        )
        
        self.style.configure('Vertical.TScrollbar', 
            background='#252526', 
            troughcolor='#121212', 
            bordercolor='#2d2d2d', 
            lightcolor='#252526',
            darkcolor='#252526',
            arrowcolor='#e3e3e3'
        )
        self.style.map('Vertical.TScrollbar', 
            background=[('active', '#2d2d2d')]
        )

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- COLUNA 1: Dynamic Explorer & Editor Pane (explorer.py) ---
        self.explorer_pane = explorer.PhaetonExplorerFrame(main_paned, self.log_activity)
        main_paned.add(self.explorer_pane, weight=2)
        
        # --- COLUNA 2: Chat Box (Centro) ---
        chat_frame = ttk.LabelFrame(main_paned, text=" Chat with Ao ")
        main_paned.add(chat_frame, weight=2)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            font=("Segoe UI", 10),
            bg="#1e1e1e",
            fg="#e3e3e3",
            insertbackground="white",
            selectbackground="#0f766e",
            selectforeground="white",
            bd=0,
            highlightthickness=0
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.chat_display.tag_config("You", foreground="#60a5fa", font=("Segoe UI", 10, "bold"))  # Soft Blue
        self.chat_display.tag_config("Ao", foreground="#34d399", font=("Segoe UI", 10, "bold"))   # Mint Green
        self.chat_display.tag_config("System", foreground="#888888", font=("Segoe UI", 9, "italic"))
        
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.input_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda event: self.send_chat_message())
        
        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_chat_message)
        self.send_button.pack(side=tk.RIGHT)
        
        # --- COLUNA 3: Status & Console Logs (Direita) ---
        sidebar_frame = ttk.Frame(main_paned)
        main_paned.add(sidebar_frame, weight=1)
        
        status_frame = ttk.LabelFrame(sidebar_frame, text=" System Status ")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.lbl_discord = ttk.Label(status_frame, text="Discord Bot: Starting...", font=("Segoe UI", 9, "bold"))
        self.lbl_discord.pack(anchor=tk.W, padx=10, pady=5)
        
        self.lbl_expander = ttk.Label(status_frame, text="Expander status: Idle", font=("Segoe UI", 9))
        self.lbl_expander.pack(anchor=tk.W, padx=10, pady=5)
        
        self.lbl_worldbuilder = ttk.Label(status_frame, text="WorldBuilder status: Idle", font=("Segoe UI", 9))
        self.lbl_worldbuilder.pack(anchor=tk.W, padx=10, pady=5)
        
        # Painel de Ações
        actions_frame = ttk.LabelFrame(sidebar_frame, text=" Tools ")
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_expander = ttk.Button(
            actions_frame, text="Run Expander Task", command=self.start_expander_thread
        )
        self.btn_expander.pack(fill=tk.X, padx=10, pady=5)
        self.worldbuilder_objective = tk.StringVar(
            value="Completar o Projeto"
        )

        ttk.Label(
            actions_frame,
            text="WorldBuilder Objective:"
        ).pack(
            anchor=tk.W,
            padx=10,
            pady=(10, 0)
        )

        self.objective_entry = ttk.Entry(
            actions_frame,
            textvariable=self.worldbuilder_objective
        )

        self.objective_entry.pack(
            fill=tk.X,
            padx=10,
            pady=5
        )
        self.btn_worldbuilder = ttk.Button(
            actions_frame, text="Run WorldBuilder", command=self.start_worldbuilder_thread
        )
        self.btn_worldbuilder.pack(fill=tk.X, padx=10, pady=5)
        
        # Ajuste de Fonte na barra de ferramentas
        font_control_frame = ttk.Frame(actions_frame)
        font_control_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        lbl_font_title = ttk.Label(font_control_frame, text="Zoom Interface:")
        lbl_font_title.pack(side=tk.LEFT, padx=(0, 5))
        
        btn_font_dec = ttk.Button(font_control_frame, text="A-", width=4, command=lambda: self.change_font_size(-1))
        btn_font_dec.pack(side=tk.LEFT, padx=2)
        
        btn_font_inc = ttk.Button(font_control_frame, text="A+", width=4, command=lambda: self.change_font_size(1))
        btn_font_inc.pack(side=tk.LEFT, padx=2)
        
        log_frame = ttk.LabelFrame(sidebar_frame, text=" Activity Log ")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_display = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            font=("Consolas", 8), 
            height=15,
            bg="#1e1e1e",
            fg="#cccccc",
            insertbackground="white",
            selectbackground="#0f766e",
            selectforeground="white",
            bd=0,
            highlightthickness=0
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.append_to_chat("System", "Multiverse local console connected. You can start typing below.")

    # --- MAPEAMENTO DE ATALHOS DE ZOOM (Ctrl + e Ctrl -) ---
    def setup_shortcuts(self):
        """Vincula atalhos físicos do Windows para controle rápido de zoom."""
        self.root.bind("<Control-KeyPress-equal>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-plus>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-minus>", lambda e: self.change_font_size(-1))
        self.root.bind("<Control-KP_Add>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KP_Subtract>", lambda e: self.change_font_size(-1))

    def change_font_size(self, delta):
        """Processa o zoom da tela recalculando tamanhos e cabeçalhos em negrito."""
        self.current_font_size = max(8, min(24, self.current_font_size + delta))
        
        # 1. Atualiza o texto do Chat
        self.chat_display.configure(font=("Segoe UI", self.current_font_size))
        
        # 2. Envia o sinal para redimensionar o editor dinâmico no explorer.py
        self.explorer_pane.update_editor_font(self.current_font_size)
        
        if delta != 0:
            self.log_activity(f"Font size scaled to: {self.current_font_size}")

    # --- CHAT CONSOLE SIMULATION ---
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
        
        # Toda mensagem do chat realiza o salvamento de rascunhos abertos antes de pesquisar
        self.explorer_pane.save_current_file()
        
        threading.Thread(target=self.query_ao_api, args=(prompt,), daemon=True).start()

    def query_ao_api(self, prompt):
        try:
            guild_id = "desktop_env"
            guild_name = "Desktop_Console"
            userid = "999999"
            user_name = "Local_Admin"
            
            persona = (
                "- Você é um mestre de mesa chamado Ao, focado em aventuras de D&D.\n"
                "- Você se diverte criando situações e aventuras engajantes para jogadores e aventureiros.\n"
                "- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas."
            )
            regras = (
                "- Não faça julgamentos de valor;\n"
                "- Pode criar histórias e lugares fictícios, mas não altere informações já definidas, exceto se isso for pedido diretamente;\n"
            )
            
            # Carrega a leitura dinâmica de arquivos
            info = pu.carregar_phaeton()
            extra = detectar_intencao(prompt)
            memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)
            
            self.log_activity("Querying Gemini on dynamic file contents...")
            
            # Unificação no padrão do ask_gemini
            system_instruction = f"{persona}\n\n{regras}"
            conteudo_prompt = ""
            if info:
                conteudo_prompt += f"--- CONTEXTO ATUAL DO MUNDO ({pu.PASTA_PROJETO}) ---\n{info}\n\n"
            if extra:
                conteudo_prompt += f"--- CONTEXTO ADICIONAL DE INTENÇÃO ---\n{extra}\n\n"
            if memorias:
                conteudo_prompt += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
            conteudo_prompt += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"

            resposta = ask_gemini(
                contents=conteudo_prompt,
                system_instruction=system_instruction,
                temperature=0.65
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
            self.log_activity(f"Error building chat execution: {e}")
            self.root.after(0, lambda: self.append_to_chat("System", f"Execution error: {e}"))

    # --- ENGINE DE DISCORD ---
    
    def start_discord_bot_thread(self):
        threading.Thread(target=self.run_discord_bot, daemon=True).start()

    def run_discord_bot(self):
        try:
            self.log_activity("Launching background Discord runner...")
            from main import discordclient, TOKEN
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.discord_loop = loop
            
            # Ajuste de cores para contraste do status no tema escuro
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Online", foreground="#10b981"))
            self.log_activity("Discord server instance online.")
            
            loop.run_until_complete(discordclient.start(TOKEN))
        except Exception as e:
            self.log_activity(f"Discord exception occurred: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Offline/Error", foreground="#ef4444"))
        finally:
                # Quando o loop termina (seja por erro ou por close() pedido no shutdown),
                # garantimos que ele seja fechado corretamente para liberar recursos.
                self.discord_loop = None
    def on_closing(self):
        """Garante o salvamento automático do rascunho em edição e o encerramento limpo da conexão com o Discord caso a janela seja fechada."""
        self.log_activity("Shutting down... saving open files...")
        self.explorer_pane.save_current_file()

        # --- ENCERRAMENTO SEGURO DO BOT DO DISCORD ---
        # discordclient.close() é uma coroutine e o bot está rodando em outra thread,
        # com seu próprio event loop (self.discord_loop). Por isso não podemos chamar
        # await diretamente aqui; usamos run_coroutine_threadsafe para agendar o close()
        # dentro do loop correto, de forma segura entre threads.
        if self.discord_loop and self.discord_loop.is_running():
            from main import discordclient
            self.log_activity("Closing Discord connection...")
            future = asyncio.run_coroutine_threadsafe(discordclient.close(), self.discord_loop)
            try:
                # Espera até 5 segundos pelo fechamento, para não travar o app indefinidamente
                future.result(timeout=5)
            except Exception as e:
                self.log_activity(f"Warning: Discord close did not finish cleanly: {e}")
        self.root.destroy()

    # --- ENGINE DE EXPANSOR ---
    def start_expander_thread(self):
        if self.expander_running:
            messagebox.showwarning("Warning", "The expander task is currently running.")
            return
            
        self.expander_running = True
        self.btn_expander.config(state=tk.DISABLED)
        self.lbl_expander.config(text="Expander status: Working...", foreground="#60a5fa")
        self.log_activity("Spawning child task for file expansion...")
        
        # Garante o auto-salvamento do arquivo atualmente editado antes do expander iniciar a leitura
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
        self.lbl_expander.config(text=f"Expander status: {status}", foreground="#e3e3e3")
        # Atualiza a árvore de arquivos dinamicamente de forma segura
        self.explorer_pane.refresh_tree()

    # --- ENGINE DE WORLD BUILDER ---
    def start_worldbuilder_thread(self):
        self.worldbuilder_objective_value = (self.worldbuilder_objective.get().strip())
        
        if not self.worldbuilder_objective_value:
            self.worldbuilder_objective_value = ("Completar o Projeto")
        
        if self.worldbuilder_running:
            messagebox.showwarning(
                "Warning",
                "The WorldBuilder task is currently running."
            )
            return
        self.worldbuilder_running = True
        self.btn_worldbuilder.config(
            state=tk.DISABLED
        )
        self.lbl_worldbuilder.config(
            text="WorldBuilder status: Working...",
            foreground="#60a5fa"
        )
        self.log_activity(
            "Spawning child task for WorldBuilder..."
        )
        self.explorer_pane.save_current_file()
        threading.Thread(
            target=self.run_worldbuilder_task,
            daemon=True
        ).start()

    def run_worldbuilder_task(self):
        try:
            import wbuilder
            self.log_activity(
                "Starting autonomous WorldBuilder..."
            )
            objective = self.worldbuilder_objective_value

            iterations = wbuilder.iterationschoice(objective)

            if iterations is None:
                iterations = 1
            self.log_activity(
                f"Gemini decided on {iterations} iterations."
            )
            
            wbuilder.taskplanner(iterations,objective)

            self.log_activity(
                "WorldBuilder completed successfully."
            )
            self.finished_worldbuilder_ui_update(
                "Task Finished"
            )
        except Exception as e:
            self.log_activity(
                f"WorldBuilder encountered an issue: {e}"
            )
            self.finished_worldbuilder_ui_update(
                "Failed (Error)"
            )

    def finished_worldbuilder_ui_update(self, status):
        self.worldbuilder_running = False
        self.root.after(0, self._safe_finished_worldbuilder, status)

    def _safe_finished_worldbuilder(self, status):
        self.btn_worldbuilder.config(state=tk.NORMAL)
        self.lbl_worldbuilder.config(text=f"WorldBuilder status: {status}", foreground="#e3e3e3")
        self.explorer_pane.refresh_tree()

if __name__ == "__main__":
    root = tk.Tk()
    app = AoDesktopApp(root)
    root.mainloop()
    
