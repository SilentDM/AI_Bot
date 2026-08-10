import os, sys, shutil, subprocess, threading, re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from pathlib import Path
import engine.project_utils as pu
import engine.wbuilder as wb

class NewFileDialog(tk.Toplevel):
    """Janela modal para criar um novo arquivo definindo nome e template."""
    def __init__(self, parent, templates_disponiveis):
        super().__init__(parent)
        self.title("Novo Arquivo")
        self.geometry("420x230")
        self.resizable(False, False)
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set()
        
        self.result_filename = None
        self.result_template = None

        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(container, text="Nome do Arquivo:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.entry_nome = ttk.Entry(container, font=("Segoe UI", 10))
        self.entry_nome.pack(fill=tk.X, pady=(0, 14))
        self.entry_nome.focus_set()
        self.entry_nome.bind("<Return>", lambda e: self.on_confirm())

        ttk.Label(container, text="Modelo / Template:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.combo_template = ttk.Combobox(container, values=templates_disponiveis, state="readonly", font=("Segoe UI", 10))
        self.combo_template.set(templates_disponiveis[0] if templates_disponiveis else "Nenhum (Padrão)")
        self.combo_template.pack(fill=tk.X, pady=(0, 20))

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_frame, text="Criar Arquivo", command=self.on_confirm).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def on_confirm(self):
        nome = self.entry_nome.get().strip()
        if not nome:
            messagebox.showwarning("Aviso", "Por favor, digite o nome do arquivo.", parent=self)
            return
        self.result_filename = nome
        self.result_template = self.combo_template.get()
        self.destroy()

class ExplorerFrame(ttk.Frame):
    def __init__(self, parent, log_callback, toast_callback=None, auto_expander_callback=None, ask_ao_callback=None, stats_callback=None):
        super().__init__(parent)
        self.log_callback = log_callback
        self.toast_callback = toast_callback
        self.auto_expander_callback = auto_expander_callback 
        self.ask_ao_callback = ask_ao_callback
        self.stats_callback = stats_callback
        
        self.current_file = None
        self.path_to_item = {}
        self.autosave_timer = None
        self.clipboard_item = None

        # Histórico de navegação (Voltar / Avançar)
        #self.history_back = []
        #self.history_forward = []
        self.history = []
        self.history_index = -1
        self._navigating_history = False
        
        self._drag_item = None
        self._drag_path = None

        self.pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # SUBCOLUNA A: Árvore de Diretórios
        self.tree_frame = ttk.LabelFrame(self.pane)
        self.pane.add(self.tree_frame, weight=1)

        search_bar_frame = ttk.Frame(self.tree_frame)
        search_bar_frame.pack(fill=tk.X, padx=5, pady=(5, 2))

        ttk.Label(search_bar_frame, text="🔍").pack(side=tk.LEFT, padx=(2, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_bar_frame, textvariable=self.search_var, font=("Segoe UI", 9))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.on_search_key_release)

        self.btn_clear_search = ttk.Button(search_bar_frame, text="✕", width=3, command=self.clear_search)
        self.btn_clear_search.pack(side=tk.RIGHT, padx=(2, 0))

        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse", show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        self.tree_ysb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.tree_ysb.set)
        self.tree_ysb.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_refresh = ttk.Button(self.tree_frame, text="Atualizar Diretório", command=self.refresh_tree)
        self.btn_refresh.pack(fill=tk.X, padx=5, pady=5)

        # SUBCOLUNA B: Editor de Texto com Barra de Navegação Superior
        self.editor_frame = ttk.Frame(self.pane)
        self.pane.add(self.editor_frame, weight=2)

        # Barra Superior de Ferramentas / Navegação
        editor_header = ttk.Frame(self.editor_frame)
        editor_header.pack(fill=tk.X, padx=5, pady=(5, 2))

        self.btn_nav_back = ttk.Button(editor_header, text="◀ Voltar", width=8, command=self.go_back)
        self.btn_nav_back.pack(side=tk.LEFT, padx=(0, 2))

        self.btn_nav_forward = ttk.Button(editor_header, text="Avançar ▶", width=8, command=self.go_forward)
        self.btn_nav_forward.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_editor_title = ttk.Label(editor_header, text="Editor Dinâmico", font=("Segoe UI", 9, "bold"), foreground="#10b981",anchor="center")
        self.lbl_editor_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # ScrolledText do Editor
        self.editor = scrolledtext.ScrolledText(
            self.editor_frame, wrap=tk.WORD, font=("Consolas", 12), undo=True,
            bg="#1e1e1e", fg="#e3e3e3", insertbackground="white",
            selectbackground="#0f766e", selectforeground="white", bd=0, highlightthickness=0
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))

        #self.editor.insert("1.0", "--- Selecione um arquivo para visualizar e editar ---")
        self.editor.config(state=tk.DISABLED)
        self.editor.bind("<KeyRelease>", self.on_key_release)

        # Syntax Highlighting
        self.editor.tag_configure("md_h1", font=("Consolas", 15, "bold"), foreground="#10b981")
        self.editor.tag_configure("md_h2", font=("Consolas", 13, "bold"), foreground="#34d399")
        self.editor.tag_configure("md_h3", font=("Consolas", 12, "bold"), foreground="#60a5fa")
        self.editor.tag_configure("md_bold", font=("Consolas", 12, "bold"), foreground="#ffffff")
        self.editor.tag_configure("md_italic", font=("Consolas", 12, "italic"), foreground="#cbd5e1")
        self.editor.tag_configure("md_wikilink", font=("Consolas", 12, "bold", "underline"), foreground="#38bdf8")
        self.editor.tag_configure("md_todo", font=("Consolas", 12, "bold"), foreground="#f97316", background="#2a1205")
        self.editor.tag_configure("md_quote", font=("Consolas", 12, "italic"), foreground="#94a3b8")

        self.editor.tag_bind("md_wikilink", "<Enter>", lambda e: self.editor.config(cursor="hand2"))
        self.editor.tag_bind("md_wikilink", "<Leave>", lambda e: self.editor.config(cursor="xterm"))
        self.editor.tag_bind("md_wikilink", "<Button-1>", self.on_wikilink_click)

        # 🛡️ REGISTRO DE ATALHOS: F2 (Renomear) e Navegação Voltar/Avançar
        self.tree.bind("<F2>", self.on_f2_rename)

        for w in [self, self.editor, self.tree]:
            w.bind("<Alt-Left>", self.go_back)
            w.bind("<Alt-Right>", self.go_forward)
            
            # Tenta registrar botões de mouse estendidos caso a versão do Tcl/SO suporte
            try:
                w.bind("<Button-8>", self.go_back)
                w.bind("<Button-9>", self.go_forward)
            except tk.TclError:
                pass

        # Menus de contexto
        self.context_menu = tk.Menu(self, tearoff=0, bg="#1e1e1e", fg="#e3e3e3", activebackground="#0f766e", activeforeground="white")
        self.editor_context_menu = tk.Menu(self, tearoff=0, bg="#1e1e1e", fg="#e3e3e3", activebackground="#0f766e", activeforeground="white")

        self.editor_context_menu.add_command(label="🏷️ Inserir Tag To-Do", command=self.insert_todo_tag)
        self.editor_context_menu.add_separator()
        self.editor_context_menu.add_command(label="✂️ Recortar", command=lambda: self.editor.event_generate("<<Cut>>"))
        self.editor_context_menu.add_command(label="📋 Copiar", command=lambda: self.editor.event_generate("<<Copy>>"))
        self.editor_context_menu.add_command(label="📥 Colar", command=lambda: self.editor.event_generate("<<Paste>>"))
        self.editor_context_menu.add_separator()
        self.editor_context_menu.add_command(label="Selecionar Tudo", command=lambda: self.editor.tag_add("sel", "1.0", "end"))

        self.editor.bind("<Button-3>", self.show_editor_context_menu)
        self.editor.bind("<Button-2>", self.show_editor_context_menu)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-2>", self.show_context_menu)

        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_release)

        self.refresh_tree()

    def toast(self, msg):
        if self.toast_callback:
            self.toast_callback(msg)

    # --- ATALHOS F2 E NAVEGAÇÃO VOLTAR / AVANÇAR ---
    def on_f2_rename(self, event=None):
        """Aperta F2 para abrir o diálogo de renomear item selecionado."""
        selected = self.tree.selection()
        if selected:
            item_values = self.tree.item(selected[0], "values")
            if item_values:
                self.rename_item(item_values[0])
        return "break"
    
    def _add_to_history(self, caminho):
        """Adiciona o arquivo ao histórico de forma segura."""
        if not hasattr(self, "history"):
            self.history = []
        if not hasattr(self, "history_index"):
            self.history_index = -1
        if not hasattr(self, "_is_navigating"):
            self._is_navigating = False

        if not caminho or not os.path.isfile(caminho) or self._is_navigating:
            return

        caminho_abs = os.path.abspath(caminho)

        if 0 <= self.history_index < len(self.history):
            if os.path.abspath(self.history[self.history_index]) == caminho_abs:
                return

        self.history = self.history[:self.history_index + 1]
        self.history.append(caminho_abs)
        if len(self.history) > 50:
            self.history.pop(0)
        self.history_index = len(self.history) - 1

    def go_back(self, event=None):
        if self.history_index <= 0:
            self.toast("◀ Início do histórico de navegação.")
            return "break"

        self.save_current_file()

        # Recua o ponteiro para o arquivo anterior válido no disco
        target_idx = self.history_index - 1
        while target_idx >= 0 and not os.path.isfile(self.history[target_idx]):
            self.history.pop(target_idx)
            target_idx -= 1

        if target_idx < 0:
            self.history_index = 0
            self.toast("◀ Início do histórico de navegação.")
            return "break"

        self.history_index = target_idx
        target_file = self.history[self.history_index]

        self._is_navigating = True
        try:
            self.select_path_in_tree(target_file)
            self.toast(f"◀ Voltar: '{os.path.basename(target_file)}'")
        finally:
            # Reseta a flag com delay para cobrir o evento assíncrono do Tkinter
            self.after(50, self._reset_navigating_flag)

        return "break"

    def go_forward(self, event=None):
        if self.history_index >= len(self.history) - 1:
            self.toast("▶ Fim do histórico de navegação.")
            return "break"

        self.save_current_file()

        # Avança o ponteiro para o próximo arquivo válido
        target_idx = self.history_index + 1
        while target_idx < len(self.history) and not os.path.isfile(self.history[target_idx]):
            self.history.pop(target_idx)

        if target_idx >= len(self.history):
            self.history_index = len(self.history) - 1
            self.toast("▶ Fim do histórico de navegação.")
            return "break"

        self.history_index = target_idx
        target_file = self.history[self.history_index]

        self._is_navigating = True
        try:
            self.select_path_in_tree(target_file)
            self.toast(f"▶ Avançar: '{os.path.basename(target_file)}'")
        finally:
            self.after(50, self._reset_navigating_flag)

        return "break"

    def _reset_navigating_flag(self):
        self._is_navigating = False

    # --- SYNTAX HIGHLIGHTING & WIKILINKS ---
    def apply_syntax_highlighting(self):
        if str(self.editor.cget("state")) == "disabled":
            return

        for tag in ["md_h1", "md_h2", "md_h3", "md_bold", "md_italic", "md_wikilink", "md_todo", "md_quote"]:
            self.editor.tag_remove(tag, "1.0", tk.END)

        texto = self.editor.get("1.0", tk.END)
        if not texto.strip():
            return

        for match in re.finditer(r'^(#{1,3})\s+(.*)$', texto, re.MULTILINE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            level = len(match.group(1))
            self.editor.tag_add(f"md_h{level}", start_idx, end_idx)

        for match in re.finditer(r'^(>.*)$', texto, re.MULTILINE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.editor.tag_add("md_quote", start_idx, end_idx)

        for match in re.finditer(r'(<--\s*(?:TODO|TO DO|To Do|To-Do|todo):?.*)', texto, re.IGNORECASE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.editor.tag_add("md_todo", start_idx, end_idx)

        for match in re.finditer(r'\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]', texto):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.editor.tag_add("md_wikilink", start_idx, end_idx)

        for match in re.finditer(r'(\*\*[^\*\n]+\*\*)', texto):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.editor.tag_add("md_bold", start_idx, end_idx)

    def on_wikilink_click(self, event):
        try:
            index_clicado = self.editor.index(f"@{event.x},{event.y}")
            intervalo = self.editor.tag_prevrange("md_wikilink", f"{index_clicado}+1c")
            if not intervalo:
                return

            texto_link = self.editor.get(intervalo[0], intervalo[1]).strip()
            match = re.match(r'\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]', texto_link)
            if not match:
                return

            nome_alvo = match.group(1).strip()
            caminho_encontrado = self._encontrar_arquivo_por_nome(nome_alvo)

            if caminho_encontrado:
                self.save_current_file()
                self.select_path_in_tree(str(caminho_encontrado))
                self.toast(f"🔗 Navegando para '{caminho_encontrado.name}'...")
            else:
                resposta = messagebox.askyesno(
                    "Criar Novo Documento",
                    f"O documento para '[[{nome_alvo}]]' não existe.\n\nDeseja criá-lo agora em '{pu.PASTA_PROJETO}'?",
                    parent=self
                )
                if resposta:
                    pasta_destino = os.path.dirname(self.current_file) if self.current_file else str(pu.CAMINHO_PROJETO)
                    nome_md = nome_alvo if nome_alvo.lower().endswith(".md") else f"{nome_alvo}.md"
                    novo_caminho = os.path.join(pasta_destino, nome_md)
                    
                    titulo = nome_alvo.replace('.md', '').replace('_', ' ').title()
                    nome_origem = os.path.basename(self.current_file) if self.current_file else "origem"
                    conteudo_inicial = f"# {titulo}\n\nDocumento criado a partir de wikilink em [[{nome_origem}]]."
                    
                    with open(novo_caminho, "w", encoding="utf-8") as f:
                        f.write(conteudo_inicial)

                    self.toast(f"📄 Documento '{nome_md}' criado com sucesso!")
                    self.refresh_tree()
                    self.select_path_in_tree(novo_caminho)

        except Exception as e:
            self.log_callback(f"Erro ao navegar por wikilink: {e}")

    def _encontrar_arquivo_por_nome(self, nome_alvo):
        alvo_norm = pu.normalizar_nome(nome_alvo)
        raiz = Path(pu.CAMINHO_PROJETO)
        
        candidatos = []
        for arq in raiz.rglob("*.md"):
            if any(part in pu.IGNORELIST for part in arq.parts):
                continue
            if pu.normalizar_nome(arq.stem) == alvo_norm:
                candidatos.append(arq.resolve())

        if not candidatos:
            return None

        def get_version(path_obj):
            match = re.search(r'_v(\d+)$', path_obj.stem, flags=re.IGNORECASE)
            return int(match.group(1)) if match else 0

        candidatos.sort(key=get_version, reverse=True)
        return candidatos[0]

    # --- LÓGICA DO BUSCADOR GLOBAL ---
    def on_search_key_release(self, event):
        query = self.search_var.get().strip().lower()
        if not query:
            self.refresh_tree()
            return

        matching_paths = set()
        for arq in Path(pu.CAMINHO_PROJETO).rglob("*.md"):
            if any(part in pu.IGNORELIST for part in arq.parts):
                continue
            try:
                with open(arq, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                if query in arq.name.lower() or query in content:
                    p = arq.resolve()
                    matching_paths.add(str(p))
                    for parent in p.parents:
                        matching_paths.add(str(parent))
            except Exception:
                pass

        self.populate_tree_filtered(matching_paths)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_tree()

    def populate_tree_filtered(self, allowed_paths):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.path_to_item.clear()

        pasta_projeto = pu.CAMINHO_PROJETO
        root_abs = os.path.abspath(pasta_projeto)

        root_node = self.tree.insert("", "end", text=f"{pu.PASTA_PROJETO} (Filtrado)", open=True, values=[pasta_projeto])
        self.path_to_item[root_abs] = root_node

        self.populate_tree_recursive(root_node, pasta_projeto, allowed_paths)

    def populate_tree_recursive(self, parent_node, path, allowed_paths=None, depth=0, max_depth=15):
        if depth > max_depth:
            return

        try:
            itens_ordenados = pu.obter_itens_ordenados(path)
            for item in itens_ordenados:
                if item in pu.IGNORELIST:
                    continue

                item_path = os.path.join(path, item)
                item_abs = os.path.abspath(item_path)

                if os.path.islink(item_path):
                    continue

                is_dir = os.path.isdir(item_path)

                if allowed_paths is not None and item_abs not in allowed_paths:
                    continue

                if not is_dir and not item.lower().endswith(".md"):
                    continue

                icon = "📁 " if is_dir else "📄 "
                itemclean = item[:-3] if (not is_dir and item.lower().endswith(".md")) else item
                
                node = self.tree.insert(parent_node, "end", text=f"{icon}{itemclean}", open=(allowed_paths is not None), values=[item_path])
                self.path_to_item[item_abs] = node

                if is_dir:
                    self.populate_tree_recursive(node, item_path, allowed_paths, depth=depth + 1, max_depth=max_depth)
        except Exception as e:
            self.log_callback(f"Erro ao acessar pasta {path}: {e}")

    # --- DRAG AND DROP ---
    def on_drag_start(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            values = self.tree.item(iid, "values")
            text = self.tree.item(iid, "text")
            if values:
                self._drag_item = iid
                self._drag_path = values[0]
                self._drag_text = text
                self._drag_started = False

    def _create_drag_ghost(self, x, y, text):
        self._destroy_drag_ghost()
        try:
            ghost = tk.Toplevel(self)
            ghost.overrideredirect(True)
            ghost.attributes("-topmost", True)
            ghost.attributes("-alpha", 0.75)
            ghost.configure(bg="#0f766e")

            lbl = tk.Label(
                ghost, text=f"{text}", bg="#0f766e", fg="#ffffff", 
                font=("Segoe UI", 9, "bold"), padx=8, pady=4, bd=1, relief="solid"
            )
            lbl.pack()
            ghost.geometry(f"+{x + 12}+{y + 12}")
            self._drag_ghost = ghost
        except Exception:
            self._drag_ghost = None

    def on_drag_motion(self, event):
        if not getattr(self, "_drag_item", None):
            return

        if not getattr(self, "_drag_started", False):
            self._drag_started = True
            self._create_drag_ghost(event.x_root, event.y_root, getattr(self, "_drag_text", ""))

        if hasattr(self, "_drag_ghost") and self._drag_ghost:
            self._drag_ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        target_iid = self.tree.identify_row(event.y)
        if target_iid and target_iid != self._drag_item:
            self.tree.selection_set(target_iid)
            self.tree.focus(target_iid)

    def _destroy_drag_ghost(self):
        if hasattr(self, "_drag_ghost") and self._drag_ghost:
            try:
                self._drag_ghost.destroy()
            except Exception:
                pass
            self._drag_ghost = None

    def on_drag_release(self, event):
        self._destroy_drag_ghost()

        if not getattr(self, "_drag_item", None) or not getattr(self, "_drag_path", None):
            return

        target_iid = self.tree.identify_row(event.y)
        if not target_iid or target_iid == self._drag_item:
            self._drag_item = None
            self._drag_path = None
            return

        src_path = os.path.abspath(self._drag_path)
        target_path = os.path.abspath(self.tree.item(target_iid, "values")[0])

        src_parent_iid = self.tree.parent(self._drag_item)
        target_parent_iid = self.tree.parent(target_iid)

        if src_parent_iid == target_parent_iid:
            target_index = self.tree.index(target_iid)
            self.tree.move(self._drag_item, src_parent_iid, target_index)

            parent_dir = os.path.dirname(src_path)
            novos_filhos = []
            for child_iid in self.tree.get_children(src_parent_iid):
                child_path = self.tree.item(child_iid, "values")[0]
                novos_filhos.append(os.path.basename(child_path))

            pu.salvar_ordem_pasta(parent_dir, novos_filhos)
            self.toast("Ordem salva em logs!")

            self._drag_item = None
            self._drag_path = None
            return

        dest_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        if os.path.isdir(src_path) and dest_dir.startswith(src_path):
            self.toast("Não é possível mover uma pasta para dentro dela mesma.")
            self._drag_item = None
            self._drag_path = None
            return

        dest_path = os.path.join(dest_dir, os.path.basename(src_path))
        if os.path.abspath(src_path) != os.path.abspath(dest_path):
            try:
                shutil.move(src_path, dest_path)
                msg = f"Movido '{os.path.basename(src_path)}' para '{os.path.basename(dest_dir)}'"
                self.log_callback(msg)
                self.toast(msg)
                self.refresh_tree()
                self.select_path_in_tree(dest_path)
            except Exception as e:
                messagebox.showerror("Erro ao mover", f"Falha ao mover item: {e}")

        self._drag_item = None
        self._drag_path = None

    # --- AUTO-SAVE E EDIÇÃO ---
    def on_key_release(self, event):
        self.update_stats()
        self.apply_syntax_highlighting()
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

    def on_select(self, event=None):
        """Seleciona e carrega o arquivo no editor de forma blindada."""
        try:
            selected_item = self.tree.selection()
            if not selected_item:
                return

            item_values = self.tree.item(selected_item[0], "values")
            if not item_values:
                return

            novo_caminho = str(item_values[0])
            if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(novo_caminho):
                return

            arquivo_anterior = self.current_file
            if self.autosave_timer:
                self.after_cancel(self.autosave_timer)
                self.autosave_timer = None

            # Salva o arquivo anterior se existir
            try:
                self.save_current_file()
            except Exception as e:
                self.log_callback(f"Erro ao salvar arquivo anterior: {e}")

            if arquivo_anterior and os.path.isfile(arquivo_anterior):
                try:
                    self.process_saved_file(arquivo_anterior)
                except Exception as e:
                    self.log_callback(f"Erro ao processar arquivo salvo: {e}")

            # Se for um ARQUIVO no disco
            if os.path.isfile(novo_caminho):
                self.current_file = novo_caminho

                # Registra no histórico sem travar o leitor caso falhe
                try:
                    self._add_to_history(novo_caminho)
                except Exception as e:
                    self.log_callback(f"Erro ao adicionar ao histórico: {e}")

                # 1. Habilita o editor
                self.editor.config(state=tk.NORMAL)
                self.editor.delete("1.0", tk.END)

                # 2. Leitura do arquivo
                texto = ""
                try:
                    with open(novo_caminho, "r", encoding="utf-8", errors="ignore") as f:
                        texto = f.read()
                except Exception as e:
                    self.log_callback(f"Erro ao ler arquivo {novo_caminho}: {e}")

                # 3. Insere o texto garantidamente
                self.editor.insert("1.0", texto)

                # 4. Ajustes visuais secundários
                try:
                    self.editor.edit_reset()
                except Exception:
                    pass

                try:
                    self.apply_syntax_highlighting()
                except Exception as e:
                    self.log_callback(f"Erro na sintaxe: {e}")

                try:
                    self.update_stats()
                except Exception:
                    pass

            # Se for uma PASTA / DIRETÓRIO
            else:
                self.current_file = None
                self.editor.config(state=tk.NORMAL)
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", f"--- Diretório Selecionado: {os.path.basename(novo_caminho)} ---")
                self.editor.config(state=tk.DISABLED)

        except Exception as e:
            self.log_callback(f"Erro no on_select: {e}")

    def process_saved_file(self, path):
        if self.auto_expander_callback and not self.auto_expander_callback():
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                texto = f.read()
            if any(tag in texto for tag in pu.TAG_ALVO):
                nome_arq = os.path.basename(path)

                if getattr(self, "_processing_auto_expander", False):
                    return
                self._processing_auto_expander = True

                self.log_callback(f"'<--TO DO:' encontrado em {nome_arq}")
                self.toast(f"Tag '<--TO DO:' detectada em '{nome_arq}'! Executando Expander!")
            
                def _worker():
                    try:
                        wb.improvefile(path)
                    finally:
                        self._processing_auto_expander = False
                        self.after(0, self.refresh_tree)

                threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:
            self.log_callback(f"Erro analisando TODO: {e}")

    # --- MENU DE CONTEXTO ---
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

            if os.path.isfile(caminho) and caminho.lower().endswith(".md"):
                self.context_menu.add_command(
                    label="💬 Perguntar sobre este arquivo ao Ao",
                    command=lambda: self.ask_ao_about_file(caminho)
                )
                self.context_menu.add_separator()

            if os.path.isdir(caminho):
                self.context_menu.add_command(label="📄 Novo Arquivo", command=lambda: self.create_new_file(caminho))
                self.context_menu.add_command(label="📁 Nova Pasta", command=lambda: self.create_new_folder(caminho))
                self.context_menu.add_separator()

            self.context_menu.add_command(label="❌ Deletar", command=lambda: self.delete_item(caminho))
            self.context_menu.add_command(label="✏️ Renomear (F2)", command=lambda: self.rename_item(caminho))
            self.context_menu.add_separator()
            
            self.context_menu.add_command(label="📋 Copiar", command=lambda: self.copy_item(caminho))
            self.context_menu.add_command(label="✂️ Recortar", command=lambda: self.cut_item(caminho))
            pode_colar = self.clipboard_item and os.path.exists(self.clipboard_item["path"])
            colar_state = tk.NORMAL if pode_colar else tk.DISABLED
            self.context_menu.add_command(label="📥 Colar", command=lambda: self.paste_item(caminho), state=colar_state)
            self.context_menu.add_command(label="📑 Duplicar", command=lambda: self.duplicate_item(caminho))
            self.context_menu.add_separator()

            self.context_menu.add_command(label="📂 Mostrar no Windows Explorer", command=lambda: self.reveal_in_explorer(caminho))
            if os.path.isfile(caminho) and caminho.lower().endswith(".md"):
                self.context_menu.add_separator()
                self.context_menu.add_command(label="✨ Melhorar com IA (ImproveFile)", command=lambda: self.run_improve_file(caminho))
            
            self.context_menu.post(event.x_root, event.y_root)

    def ask_ao_about_file(self, caminho):
        if self.ask_ao_callback:
            self.save_current_file()
            self.ask_ao_callback(caminho)

    def run_improve_file(self, caminho):
        nome_arq = os.path.basename(caminho)
        motivo = simpledialog.askstring(
            "Melhorar Arquivo com IA",
            f"Qual o objetivo da melhoria para '{nome_arq}'?\n(Deixe em branco para uma melhoria geral de coesão e detalhes):",
            parent=self
        )
        if motivo is None:
            return

        motivo = motivo.strip() or "Melhorar a qualidade, riqueza de detalhes, estilo e coesão do arquivo com o restante do universo."

        if self.current_file and os.path.abspath(self.current_file) == os.path.abspath(caminho):
            self.save_current_file()

        self.toast(f"✨ Executando ImproveFile em '{nome_arq}'...")
        self.log_callback(f"Iniciando ImproveFile manual para: {nome_arq}")

        def _worker():
            try:
                sucesso = wb.improvefile(caminho, reason=motivo)
                if sucesso:
                    self.log_callback(f"✅ ImproveFile concluído para: {nome_arq}")
                    self.toast(f"✅ Nova versão criada para '{nome_arq}'!")
                    self.after(0, self.refresh_tree)
                else:
                    self.toast(f"⚠️ ImproveFile não gerou alterações para '{nome_arq}'.")
            except Exception as e:
                self.log_callback(f"Erro ao executar ImproveFile: {e}")
                self.toast(f"❌ Erro ao melhorar '{nome_arq}'.")

        threading.Thread(target=_worker, daemon=True).start()
    
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
            if os.name == 'nt':
                if os.path.isfile(caminho):
                    subprocess.run(['explorer', '/select,', caminho])
                else:
                    os.startfile(caminho)
            elif sys.platform == 'darwin':
                subprocess.call(['open', '-R' if os.path.isfile(caminho) else '', caminho])
            else:
                pasta = os.path.dirname(caminho) if os.path.isfile(caminho) else caminho
                subprocess.call(['xdg-open', pasta])
            self.toast(f"Abrindo no explorador de arquivos...")
        except Exception as e:
            self.log_callback(f"Erro ao abrir explorador nativo: {e}")

    def create_new_file(self, parent_dir):
        opcoes_templates = ["Nenhum (Padrão)"]
        locais_templates = [
            pu.PASTA_TEMPLATES,
            Path(pu.CAMINHO_PROJETO) / "Templates"
        ]
        
        modelos_encontrados = set()
        for pasta in locais_templates:
            if pasta.exists() and pasta.is_dir():
                for arq in pasta.glob("*.md"):
                    modelos_encontrados.add(arq.stem.lower())
        
        opcoes_templates.extend(sorted(list(modelos_encontrados)))

        dialog = NewFileDialog(self, opcoes_templates)
        if not dialog.result_filename:
            return

        nome = dialog.result_filename
        template_escolhido = dialog.result_template

        if not nome.lower().endswith(".md"):
            nome += ".md"

        caminho_arquivo = os.path.join(parent_dir, nome)
        if os.path.exists(caminho_arquivo):
            messagebox.showerror("Erro", "Um arquivo com esse nome já existe.")
            return

        try:
            titulo = nome.replace('.md', '').replace('_', ' ').title()
            conteudo_template = wb.obter_conteudo_template(template_escolhido)

            if conteudo_template:
                conteudo_final = f"# {titulo}\nstatus: rascunho\n---\n<-- TODO: Preencha as informações de {titulo} usando o template.\n{conteudo_template}"
            else:
                conteudo_final = f"# {titulo}\n\n<-- TODO: Crie informações para {titulo}."

            with open(caminho_arquivo, "w", encoding="utf-8") as f:
                f.write(conteudo_final)

            msg_toast = f"📄 Arquivo '{nome}' criado com sucesso!"
            if template_escolhido != "Nenhum (Padrão)":
                msg_toast = f"📑 Arquivo '{nome}' criado usando template '{template_escolhido}'!"

            self.toast(msg_toast)
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

        root_node = self.tree.insert("", "end", text=f"{nome_pasta}", open=True, values=[pasta_projeto])
        self.path_to_item[os.path.abspath(pasta_projeto)] = root_node

        self.populate_tree(root_node, pasta_projeto)
        self.restore_open_folders(open_folders)
        self.restore_current_file(current_file)
        self.log_callback("Árvore do diretório sincronizada.")

    def populate_tree(self, parent_node, path, depth=0, max_depth=15):
        if depth > max_depth:
            return

        try:
            itens_ordenados = pu.obter_itens_ordenados(path)
            for item in itens_ordenados:
                if item in pu.IGNORELIST:
                    continue

                item_path = os.path.join(path, item)

                if os.path.islink(item_path):
                    continue

                is_dir = os.path.isdir(item_path)

                if not is_dir and not item.lower().endswith(".md"):
                    continue

                icon = "📁 " if is_dir else "📄 "
                itemclean = item[:-3] if (not is_dir and item.lower().endswith(".md")) else item
                
                node = self.tree.insert(parent_node, "end", text=f"{icon}{itemclean}", open=False, values=[item_path])
                self.path_to_item[os.path.abspath(item_path)] = node

                if is_dir:
                    self.populate_tree(node, item_path, depth=depth + 1, max_depth=max_depth)
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
        self.editor.tag_configure("md_h1", font=("Consolas", font_size + 3, "bold"))
        self.editor.tag_configure("md_h2", font=("Consolas", font_size + 2, "bold"))
        self.editor.tag_configure("md_h3", font=("Consolas", font_size + 1, "bold"))
        self.editor.tag_configure("md_bold", font=("Consolas", font_size, "bold"))
        self.editor.tag_configure("md_italic", font=("Consolas", font_size, "italic"))
        self.editor.tag_configure("md_wikilink", font=("Consolas", font_size, "bold", "underline"))
        self.editor.tag_configure("md_todo", font=("Consolas", font_size, "bold"))
        self.editor.tag_configure("md_quote", font=("Consolas", font_size, "italic"))
        
    def show_editor_context_menu(self, event):
        if str(self.editor.cget("state")) == "disabled":
            return
        try:
            self.editor.focus_set()
            if not self.editor.tag_ranges("sel"):
                self.editor.mark_set("insert", f"@{event.x},{event.y}")
        except Exception:
            pass

        self.editor_context_menu.post(event.x_root, event.y_root)

    def insert_todo_tag(self):
        if str(self.editor.cget("state")) != "disabled":
            tag_texto = "<-- To do:"
            self.editor.insert("insert", tag_texto)
            self.editor.focus_set()
            self.on_key_release(None)
            self.toast("Tag To-Do inserida!")
    
    def update_stats(self):
        if self.stats_callback and self.current_file:
            try:
                texto = self.editor.get("1.0", tk.END)
                palavras = len(texto.split())
                caracteres = len(texto.replace("\n", ""))
                linhas = int(self.editor.index("end-1c").split(".")[0])
                tokens = palavras / 4
                self.stats_callback(palavras, caracteres, linhas, tokens)
            except Exception:
                pass