import os
import sys
import threading
import time
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Import do novo módulo de visualização e arquivos e o gerenciador de memória
import explorer
import memory

class AoDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ao Multiverse Console")
        self.root.geometry("1250x650")
        self.root.minsize(1000, 500)
        self.root.state("zoomed")  # Windows
        
        # Define o plano de fundo da janela mestre para combinar com o Dark Mode
        self.root.configure(bg="#1e1e1e")
        
        # Seta a fonte padrão inicial de controle
        self.current_font_size = 11
        
        # Vincula o evento de fechamento seguro da janela para realizar auto-salvamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Aplica a paleta moderna de Dark Mode usando o baseline 'clam'
        self.setup_dark_style()
        
        # Estados internos das engines de background
        self.discord_running = False
        self.expander_running = False
        
        # Constrói o layout de 3 colunas principais
        self.setup_ui()
        
        # Mapeia os atalhos universais de Zoom de teclado (Ctrl + e Ctrl -)
        self.setup_shortcuts()
        
        # Inicializa o tamanho de fonte unificado em toda a interface
        self.change_font_size(0)
        
        # Inicializa a sincronização do Discord Bot em segundo plano
        self.start_discord_bot_thread()

    def setup_dark_style(self):
        """Configura uma paleta dark mode uniforme em todos os elementos ttk."""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure('.', 
            background='#1e1e1e', 
            foreground='#e1e1e1', 
            fieldbackground='#2d2d2d',
            font=('Segoe UI', 10),
            bordercolor='#3e3e42',
            lightcolor='#1e1e1e',
            darkcolor='#1e1e1e'
        )
        
        self.style.map('.', 
            background=[('active', '#3e3e42'), ('disabled', '#1e1e1e')],
            foreground=[('disabled', '#606060')]
        )
        
        self.style.configure('TPanedwindow', background='#1e1e1e')
        self.style.configure('Sash', background='#3e3e42', bordercolor='#3e3e42', sashthickness=4)
        
        self.style.configure('TLabelframe', 
            background='#1e1e1e', 
            bordercolor='#3e3e42',
            borderwidth=1
        )
        self.style.configure('TLabelframe.Label', 
            background='#1e1e1e', 
            foreground='#569cd6', 
            font=('Segoe UI', 10, 'bold')
        )
        
        self.style.configure('TButton', 
            background='#2d2d2d', 
            foreground='#e1e1e1', 
            bordercolor='#3e3e42',
            lightcolor='#3e3e42',
            darkcolor='#1e1e1e',
            borderwidth=1
        )
        self.style.map('TButton', 
            background=[('active', '#3e3e42'), ('pressed', '#1e1e1e')],
            foreground=[('active', '#ffffff')]
        )
        
        self.style.configure('TEntry', 
            fieldbackground='#2d2d2d', 
            foreground='#e1e1e1',
            bordercolor='#3e3e42',
            lightcolor='#2d2d2d',
            darkcolor='#2d2d2d'
        )
        
        self.style.configure('Treeview', 
            background='#2d2d2d', 
            foreground='#e1e1e1', 
            fieldbackground='#2d2d2d',
            bordercolor='#3e3e42',
            borderwidth=1,
            rowheight=22
        )
        self.style.map('Treeview', 
            background=[('selected', '#007acc')], 
            foreground=[('selected', '#ffffff')]
        )
        self.style.configure('Heading', 
            background='#1e1e1e', 
            foreground='#569cd6', 
            bordercolor='#3e3e42',
            font=('Segoe UI', 9, 'bold')
        )
        self.style.map('Heading',
            background=[('active', '#3e3e42')]
        )
        
        self.style.configure('Vertical.TScrollbar', 
            background='#2d2d2d', 
            troughcolor='#1e1e1e', 
            bordercolor='#3e3e42', 
            lightcolor='#2d2d2d',
            darkcolor='#2d2d2d',
            arrowcolor='#e1e1e1'
        )
        self.style.map('Vertical.TScrollbar', 
            background=[('active', '#3e3e42')]
        )

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- COLUNA 1: Dynamic Explorer & Editor Pane (explorer.py) ---
        self.explorer_pane = explorer.PhaetonExplorerFrame(main_paned, self.log_activity)
        main_paned.add(self.explorer_pane, weight=2)
        
        # --- COLUNA 2: Chat Box (Centro) ---
        chat_frame = ttk.LabelFrame(main_paned, text=" Chat with Ao (Simulated) ")
        main_paned.add(chat_frame, weight=2)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            font=("Segoe UI", 10),
            bg="#2d2d2d",
            fg="#e1e1e1",
            insertbackground="white",
            selectbackground="#007acc",
            selectforeground="white"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.chat_display.tag_config("You", foreground="#007ACC", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("Ao", foreground="#2C8558", font=("Segoe UI", 10, "bold"))
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
        
        # Painel de Ações
        actions_frame = ttk.LabelFrame(sidebar_frame, text=" Tools ")
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_expander = ttk.Button(
            actions_frame, text="Run Expander Task", command=self.start_expander_thread
        )
        self.btn_expander.pack(fill=tk.X, padx=10, pady=5)
        
        # Adição dos Botões Físicos de Ajuste de Fonte na barra de ferramentas
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
            bg="#2d2d2d",
            fg="#e1e1e1",
            insertbackground="white",
            selectbackground="#007acc",
            selectforeground="white"
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.append_to_chat("System", "Multiverse local console connected. You can start typing below.")

    # --- MAPEAMENTO DE ATALHOS DE ZOOM (Ctrl + e Ctrl -) ---
    def setup_shortcuts(self):
        """Vincula atalhos físicos do Windows para controle rápido de zoom."""
        # Combinações para teclados internacionais e teclados numéricos
        self.root.bind("<Control-KeyPress-equal>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-plus>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KeyPress-minus>", lambda e: self.change_font_size(-1))
        self.root.bind("<Control-KP_Add>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-KP_Subtract>", lambda e: self.change_font_size(-1))

    def change_font_size(self, delta):
        """Processa o zoom da tela recalculando tamanhos e cabeçalhos em negrito."""
        # Limita o tamanho de fonte entre 8 (mínimo) e 24 (máximo)
        self.current_font_size = max(8, min(24, self.current_font_size + delta))
        
        # 1. Atualiza o texto do Chat
        self.chat_display.configure(font=("Segoe UI", self.current_font_size))
        
        # 2. Atualiza as Tags em negrito ("You" e "Ao") para crescerem proporcionalmente
        #self.chat_display.tag_config("You", foreground="#569cd6", font=("Segoe UI", self.current_font_size, "bold"))
        #self.chat_display.tag_config("Ao", foreground="#4ec9b0", font=("Segoe UI", self.current_font_size, "bold"))
        #self.chat_display.tag_config("System", foreground="#808080", font=("Segoe UI", max(7, self.current_font_size - 1), "italic"))
        
        # 3. Atualiza os Logs secundários do console (levemente menores)
        #self.log_display.configure(font=("Consolas", max(7, self.current_font_size - 2)))
        
        # 4. Envia o sinal para redimensionar o editor dinâmico no explorer.py
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
            from main import carregar_phaeton, detectar_intencao, gerar_resposta_google, geminiclient
            
            guild_id = "desktop_env"
            guild_name = "Desktop_Console"
            userid = "999999"
            user_name = "Local_Admin"
            
            persona = (
                "[Personalidade]\n"
                "- Você é Ao, o criador do universo. Está aqui para responder dúvidas com gentileza e sabedoria.\n"
                "- Aja como o criador lidando com suas criações, contente em ajudar.\n"
                "- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas."
            )
            regras = (
                "[REGRAS]\n"
                "- Não ofereça e não peça por mais informações;\n"
                "- Responda de forma clara e concisa;\n"
                "- Não faça julgamentos de valor;\n"
                "- Pode criar histórias e lugares fictícios, mas não altere informações já definidas;\n"
            )
            
            # Carrega a leitura dinâmica de arquivos
            info = carregar_phaeton()
            extra = detectar_intencao(prompt)
            memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)
            
            self.log_activity("Querying Gemini on dynamic file contents...")
            resposta = gerar_resposta_google(prompt, extra, info, persona, regras, memorias)
            
            if resposta:
                finalz = [".", "!", "?"]
                if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
                    resposta = memory.trim_incomplete_sentences(resposta)
                
                self.root.after(0, lambda: self.append_to_chat("Ao", resposta))
                memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta, geminiclient)
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
            
            # Ajuste de cores para contraste do status no tema escuro
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Online", foreground="#4ec9b0"))
            self.log_activity("Discord server instance online.")
            
            loop.run_until_complete(discordclient.start(TOKEN))
        except Exception as e:
            self.log_activity(f"Discord exception occurred: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Offline/Error", foreground="#F44336"))

    # --- ENGINE DE EXPANSOR ---
    def start_expander_thread(self):
        if self.expander_running:
            messagebox.showwarning("Warning", "The expander task is currently running.")
            return
            
        self.expander_running = True
        self.btn_expander.config(state=tk.DISABLED)
        self.lbl_expander.config(text="Expander status: Working...", foreground="#569cd6")
        self.log_activity("Spawning child task for file expansion...")
        
        # Garante o auto-salvamento do arquivo atualmente editado antes do expander iniciar a leitura
        self.explorer_pane.save_current_file()
        
        threading.Thread(target=self.run_expander_task, daemon=True).start()

    def run_expander_task(self):
        try:
            import expander
            instrucoes = expander.obter_instrucoes()
            if not instrucoes:
                self.log_activity("Expander Error: 'vision.md' rules file missing.")
                self.finished_expander_ui_update("Failed (No rules)")
                return
            
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
        self.lbl_expander.config(text=f"Expander status: {status}", foreground="#e1e1e1")
        # Atualiza a árvore de arquivos dinamicamente de forma segura
        self.explorer_pane.refresh_tree()

    # --- FECHAMENTO SEGURO DO APLICATIVO ---
    def on_closing(self):
        """Garante o salvamento automático do rascunho em edição caso a janela seja fechada."""
        self.log_activity("Shutting down... saving open files...")
        self.explorer_pane.save_current_file()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AoDesktopApp(root)
    root.mainloop()