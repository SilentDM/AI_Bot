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
        
        # Vincula o evento de fechamento seguro da janela para realizar auto-salvamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Configuração visual de estilos
        self.style = ttk.Style()
        self.style.theme_use('vista' if os.name == 'nt' else 'clam')
        
        # Estados internos das engines de background
        self.discord_running = False
        self.expander_running = False
        
        # Constrói o layout de 3 colunas principais
        self.setup_ui()
        
        # Inicializa a sincronização do Discord Bot em segundo plano
        self.start_discord_bot_thread()

    def setup_ui(self):
        # PanedWindow principal responsável pelas divisões redimensionáveis de colunas
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- COLUNA 1: Dynamic Explorer & Editor Pane (Delegado para explorer.py) ---
        self.explorer_pane = explorer.PhaetonExplorerFrame(main_paned, self.log_activity)
        main_paned.add(self.explorer_pane, weight=2)
        
        # --- COLUNA 2: Chat Box (Centro) ---
        chat_frame = ttk.LabelFrame(main_paned, text=" Chat with Ao (Simulated) ")
        main_paned.add(chat_frame, weight=2)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 10)
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
        
        actions_frame = ttk.LabelFrame(sidebar_frame, text=" Tools ")
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_expander = ttk.Button(
            actions_frame, text="Run Expander Task", command=self.start_expander_thread
        )
        self.btn_expander.pack(fill=tk.X, padx=10, pady=10)
        
        log_frame = ttk.LabelFrame(sidebar_frame, text=" Activity Log ")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_display = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 8), height=15
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.append_to_chat("System", "Multiverse local console connected. You can start typing below.")

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
                "- Você é Ao, o criador do universo. Está aqui para responder dúvidas, com gentileza e sabedoria.\n"
                "- Sempre se refira a Ao em primeira pessoa.\n"
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
            
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Online", foreground="#2C8558"))
            self.log_activity("Discord server instance online.")
            
            loop.run_until_complete(discordclient.start(TOKEN))
        except Exception as e:
            self.log_activity(f"Discord exception occurred: {e}")
            self.root.after(0, lambda: self.lbl_discord.config(text="Discord Bot: Offline/Error", foreground="#D32F2F"))

    # --- ENGINE DE EXPANSOR ---
    def start_expander_thread(self):
        if self.expander_running:
            messagebox.showwarning("Warning", "The expander task is currently running.")
            return
            
        self.expander_running = True
        self.btn_expander.config(state=tk.DISABLED)
        self.lbl_expander.config(text="Expander status: Working...", foreground="#007ACC")
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
        self.lbl_expander.config(text=f"Expander status: {status}", foreground="black")
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