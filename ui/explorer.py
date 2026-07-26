import os, sys, shutil, subprocess, threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import engine.project_utils as pu
import engine.wbuilder as wb

class ExplorerFrame(ttk.Frame):
    def __init__(self, parent, log_callback, toast_callback=None):
        super().__init__(parent)
        self.log_callback = log_callback
        self.toast_callback = toast_callback
        self.current_file = None
        self.path_to_item = {}  # Mapeia caminhos absolutos para os IDs da Treeview
        self.autosave_timer = None
        
        # Área de transferência interna para Copiar/Recortar/Colar
        self.clipboard_item = None  # Dict: {"path": str, "mode": "copy" | "cut"}

        # Variáveis de controle para Drag and Drop
        self._drag_item = None
        self._drag_path = None

        # Splitter interno horizontal para dividir a árvore de arquivos e o editor de texto
        self.pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # --- SUBCOLUNA A: Árvore de Diretórios (Esquerda) ---
        self.tree_frame = ttk.LabelFrame(self.pane, text=" Explorer ")
        self.pane.add(self.tree_frame, weight=1)

        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree_ysb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.tree_ysb.set)
        self.tree_ysb.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_refresh = ttk.Button(self.tree_frame, text="Atualizar Diretório", command=self.refresh_tree)
        self.btn_refresh.pack(fill=tk.X, padx=5, pady=5)

        # --- SUBCOLUNA B: Painel do Editor de Texto (Direita) ---
        self.editor_frame = ttk.LabelFrame(self.pane, text=" Editor Dinâmico (Auto-salva ao alternar) ")
        self.pane.add(self.editor_frame, weight=2)

        self.editor = scrolledtext.ScrolledText(
            self.editor_frame,
            wrap=tk.WORD,
            font=("Consolas", 12),
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

        self.editor.insert("1.0", "--- Selecione um arquivo para visualizar e editar ---")
        self.editor.config(state=tk.DISABLED)
        self.editor.bind("<KeyRelease>", self.on_key_release)

        # Menu de contexto clássico (Clique direito)
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
        self.tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux
        self.tree.bind("<Button-2>", self.show_context_menu)  # macOS

        # Eventos de Drag and Drop (Arrastar e Soltar)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_release)

        # Sincronização inicial
        self.refresh_tree()

    def toast(self, msg):
        if self.toast_callback:
            self.toast_callback(msg)

    # --- ARRASTAR E SOLTAR (DRAG & DROP) ---
    def on_drag_start(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            values = self.tree.item(iid, "values")
            if values:
                self._drag_item = iid
                self._drag_path = values[0]

    def on_drag_release(self, event):
        if not self._drag_item or not self._drag_path:
            return

        target_iid = self.tree.identify_row(event.y)
        if not target_iid or target_iid == self._drag_item:
            self._drag_item = None
            self._drag_path = None
            return

        target_values = self.tree.item(target_iid, "values")
        if not target_values:
            self._drag_item = None
            self._drag_path = None
            return

        src_path = os.path.abspath(self._drag_path)
        target_path = os.path.abspath(target_values[0])

        dest_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)

        # Impede mover uma pasta para dentro dela mesma
        if os.path.isdir(src_path) and dest_dir.startswith(src_path):
            self.toast("⚠️ Não é possível mover uma pasta para dentro dela mesma.")
            self._drag_item = None
            self._drag_path = None
            return

        dest_path = os.path.join(dest_dir, os.path.basename(src_path))

        if os.path.abspath(src_path) == os.path.abspath(dest_path):
            self._drag_item = None
            self._drag_path = None
            return

        try:
            shutil.move(src_path, dest_path)
            nome_item = os.path.basename(src_path)
            nome_destino = os.path.basename(dest_dir)
            msg = f"📦 Movido '{nome_item}' para '{nome_destino}'"
            self.log_callback(msg)
            self.toast(msg)
            self.refresh_tree()
            self.select_path_in_tree(dest_path)
        except Exception as e:
            messagebox.showerror("Erro ao mover", f"Falha ao mover item: {e}")
        finally:
            self._drag_item = None
            self._drag_path = None

    # --- AUTO-SAVE E EDIÇÃO ---
    def on_key_release(self, event):
        if self.autosave_timer:
            self.after_cancel(self.autosave_timer)
        self.autosave_timer = self.after(5000, self.save_current_file_on_timer)

    def save_current_file_on_timer(self):
        self.autosave_timer = None
        self.save_current_file()

    def save_current_file(self):
        self.autosave_timer = None
        if self.current_file and os.path.isfile(self.current_file):
            try:
                conteudo = self.editor.get("1.0", tk.END)
                if conteudo.endswith("\n"):
                    conteudo = conteudo[:-1]

                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(conteudo)
                self.log_callback(f"Auto-salvo: {os.path.basename(self.current_file)}")
            except Exception as e:
                self.log_callback(f"Falha ao auto-salvar {self.current_file}: {e}")

    def on_select(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return

        item_values = self.tree.item(selected_item[0], "values")
        if not item_values:
            return

        novo_caminho = item_values[0]

        if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(novo_caminho):
            return

        arquivo_anterior = self.current_file
        if self.autosave_timer:
            self.after_cancel(self.autosave_timer)
            self.autosave_timer = None

        self.save_current_file()

        if arquivo_anterior:
            self.process_saved_file(arquivo_anterior)

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
            self.current_file = None
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", f"--- Diretório Selecionado: {os.path.basename(novo_caminho)} ---")
            self.editor.config(state=tk.DISABLED)

    def process_saved_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                texto = f.read()
            if any(tag in texto for tag in pu.TAG_ALVO):
                nome_arq = os.path.basename(path)
                self.log_callback(f"TODO encontrado em {nome_arq}")
                self.toast(f"⚡ TODO detectado em '{nome_arq}'! Executando Expander...")
                threading.Thread(target=wb.improvefile, args=(path,), daemon=True).start()
        except Exception as e:
            self.log_callback(f"Erro analisando TODO: {e}")

    # --- MENU DE CONTEXTO E OPERAÇÕES COMPLETAS DO WINDOWS ---
    def show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            selected_item = self.tree.selection()[0]
            item_values = self.tree.item(selected_item, "values")
            if not item_values:
                return
            caminho = item_values[0]

            self.context_menu.delete(0, tk.END)

            # Opções de Criação
            if os.path.isdir(caminho):
                self.context_menu.add_command(label="📄 Novo Arquivo", command=lambda: self.create_new_file(caminho))
                self.context_menu.add_command(label="📁 Nova Pasta", command=lambda: self.create_new_folder(caminho))
                self.context_menu.add_separator()

            # Copiar / Recortar / Colar
            self.context_menu.add_command(label="📋 Copiar", command=lambda: self.copy_item(caminho))
            self.context_menu.add_command(label="✂️ Recortar", command=lambda: self.cut_item(caminho))

            pode_colar = self.clipboard_item and os.path.exists(self.clipboard_item["path"])
            colar_state = tk.NORMAL if pode_colar else tk.DISABLED
            self.context_menu.add_command(label="📥 Colar", command=lambda: self.paste_item(caminho), state=colar_state)

            self.context_menu.add_command(label="📑 Duplicar", command=lambda: self.duplicate_item(caminho))
            self.context_menu.add_separator()

            # Renomear e Deletar
            self.context_menu.add_command(label="✏️ Renomear...", command=lambda: self.rename_item(caminho))
            self.context_menu.add_command(label="❌ Deletar", command=lambda: self.delete_item(caminho))
            self.context_menu.add_separator()

            # Abrir no Explorador Nativo do SO
            self.context_menu.add_command(label="📂 Mostrar no Explorador de Arquivos", command=lambda: self.reveal_in_explorer(caminho))

            self.context_menu.post(event.x_root, event.y_root)

    def copy_item(self, caminho):
        self.clipboard_item = {"path": caminho, "mode": "copy"}
        nome = os.path.basename(caminho)
        self.toast(f"📋 Copiado '{nome}' para a área de transferência")

    def cut_item(self, caminho):
        self.clipboard_item = {"path": caminho, "mode": "cut"}
        nome = os.path.basename(caminho)
        self.toast(f"✂️ Recortado '{nome}'")

    def paste_item(self, target_path):
        if not self.clipboard_item or not os.path.exists(self.clipboard_item["path"]):
            self.toast("⚠️ Nenhum item na área de transferência.")
            return

        src = self.clipboard_item["path"]
        mode = self.clipboard_item["mode"]

        dest_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        base_name = os.path.basename(src)
        dest = os.path.join(dest_dir, base_name)

        if os.path.abspath(src) == os.path.abspath(dest):
            self.toast("⚠️ Origem e destino são o mesmo caminho.")
            return

        try:
            if mode == "cut":
                shutil.move(src, dest)
                self.clipboard_item = None
                msg = f"✂️ Recortado e colado '{base_name}'"
            else:
                if os.path.isdir(src):
                    shutil.copytree(src, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dest)
                msg = f"📋 Colado '{base_name}'"

            self.log_callback(msg)
            self.toast(msg)
            self.refresh_tree()
            self.select_path_in_tree(dest)
        except Exception as e:
            messagebox.showerror("Erro ao Colar", f"Falha ao colar item: {e}")

    def duplicate_item(self, caminho):
        try:
            diretorio = os.path.dirname(caminho)
            nome, ext = os.path.splitext(os.path.basename(caminho))
            novo_nome = f"{nome}_copia{ext}"
            novo_caminho = os.path.join(diretorio, novo_nome)

            counter = 1
            while os.path.exists(novo_caminho):
                novo_nome = f"{nome}_copia_{counter}{ext}"
                novo_caminho = os.path.join(diretorio, novo_nome)
                counter += 1

            if os.path.isdir(caminho):
                shutil.copytree(caminho, novo_caminho)
            else:
                shutil.copy2(caminho, novo_caminho)

            self.toast(f"📑 Duplicado: '{os.path.basename(novo_caminho)}'")
            self.refresh_tree()
            self.select_path_in_tree(novo_caminho)
        except Exception as e:
            messagebox.showerror("Erro ao Duplicar", f"Falha ao duplicar item: {e}")

    def reveal_in_explorer(self, caminho):
        caminho = os.path.normpath(caminho)
        try:
            if os.name == 'nt':  # Windows
                if os.path.isfile(caminho):
                    subprocess.run(['explorer', '/select,', caminho])
                else:
                    os.startfile(caminho)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', '-R' if os.path.isfile(caminho) else '', caminho])
            else:  # Linux
                pasta = os.path.dirname(caminho) if os.path.isfile(caminho) else caminho
                subprocess.call(['xdg-open', pasta])
            self.toast(f"📂 Abrindo no explorador de arquivos...")
        except Exception as e:
            self.log_callback(f"Erro ao abrir explorador nativo: {e}")

    def create_new_file(self, parent_dir):
        nome = simpledialog.askstring("Novo Arquivo", "Coloque o nome do Arquivo (exemplo: Historia.md):", parent=self)
        if nome:
            if not nome.endswith(".md"):
                nome += ".md"
            caminho_arquivo = os.path.join(parent_dir, nome)
            if os.path.exists(caminho_arquivo):
                messagebox.showerror("Erro", "Um arquivo com esse nome já existe.")
                return
            try:
                with open(caminho_arquivo, "w", encoding="utf-8") as f:
                    f.write(f"# {nome.replace('.md', '').title()}\n\n<-- TODO: Crie informações para {nome.replace('.md', '').title()}.")
                self.toast(f"📄 Arquivo criado: '{nome}'")
                self.refresh_tree()
                self.select_path_in_tree(caminho_arquivo)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao criar arquivo: {e}")

    def create_new_folder(self, parent_dir):
        nome = simpledialog.askstring("Nova Pasta", "Coloque o nome da pasta:", parent=self)
        if nome:
            caminho_pasta = os.path.join(parent_dir, nome)
            if os.path.exists(caminho_pasta):
                messagebox.showerror("Erro", "Já existe uma pasta com esse nome.")
                return
            try:
                os.makedirs(caminho_pasta, exist_ok=True)
                self.toast(f"📁 Pasta criada: '{nome}'")
                self.refresh_tree()
                self.select_path_in_tree(caminho_pasta)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao criar pasta: {e}")

    def rename_item(self, caminho):
            diretorio_pai = os.path.dirname(caminho)
            nome_antigo = os.path.basename(caminho)

            novo_nome = simpledialog.askstring("Renomear", f"Entre o novo nome para {nome_antigo}:", initialvalue=nome_antigo, parent=self)
            if novo_nome:
                novo_nome = novo_nome.strip()

                # Se for um arquivo (não pasta) e não terminar com .md, força a extensão
                if os.path.isfile(caminho) and not novo_nome.lower().endswith(".md"):
                    novo_nome += ".md"

                if novo_nome != nome_antigo:
                    novo_caminho = os.path.join(diretorio_pai, novo_nome)
                    if os.path.exists(novo_caminho):
                        messagebox.showerror("Erro", "Já existe um arquivo ou pasta com esse nome.")
                        return
                    try:
                        esta_aberto = (self.current_file and os.path.abspath(self.current_file) == os.path.abspath(caminho))
                        if esta_aberto:
                            self.save_current_file()
                            self.current_file = None

                        os.rename(caminho, novo_caminho)
                        self.toast(f"✏️ Renomeado: '{nome_antigo}' -> '{novo_nome}'")
                        self.refresh_tree()

                        if esta_aberto:
                            self.select_path_in_tree(novo_caminho)
                    except Exception as e:
                        messagebox.showerror("Erro", f"Falha ao Renomear: {e}")

    def delete_item(self, caminho):
        nome = os.path.basename(caminho)
        confirmacao = messagebox.askyesno(
            "Confirmar Exclusão", f"Tem certeza que deseja deletar '{nome}'?\nEsta ação não poderá ser desfeita.", parent=self
        )
        if confirmacao:
            try:
                if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(caminho):
                    self.current_file = None
                    self.editor.config(state=tk.NORMAL)
                    self.editor.delete("1.0", tk.END)
                    self.editor.config(state=tk.DISABLED)

                if os.path.isdir(caminho):
                    shutil.rmtree(caminho)
                else:
                    os.remove(caminho)

                self.toast(f"❌ Deletado: '{nome}'")
                self.refresh_tree()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao deletar item: {e}")

    # --- NAVEGAÇÃO E ATUALIZAÇÃO ---
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

    def refresh_tree(self):
        current_file = self.current_file
        open_folders = self.get_open_folders()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.path_to_item.clear()

        nome_pasta = pu.PASTA_PROJETO
        pasta_projeto = pu.CAMINHO_PROJETO

        os.makedirs(pasta_projeto, exist_ok=True)

        root_node = self.tree.insert("", "end", text=f"📁 {nome_pasta}", open=True, values=[pasta_projeto])
        self.path_to_item[os.path.abspath(pasta_projeto)] = root_node

        self.populate_tree(root_node, pasta_projeto)
        self.restore_open_folders(open_folders)
        self.restore_current_file(current_file)
        self.log_callback("Árvore do diretório sincronizada.")

    def populate_tree(self, parent_node, path):
        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)

                if not is_dir and not item.lower().endswith(".md"):
                    continue

                icon = "📁 " if is_dir else "📄 "
                node = self.tree.insert(
                    parent_node, "end", text=f"{icon}{item}", open=False, values=[item_path]
                )
                self.path_to_item[os.path.abspath(item_path)] = node

                if is_dir:
                    self.populate_tree(node, item_path)
        except Exception as e:
            self.log_callback(f"Erro ao acessar pasta {path}: {e}")

    def restore_current_file(self, current_file):
        if not current_file:
            return
        caminho = os.path.abspath(current_file)
        item = self.path_to_item.get(caminho)
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)

    def select_path_in_tree(self, caminho_alvo):
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

    def on_double_click(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_values = self.tree.item(selected_item[0], "values")
        if not item_values:
            return

        caminho = item_values[0]
        if os.path.isfile(caminho):
            try:
                self.log_callback(f"Abrindo nativamente: {os.path.basename(caminho)}")
                if os.name == 'nt':
                    os.startfile(caminho)
                elif sys.platform == 'darwin':
                    subprocess.call(('open', caminho))
                else:
                    subprocess.call(('xdg-open', caminho))
            except Exception as e:
                self.log_callback(f"Erro ao abrir arquivo nativo: {e}")

    def update_editor_font(self, font_size):
        self.editor.configure(font=("Consolas", font_size))