import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import project_utils as pu

class PhaetonExplorerFrame(ttk.Frame):
    def __init__(self, parent, log_callback):
        super().__init__(parent)
        self.log_callback = log_callback
        self.current_file = None
        self.path_to_item = {}  # Mapeia caminhos absolutos para os IDs da Treeview
        self.autosave_timer = None
        
        # Splitter interno horizontal para dividir a árvore de arquivos e o editor de texto
        self.pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)
        
        # --- SUBCOLUNA A: Árvore de Diretórios (Esquerda) ---
        self.tree_frame = ttk.LabelFrame(self.pane, text=" Phaeton Explorer ")
        self.pane.add(self.tree_frame, weight=1)
        
        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tree_ysb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.tree_ysb.set)
        self.tree_ysb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.btn_refresh = ttk.Button(self.tree_frame, text="Refresh Directory", command=self.refresh_tree)
        self.btn_refresh.pack(fill=tk.X, padx=5, pady=5)
        
        # --- SUBCOLUNA B: Painel do Editor de Texto (Direita) ---
        self.editor_frame = ttk.LabelFrame(self.pane, text=" Dynamic Editor (Auto-saves on switch) ")
        self.pane.add(self.editor_frame, weight=2)
        
        # Editor ajustado com as novas cores escuras modernas e bordas planas
        self.editor = scrolledtext.ScrolledText(
            self.editor_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 10), 
            undo=True,
            bg="#1e1e1e",
            fg="#e3e3e3",
            insertbackground="white",
            selectbackground="#0f766e",
            selectforeground="white",
            bd=0,
            highlightthickness=0
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Inicializa o editor bloqueado até que um arquivo seja selecionado
        self.editor.insert("1.0", "--- Select a file to view and edit ---")
        self.editor.config(state=tk.DISABLED)
        self.editor.bind("<KeyRelease>",self.on_key_release)
        # Menu de contexto clássico (Clique direito) estilizado no novo dark mode
        self.context_menu = tk.Menu(
            self, 
            tearoff=0,
            bg="#1e1e1e",
            fg="#e3e3e3",
            activebackground="#0f766e",
            activeforeground="white",
            bd=1,
            relief=tk.FLAT
        )
        
        # Eventos do Treeview
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu) # Windows/Linux
        self.tree.bind("<Button-2>", self.show_context_menu) # macOS
        
        # Sincronização inicial do diretório
        self.refresh_tree()
        

        
        
    def on_key_release(self, event):
        # Cancela o temporizador anterior se houver nova digitação
        if self.autosave_timer:
            self.after_cancel(self.autosave_timer)
        # Agenda o salvamento para 5000ms (5 segundos)
        self.autosave_timer = self.after(5000, self.save_current_file_on_timer)
        
    def save_current_file_on_timer(self):
        self.autosave_timer = None
        self.save_current_file()

    def get_open_folders(self):
        abertas = []
        def walk(item):
            values = self.tree.item(item, "values")
            if values and self.tree.item(item, "open"):
                abertas.append(os.path.abspath(values[0]))
            for child in self.tree.get_children(item):
                walk(child)
        for root in self.tree.get_children():
            walk(root)
        return abertas
    
    def restore_open_folders(self, folders):
        def walk(item):
            values = self.tree.item(item, "values")
            if values:
                path_abs = os.path.abspath(values[0])
                if path_abs in folders:
                    self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                walk(child)
        for root in self.tree.get_children():
            walk(root)

    # --- ATUALIZAÇÃO DA ÁRVORE DE DIRETÓRIOS ---
    def refresh_tree(self):
        nome_pasta = pu.PASTA_PROJETO
        current_file = self.current_file
        open_folders = self.get_open_folders()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.path_to_item.clear()
        
        nome_pasta = pu.PASTA_PROJETO
        pasta_projeto = pu.CAMINHO_PROJETO
        
        # Garante a existência da pasta antes de tentar povoar a árvore
        os.makedirs(pasta_projeto, exist_ok=True)
        
        root_node = self.tree.insert("", "end", text=f"📁 {nome_pasta}", open=True, values=[pasta_projeto])
        self.path_to_item[os.path.abspath(pasta_projeto)] = root_node
        
        self.populate_tree(root_node, pasta_projeto)
        self.restore_open_folders(open_folders)
        self.restore_current_file(current_file)
        self.log_callback("File explorer tree synchronized.")

    def populate_tree(self, parent_node, path):
        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                
                # Se não for pasta, verifica se é markdown (.md)
                if not is_dir:
                    if not item.lower().endswith(".md"):
                        continue
                
                icon = "📁 " if is_dir else "📄 "
                node = self.tree.insert(
                    parent_node, "end", text=f"{icon}{item}", open=False, values=[item_path]
                )
                
                # Armazena o mapeamento do caminho absoluto para o ID do nó
                self.path_to_item[os.path.abspath(item_path)] = node
                
                if is_dir:
                    self.populate_tree(node, item_path)
        except Exception as e:
            self.log_callback(f"Error accessing subfolder {path}: {e}")

    def restore_current_file(self, current_file):
        if not current_file:
            return

        caminho = os.path.abspath(current_file)
        item = self.path_to_item.get(caminho)

        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)

    # --- SALVAMENTO AUTOMÁTICO E SELEÇÃO DE ARQUIVOS ---
    def save_current_file(self):
        """Salva as alterações pendentes no arquivo atual."""
        self.autosave_timer = None
        if self.current_file and os.path.isfile(self.current_file):
            try:
                conteudo = self.editor.get("1.0", tk.END)
                if conteudo.endswith("\n"):
                    conteudo = conteudo[:-1]
                
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(conteudo)
                self.log_callback(f"Auto-saved file changes: {os.path.basename(self.current_file)}")
            except Exception as e:
                self.log_callback(f"Auto-save failed for {self.current_file}: {e}")

    def on_select(self, event):
        """Trata o clique único. Executa o auto-save do arquivo anterior e carrega o novo."""
        selected_item = self.tree.selection()
        if not selected_item:
            return
            
        item_values = self.tree.item(selected_item[0], "values")
        if not item_values:
            return
            
        novo_caminho = item_values[0]
        
        # Se for o mesmo arquivo que já está aberto, não faz nada
        if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(novo_caminho):
            return
            # Cancela qualquer salvamento temporizado pendente para evitar gravação cruzada
        if self.autosave_timer:
            self.after_cancel(self.autosave_timer)
            self.autosave_timer = None
            
        # 1. Salva automaticamente o arquivo anterior
        self.save_current_file()
        
        # 2. Carrega as informações do novo arquivo selecionado
        if os.path.isfile(novo_caminho):
            self.current_file = novo_caminho
            self.editor.config(state=tk.NORMAL)
            try:
                with open(novo_caminho, "r", encoding="utf-8") as f:
                    texto = f.read()
            except UnicodeDecodeError:
                try:
                    with open(novo_caminho, "r", encoding="latin1") as f:
                        texto = f.read()
                except Exception:
                    texto = ""
                    
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", texto)
        else:
            # Seleção de diretório: desabilita o painel de edição
            self.current_file = None
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", f"--- Directory Selected: {os.path.basename(novo_caminho)} ---")
            self.editor.config(state=tk.DISABLED)

    # --- DUPLO CLIQUE ---
    def on_double_click(self, event):
        """Executa a chamada nativa do sistema operacional para abrir o arquivo no editor padrão."""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_values = self.tree.item(selected_item[0], "values")
        if not item_values:
            return
        
        caminho = item_values[0]
        if os.path.isfile(caminho):
            try:
                self.log_callback(f"Opening natively: {os.path.basename(caminho)}")
                if os.name == 'nt':  # Windows
                    os.startfile(caminho)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(('open', caminho))
                else:  # Linux
                    subprocess.call(('xdg-open', caminho))
            except Exception as e:
                self.log_callback(f"Error opening native app: {e}")

    # --- MENU DE CONTEXTO E OPERAÇÕES DE ARQUIVOS ---
    def show_context_menu(self, event):
        """Renderiza o menu pop-up de opções ao clicar com o botão direito."""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            selected_item = self.tree.selection()[0]
            item_values = self.tree.item(selected_item, "values")
            if not item_values:
                return
            caminho = item_values[0]
            
            # Limpa itens anteriores do menu pop-up
            self.context_menu.delete(0, tk.END)
            
            # Opções dinâmicas com base na seleção
            if os.path.isdir(caminho):
                self.context_menu.add_command(label="📄 New File...", command=lambda: self.create_new_file(caminho))
                self.context_menu.add_command(label="📁 New Folder...", command=lambda: self.create_new_folder(caminho))
                self.context_menu.add_separator()
                
            self.context_menu.add_command(label="✏️ Rename...", command=lambda: self.rename_item(caminho))
            self.context_menu.add_command(label="❌ Delete", command=lambda: self.delete_item(caminho))
            
            self.context_menu.post(event.x_root, event.y_root)

    def create_new_file(self, parent_dir):
        nome = simpledialog.askstring("New File", "Enter the markdown filename (e.g., history.md):", parent=self)
        if nome:
            if not nome.endswith(".md"):
                nome += ".md"
            caminho_arquivo = os.path.join(parent_dir, nome)
            if os.path.exists(caminho_arquivo):
                messagebox.showerror("Error", "A file with this name already exists.")
                return
            try:
                with open(caminho_arquivo, "w", encoding="utf-8") as f:
                    f.write(f"# {nome.replace('.md', '').title()}\n\n<-- TODO: Write down details here.")
                self.log_callback(f"Created file: {nome}")
                self.refresh_tree()
                self.select_path_in_tree(caminho_arquivo)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create file: {e}")

    def create_new_folder(self, parent_dir):
        nome = simpledialog.askstring("New Folder", "Enter the folder name:", parent=self)
        if nome:
            caminho_pasta = os.path.join(parent_dir, nome)
            if os.path.exists(caminho_pasta):
                messagebox.showerror("Error", "A folder with this name already exists.")
                return
            try:
                os.makedirs(caminho_pasta, exist_ok=True)
                self.log_callback(f"Created folder: {nome}")
                self.refresh_tree()
                self.select_path_in_tree(caminho_pasta)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create folder: {e}")

    def rename_item(self, caminho):
        diretorio_pai = os.path.dirname(caminho)
        nome_antigo = os.path.basename(caminho)
        
        novo_nome = simpledialog.askstring("Rename", f"Enter new name for {nome_antigo}:", initialvalue=nome_antigo, parent=self)
        if novo_nome and novo_nome != nome_antigo:
            novo_caminho = os.path.join(diretorio_pai, novo_nome)
            if os.path.exists(novo_caminho):
                messagebox.showerror("Error", "Target path already exists.")
                return
            try:
                # Se for o arquivo atualmente aberto no editor, fecha-o antes de renomear
                esta_aberto = (self.current_file and os.path.abspath(self.current_file) == os.path.abspath(caminho))
                if esta_aberto:
                    self.save_current_file()
                    self.current_file = None
                    
                os.rename(caminho, novo_caminho)
                self.log_callback(f"Renamed: {nome_antigo} -> {novo_nome}")
                self.refresh_tree()
                
                # Se estava aberto, seleciona o arquivo renomeado e carrega seu novo caminho
                if esta_aberto:
                    self.select_path_in_tree(novo_caminho)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename: {e}")

    def delete_item(self, caminho):
        nome = os.path.basename(caminho)
        confirmacao = messagebox.askyesno(
            "Confirm Delete", f"Are you sure you want to delete '{nome}'?\nThis cannot be undone.", parent=self
        )
        if confirmacao:
            try:
                # Limpa o painel de edição se o arquivo apagado for o que está aberto
                if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(caminho):
                    self.current_file = None
                    self.editor.config(state=tk.NORMAL)
                    self.editor.delete("1.0", tk.END)
                    self.editor.config(state=tk.DISABLED)
                    
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho)
                    self.log_callback(f"Deleted folder: {nome}")
                else:
                    os.remove(caminho)
                    self.log_callback(f"Deleted file: {nome}")
                    
                self.refresh_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete item: {e}")

    def select_path_in_tree(self, caminho_alvo):
        """Busca recursivamente e seleciona visualmente um caminho na Árvore."""
        def procurar(node):
            node_path = self.tree.item(node, "values")
            if node_path and os.path.abspath(node_path[0]) == os.path.abspath(caminho_alvo):
                self.tree.selection_set(node)
                self.tree.see(node)
                return True
            for child in self.tree.get_children(node):
                if procurar(child):
                    return True
            return False
            
        for item_raiz in self.tree.get_children():
            if procurar(item_raiz):
                break

    # --- SUPORTE A REDIMENSIONAMENTO DE FONTE ---
    def update_editor_font(self, font_size):
        """Ajusta dinamicamente a fonte do painel de escrita."""
        self.editor.configure(font=("Consolas", font_size))
        
    
