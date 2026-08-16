import os, sys, threading, re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit, QMenu,
    QDialog, QComboBox, QMessageBox, QInputDialog, QToolBar, QTabWidget,
    QCompleter, QToolTip, QFrame
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QRegularExpression, QStringListModel
)
from PySide6.QtGui import (
    QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QCursor,
    QTextCursor, QAction, QKeySequence
)

import engine.project_utils as pu
import engine.wbuilder as wb
import core.ai_utils as au


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        h1_fmt = QTextCharFormat(); h1_fmt.setForeground(QColor("#10b981")); h1_fmt.setFontWeight(QFont.Bold); h1_fmt.setFontPointSize(14)
        self.rules.append((QRegularExpression(r"^(#{1})\s+.*$"), h1_fmt))

        h2_fmt = QTextCharFormat(); h2_fmt.setForeground(QColor("#34d399")); h2_fmt.setFontWeight(QFont.Bold); h2_fmt.setFontPointSize(12)
        self.rules.append((QRegularExpression(r"^(#{2})\s+.*$"), h2_fmt))

        h3_fmt = QTextCharFormat(); h3_fmt.setForeground(QColor("#60a5fa")); h3_fmt.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"^(#{3,6})\s+.*$"), h3_fmt))

        quote_fmt = QTextCharFormat(); quote_fmt.setForeground(QColor("#94a3b8")); quote_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"^(>.*)$"), quote_fmt))

        todo_fmt = QTextCharFormat(); todo_fmt.setForeground(QColor("#f97316")); todo_fmt.setBackground(QColor("#2a1205")); todo_fmt.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"(<--\s*(?:TODO|TO DO|To Do|To-Do|todo):?.*)"), todo_fmt))

        wiki_fmt = QTextCharFormat(); wiki_fmt.setForeground(QColor("#38bdf8")); wiki_fmt.setFontWeight(QFont.Bold); wiki_fmt.setFontUnderline(True)
        self.rules.append((QRegularExpression(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]"), wiki_fmt))

        bold_fmt = QTextCharFormat(); bold_fmt.setForeground(QColor("#ffffff")); bold_fmt.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"(\*\*[^\*\n]+\*\*)"), bold_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class QuickOpenDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(pu.tr("explorer.quick_open"))
        self.resize(500, 300)
        self.selected_path = None

        layout = QVBoxLayout(self)
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText(pu.tr("explorer.search_placeholder"))
        self.txt_input.textChanged.connect(self.filter_list)
        layout.addWidget(self.txt_input)

        self.list_widget = QTreeWidget()
        self.list_widget.setHeaderHidden(True)
        self.list_widget.itemDoubleClicked.connect(self.on_item_chosen)
        layout.addWidget(self.list_widget)

        self.all_files = list(Path(pu.CAMINHO_PROJETO).rglob("*.md"))
        self.filter_list("")

    def filter_list(self, query):
        self.list_widget.clear()
        query_norm = query.lower()
        for arq in self.all_files:
            if any(part in pu.IGNORELIST for part in arq.parts): continue
            if query_norm in arq.name.lower():
                item = QTreeWidgetItem(self.list_widget, [f"📄 {arq.stem}"])
                item.setData(0, Qt.UserRole, str(arq))

    def on_item_chosen(self, item):
        self.selected_path = item.data(0, Qt.UserRole)
        self.accept()


class MarkdownEditorTab(QWidget):
    text_changed_signal = Signal()

    def __init__(self, file_path, parent_explorer):
        super().__init__()
        self.file_path = file_path
        self.explorer = parent_explorer

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QToolBar()
        layout.addWidget(toolbar)

        btn_bold = QAction("B", self); btn_bold.triggered.connect(lambda: self.insert_formatting("**", "**"))
        toolbar.addAction(btn_bold)

        btn_italic = QAction("I", self); btn_italic.triggered.connect(lambda: self.insert_formatting("*", "*"))
        toolbar.addAction(btn_italic)

        toolbar.addSeparator()

        btn_h1 = QAction("H1", self); btn_h1.triggered.connect(lambda: self.insert_prefix("# "))
        toolbar.addAction(btn_h1)

        btn_h2 = QAction("H2", self); btn_h2.triggered.connect(lambda: self.insert_prefix("## "))
        toolbar.addAction(btn_h2)

        btn_h3 = QAction("H3", self); btn_h3.triggered.connect(lambda: self.insert_prefix("### "))
        toolbar.addAction(btn_h3)

        toolbar.addSeparator()

        btn_todo = QAction("🏷️ TODO", self); btn_todo.triggered.connect(lambda: self.insert_prefix("<-- TODO: "))
        toolbar.addAction(btn_todo)

        btn_wiki = QAction("🔗 Wikilink", self); btn_wiki.triggered.connect(lambda: self.insert_formatting("[[", "]]"))
        toolbar.addAction(btn_wiki)

        toolbar.addSeparator()

        btn_toggle_outline = QAction("📋 Sumário", self)
        btn_toggle_outline.triggered.connect(self.toggle_outline)
        toolbar.addAction(btn_toggle_outline)

        self.splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.splitter)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.editor.setMouseTracking(True)
        self.highlighter = MarkdownHighlighter(self.editor.document())
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_editor_menu)
        self.editor.mouseMoveEvent = self.on_mouse_move

        self.splitter.addWidget(self.editor)

        self.outline_panel = QWidget()
        outline_layout = QVBoxLayout(self.outline_panel)
        outline_layout.setContentsMargins(2, 2, 2, 2)

        lbl_outline = QLabel(f"<b>{pu.tr('explorer.outline_title')}</b>")
        lbl_outline.setStyleSheet("color: #10b981; padding: 4px;")
        outline_layout.addWidget(lbl_outline)

        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.itemClicked.connect(self.jump_to_heading)
        outline_layout.addWidget(self.outline_tree)

        self.splitter.addWidget(self.outline_panel)
        self.outline_panel.hide()

        self.completer = QCompleter(self)
        self.completer.setWidget(self.editor)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated.connect(self.insert_completion)

        self.load_file()

    def update_completer_words(self):
        arquivos = [f.stem for f in Path(pu.CAMINHO_PROJETO).rglob("*.md")]
        model = QStringListModel(arquivos, self.completer)
        self.completer.setModel(model)

    def load_file(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                self.editor.setPlainText(f.read())
            self.update_outline()
            self.update_completer_words()
        except Exception as e:
            self.editor.setPlainText(f"Erro ao carregar arquivo: {e}")

    def on_text_changed(self):
        self.text_changed_signal.emit()
        self.update_outline()

        cursor = self.editor.textCursor()
        texto_bloco = cursor.block().text()[:cursor.positionInBlock()]
        if texto_bloco.endswith("[["):
            self.completer.setCompletionPrefix("")
            popup = self.completer.popup()
            cr = self.editor.cursorRect()
            cr.setWidth(self.completer.popup().sizeHintForColumn(0) + 20)
            self.completer.complete(cr)

    def insert_completion(self, completion):
        tc = self.editor.textCursor()
        tc.insertText(f"{completion}]]")
        self.editor.setTextCursor(tc)

    def insert_formatting(self, prefix, suffix):
        cursor = self.editor.textCursor()
        len_p = len(prefix); len_s = len(suffix)

        if cursor.hasSelection():
            text = cursor.selectedText()
            if text.startswith(prefix) and text.endswith(suffix) and len(text) >= len_p + len_s:
                new_text = text[len_p:-len_s]
                cursor.insertText(new_text)
                return

            doc_text = self.editor.toPlainText()
            sel_start = cursor.selectionStart(); sel_end = cursor.selectionEnd()
            before = doc_text[max(0, sel_start - len_p):sel_start]
            after = doc_text[sel_end:min(len(doc_text), sel_end + len_s)]

            if before == prefix and after == suffix:
                cursor.setPosition(sel_start - len_p)
                cursor.setPosition(sel_end + len_s, QTextCursor.KeepAnchor)
                cursor.insertText(text)
                return

            cursor.insertText(f"{prefix}{text}{suffix}")
        else:
            doc_text = self.editor.toPlainText()
            pos = cursor.position()
            before = doc_text[max(0, pos - len_p):pos]
            after = doc_text[pos:min(len(doc_text), pos + len_s)]

            if before == prefix and after == suffix:
                cursor.setPosition(pos - len_p)
                cursor.setPosition(pos + len_s, QTextCursor.KeepAnchor)
                cursor.insertText("")
            else:
                cursor.insertText(f"{prefix}{suffix}")
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len_s)
                self.editor.setTextCursor(cursor)

    def insert_prefix(self, prefix):
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText(prefix)

    def toggle_outline(self):
        if self.outline_panel.isVisible(): self.outline_panel.hide()
        else: self.outline_panel.show(); self.update_outline(); self.splitter.setSizes([600, 250])

    def update_outline(self):
        self.outline_tree.clear()
        texto = self.editor.toPlainText()
        for i, linha in enumerate(texto.splitlines()):
            match = re.match(r'^(#{1,3})\s+(.*)$', linha)
            if match:
                nivel = len(match.group(1))
                indent = "  " * (nivel - 1)
                item = QTreeWidgetItem(self.outline_tree, [f"{indent}📌 {match.group(2)}"])
                item.setData(0, Qt.UserRole, i)

    def jump_to_heading(self, item, col):
        linha_num = item.data(0, Qt.UserRole)
        cursor = QTextCursor(self.editor.document().findBlockByLineNumber(linha_num))
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def on_mouse_move(self, event):
        cursor = self.editor.cursorForPosition(event.pos())
        pos = cursor.position()
        texto = self.editor.toPlainText()
        found_target = None

        for match in re.finditer(r'\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]', texto):
            if match.start() <= pos <= match.end():
                found_target = match.group(1).strip()
                break

        if found_target:
            path = pu.encontrar_arquivo_por_wikilink(found_target)
            if path and path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        linhas = [line.strip() for line in f.readlines() if line.strip()][:5]
                    preview = "<br>".join(linhas)
                    QToolTip.showText(self.editor.mapToGlobal(event.pos()), f"<b>{path.name}</b><br>{preview}")
                    return
                except Exception: pass

        QToolTip.hideText()
        QTextEdit.mouseMoveEvent(self.editor, event)

    def show_editor_menu(self, pos):
        menu = self.editor.createStandardContextMenu()
        cursor = self.editor.textCursor()

        if cursor.hasSelection():
            texto_sel = cursor.selectedText()
            menu.addSeparator()
            ai_menu = menu.addMenu(pu.tr("explorer.ai_selection_menu"))

            act_expand = ai_menu.addAction(pu.tr("explorer.ai_expand"))
            act_expand.triggered.connect(lambda: self.run_ai_on_selection("Expanda este trecho: " + texto_sel))

            act_grim = ai_menu.addAction(pu.tr("explorer.ai_grimdark"))
            act_grim.triggered.connect(lambda: self.run_ai_on_selection("Reescreva este trecho no tom Dark Fantasy: " + texto_sel))

            act_rumors = ai_menu.addAction(pu.tr("explorer.ai_rumors"))
            act_rumors.triggered.connect(lambda: self.run_ai_on_selection("Gere 3 rumores sobre este trecho: " + texto_sel))

        menu.exec(QCursor.pos())

    def run_ai_on_selection(self, prompt):
        def _worker():
            resp = au.ask_ai(contents=prompt, system_instruction="Você é um assistente de worldbuilding.", use_world_context=True)
            if resp: QTimer.singleShot(0, lambda: self.editor.textCursor().insertText(f"\n\n> {resp}\n\n"))
        threading.Thread(target=_worker, daemon=True).start()


class NewFileDialog(QDialog):
    def __init__(self, parent, templates):
        super().__init__(parent)
        self.setWindowTitle(pu.tr("explorer.new_file"))
        self.setFixedSize(380, 200)
        self.result_filename = None
        self.result_template = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Nome do Arquivo:"))
        self.txt_nome = QLineEdit(self)
        layout.addWidget(self.txt_nome)

        layout.addWidget(QLabel("Modelo / Template:"))
        self.combo_template = QComboBox(self)
        self.combo_template.addItems(templates)
        layout.addWidget(self.combo_template)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Criar Arquivo"); btn_ok.clicked.connect(self.on_confirm)
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def on_confirm(self):
        nome = self.txt_nome.text().strip()
        if not nome: QMessageBox.warning(self, "Aviso", "Digite o nome do arquivo."); return
        self.result_filename = nome
        self.result_template = self.combo_template.currentText()
        self.accept()


class ExplorerWidget(QWidget):
    signal_log = Signal(str)
    signal_toast = Signal(str)
    signal_stats = Signal(int, int, int, int)

    def __init__(self, parent, log_cb, toast_cb, auto_expander_cb, ask_ao_cb, stats_cb):
        super().__init__(parent)
        self.log_callback = log_cb
        self.toast_callback = toast_cb
        self.auto_expander_callback = auto_expander_cb
        self.ask_ao_callback = ask_ao_cb
        self.stats_callback = stats_cb

        self.signal_log.connect(self.log_callback)
        if self.toast_callback: self.signal_toast.connect(self.toast_callback)
        if self.stats_callback: self.signal_stats.connect(self.stats_callback)

        self.clipboard_item = None
        self.open_tabs_map = {}

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.save_current_tab)

        self.setup_ui()
        self.setup_shortcuts()

    def setup_shortcuts(self):
        shortcut_quick_open = QAction(self)
        shortcut_quick_open.setShortcut(QKeySequence("Ctrl+P"))
        shortcut_quick_open.triggered.connect(self.open_quick_open_dialog)
        self.addAction(shortcut_quick_open)

    def open_quick_open_dialog(self):
        dlg = QuickOpenDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.open_file_in_tab(dlg.selected_path)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(self.splitter)

        tree_frame = QWidget()
        tree_layout = QVBoxLayout(tree_frame)
        tree_layout.setContentsMargins(5, 5, 5, 5)

        search_layout = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(pu.tr("explorer.search_placeholder"))
        self.txt_search.textChanged.connect(self.on_search_text_changed)
        btn_clear = QPushButton("✕"); btn_clear.setFixedWidth(30)
        btn_clear.clicked.connect(lambda: self.txt_search.clear())
        search_layout.addWidget(self.txt_search); search_layout.addWidget(btn_clear)
        tree_layout.addLayout(search_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemClicked.connect(self.on_tree_single_click)

        tree_layout.addWidget(self.tree)

        btn_refresh = QPushButton(pu.tr("explorer.refresh_dir"))
        btn_refresh.clicked.connect(self.refresh_tree)
        tree_layout.addWidget(btn_refresh)

        self.splitter.addWidget(tree_frame)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.splitter.addWidget(self.tab_widget)
        self.splitter.setSizes([300, 700])

        self.refresh_tree()

    def toast(self, msg): self.signal_toast.emit(msg)
    def log(self, msg): self.signal_log.emit(msg)

    def on_tree_single_click(self, item, col):
        caminho = item.data(0, Qt.UserRole)
        if not caminho: return
        if os.path.isfile(caminho): self.open_file_in_tab(caminho)
        elif os.path.isdir(caminho): item.setExpanded(not item.isExpanded())

    def open_file_in_tab(self, file_path):
        file_path_abs = os.path.abspath(file_path)
        if file_path_abs in self.open_tabs_map:
            tab_index = self.open_tabs_map[file_path_abs]
            self.tab_widget.setCurrentIndex(tab_index)
            return

        tab = MarkdownEditorTab(file_path_abs, self)
        tab.text_changed_signal.connect(self.on_tab_text_changed)

        tab_name = os.path.basename(file_path_abs).replace('.md', '')
        index = self.tab_widget.addTab(tab, f"📄 {tab_name}")
        self.open_tabs_map[file_path_abs] = index
        self.tab_widget.setCurrentIndex(index)

    def close_tab(self, index):
        tab_widget = self.tab_widget.widget(index)
        if isinstance(tab_widget, MarkdownEditorTab):
            path = tab_widget.file_path
            if path in self.open_tabs_map: del self.open_tabs_map[path]
        self.tab_widget.removeTab(index)

    def on_tab_changed(self, index):
        tab = self.tab_widget.widget(index)
        if isinstance(tab, MarkdownEditorTab):
            palavras, chars, linhas, tokens = pu.calcular_estatisticas_texto(tab.editor.toPlainText())
            self.signal_stats.emit(palavras, chars, linhas, tokens)

    def on_tab_text_changed(self):
        self.autosave_timer.start(5000)
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, MarkdownEditorTab):
            palavras, chars, linhas, tokens = pu.calcular_estatisticas_texto(current_tab.editor.toPlainText())
            self.signal_stats.emit(palavras, chars, linhas, tokens)

    def save_current_tab(self):
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, MarkdownEditorTab):
            try:
                conteudo = current_tab.editor.toPlainText()
                with open(current_tab.file_path, "w", encoding="utf-8") as f:
                    f.write(conteudo)
                self.log(f"Auto-salvo: {os.path.basename(current_tab.file_path)}")
                self.process_saved_file(current_tab.file_path)
            except Exception as e: self.log(f"Falha ao salvar: {e}")

    def save_current_file(self): self.save_current_tab()

    def process_saved_file(self, path):
        if self.auto_expander_callback and not self.auto_expander_callback(): return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f: texto = f.read()
            if any(tag in texto for tag in pu.TAG_ALVO):
                nome_arq = os.path.basename(path)
                if getattr(self, "_processing_auto_expander", False): return
                self._processing_auto_expander = True
                self.toast(f"Tag '<--TO DO:' detectada em '{nome_arq}'! Executando Expander!")
                def _worker():
                    try: wb.improvefile(path)
                    finally:
                        self._processing_auto_expander = False
                        QTimer.singleShot(0, self.refresh_tree)
                threading.Thread(target=_worker, daemon=True).start()
        except Exception as e: self.log(f"Erro analisando TODO: {e}")

    def on_search_text_changed(self, text):
        if not text.strip(): self.refresh_tree(); return
        paths = pu.filtrar_caminhos_busca(text)
        self.populate_tree_filtered(paths)

    def populate_tree_filtered(self, allowed_paths):
        self.tree.clear()
        pasta_projeto = pu.CAMINHO_PROJETO
        root_item = QTreeWidgetItem(self.tree, [f"{pu.PASTA_PROJETO} (Filtrado)"])
        root_item.setData(0, Qt.UserRole, str(pasta_projeto))
        root_item.setExpanded(True)
        self.populate_tree_recursive(root_item, pasta_projeto, allowed_paths)

    def refresh_tree(self):
        self.tree.clear()
        pasta_projeto = pu.CAMINHO_PROJETO
        os.makedirs(pasta_projeto, exist_ok=True)

        root_item = QTreeWidgetItem(self.tree, [f"{pu.PASTA_PROJETO}"])
        root_item.setData(0, Qt.UserRole, str(pasta_projeto))
        root_item.setExpanded(True)
        self.populate_tree_recursive(root_item, pasta_projeto)

    def populate_tree_recursive(self, parent_item, path, allowed_paths=None, depth=0):
        if depth > 15: return
        itens_ordenados = pu.obter_itens_ordenados(path)
        for item in itens_ordenados:
            if item in pu.IGNORELIST: continue
            item_path = os.path.join(path, item)
            item_abs = os.path.abspath(item_path)

            if allowed_paths is not None and item_abs not in allowed_paths: continue

            is_dir = os.path.isdir(item_path)
            if not is_dir and not item.lower().endswith(".md"): continue

            icon = "📁 " if is_dir else "📄 "
            itemclean = item[:-3] if (not is_dir and item.lower().endswith(".md")) else item

            child_item = QTreeWidgetItem(parent_item, [f"{icon}{itemclean}"])
            child_item.setData(0, Qt.UserRole, item_path)

            if is_dir: self.populate_tree_recursive(child_item, item_path, allowed_paths, depth + 1)

    def select_path_in_tree(self, caminho_alvo): self.open_file_in_tab(caminho_alvo)

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        caminho = item.data(0, Qt.UserRole)
        menu = QMenu(self)

        if os.path.isfile(caminho) and caminho.endswith(".md"):
            menu.addAction(pu.tr("explorer.ask_ao"), lambda: self.ask_ao_callback(caminho) if self.ask_ao_callback else None)
            menu.addAction(pu.tr("explorer.improve_ai"), lambda: self.run_improve_file(caminho))
            menu.addSeparator()

        if os.path.isdir(caminho):
            menu.addAction(pu.tr("explorer.new_file"), lambda: self.create_new_file(caminho))
            menu.addAction(pu.tr("explorer.new_folder"), lambda: self.create_new_folder(caminho))
            menu.addSeparator()

        menu.addAction(pu.tr("explorer.delete"), lambda: self.delete_item(caminho))
        menu.addAction(pu.tr("explorer.rename"), lambda: self.rename_item(caminho))
        menu.addSeparator()
        menu.addAction(pu.tr("explorer.copy"), lambda: self.copy_item(caminho))
        menu.addAction(pu.tr("explorer.cut"), lambda: self.cut_item(caminho))
        menu.addAction(pu.tr("explorer.paste"), lambda: self.paste_item(caminho))
        menu.addAction(pu.tr("explorer.duplicate"), lambda: self.duplicate_item(caminho))
        menu.addSeparator()
        menu.addAction(pu.tr("explorer.show_explorer"), lambda: pu.abrir_no_explorador_nativo(caminho))

        menu.exec(QCursor.pos())

    def run_improve_file(self, caminho):
        nome = os.path.basename(caminho)
        motivo, ok = QInputDialog.getText(self, "ImproveFile", f"Objetivo da melhoria para '{nome}':")
        if ok:
            motivo = motivo.strip() or "Melhorar a qualidade, riqueza de detalhes e estilo."
            self.toast(f"Executando ImproveFile em '{nome}'...")
            def _worker():
                if wb.improvefile(caminho, reason=motivo):
                    self.toast(f"Nova versão criada para '{nome}'!")
                    QTimer.singleShot(0, self.refresh_tree)
            threading.Thread(target=_worker, daemon=True).start()

    def copy_item(self, caminho): self.clipboard_item = {"path": caminho, "mode": "copy"}; self.toast("📋 Copiado!")
    def cut_item(self, caminho): self.clipboard_item = {"path": caminho, "mode": "cut"}; self.toast("✂️ Recortado!")

    def paste_item(self, target_path):
        if not self.clipboard_item: return
        suc, msg, novo = pu.colar_item_clipboard(self.clipboard_item["path"], target_path, self.clipboard_item["mode"])
        if suc: self.toast(msg); self.refresh_tree(); self.open_file_in_tab(str(novo))
        else: QMessageBox.warning(self, "Erro", msg)

    def duplicate_item(self, caminho):
        suc, msg, novo = pu.duplicar_item_projeto(caminho)
        if suc: self.toast(msg); self.refresh_tree(); self.open_file_in_tab(str(novo))

    def create_new_file(self, parent_dir):
        templates = ["Nenhum (Padrão)"]
        for p in [pu.PASTA_TEMPLATES, Path(pu.CAMINHO_PROJETO) / "Templates"]:
            if p.exists(): templates.extend([f.stem for f in p.glob("*.md")])

        dlg = NewFileDialog(self, sorted(list(set(templates))))
        if dlg.exec() == QDialog.Accepted and dlg.result_filename:
            suc, msg, novo = pu.criar_novo_arquivo(parent_dir, dlg.result_filename, dlg.result_template, wb.obter_conteudo_template)
            if suc: self.toast("📄 Arquivo criado!"); self.refresh_tree(); self.open_file_in_tab(str(novo))
            else: QMessageBox.warning(self, "Erro", msg)

    def create_new_folder(self, parent_dir):
        nome, ok = QInputDialog.getText(self, "Nova Pasta", "Nome da pasta:")
        if ok and nome:
            suc, msg, nova = pu.criar_nova_pasta(parent_dir, nome)
            if suc: self.toast(msg); self.refresh_tree()
            else: QMessageBox.warning(self, "Erro", msg)

    def rename_item(self, caminho):
        novo, ok = QInputDialog.getText(self, "Renomear", "Novo nome:", QLineEdit.Normal, os.path.basename(caminho))
        if ok and novo:
            suc, msg, novo_p = pu.renomear_item_projeto(caminho, novo)
            if suc: self.toast(msg); self.refresh_tree()
            else: QMessageBox.warning(self, "Erro", msg)

    def delete_item(self, caminho):
        ret = QMessageBox.question(self, "Deletar", f"Excluir '{os.path.basename(caminho)}'?")
        if ret == QMessageBox.Yes:
            suc, msg = pu.deletar_item_projeto(caminho)
            if suc: self.toast(msg); self.refresh_tree()
            else: QMessageBox.warning(self, "Erro", msg)

    def update_editor_font(self, size):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, MarkdownEditorTab): tab.editor.setFont(QFont("Consolas", size))

