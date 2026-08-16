import sys, os, threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QStatusBar, QFrame,
    QTextEdit, QLineEdit, QFileDialog, QSystemTrayIcon, QMenu,
    QComboBox, QGroupBox, QGridLayout, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QObject
from PySide6.QtGui import QFont, QIcon, QColor

import engine.project_utils as pu
import core.ai_gemini as ag
import core.ai_utils as au
import core.memory as me
import core.cache_gemini as cg
import ui.explorer as expl
import ui.settings as st
import ui.worldbuilder as wb_ui
import ui.gui_logger as gl


class MainWindow(QMainWindow):
    signal_log = Signal(str)
    signal_toast = Signal(str)
    signal_stats = Signal(int, int, int, int)
    signal_discord_status = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silent Multiverse Nexus")
        self.resize(1300, 750)

        self.user_name = "Silent Dungeon Master"
        self.current_font_size = 11

        self.signal_log.connect(self.log_activity)
        self.signal_toast.connect(self.show_toast)
        self.signal_stats.connect(self.update_editor_stats)
        self.signal_discord_status.connect(self.update_discord_status)

        self.setup_qss_style()
        self.setup_ui()
        self.setup_tray()
        self.setup_status_bar()

    def setup_qss_style(self):
        qss_file = Path(__file__).parent / "styles" / "dark.qss"
        if qss_file.exists():
            with open(qss_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def setup_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # BARRA LATERAL (SIDEBAR)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 20, 10, 20)

        lbl_logo = QLabel(pu.tr("sidebar.title"))
        lbl_logo.setStyleSheet("color: #10b981; font-size: 16px; font-weight: bold;")
        side_layout.addWidget(lbl_logo)

        # SELETOR DE PROJETOS NA BARRA LATERAL
        side_layout.addWidget(QLabel(pu.tr("sidebar.active_project")))
        proj_row = QHBoxLayout()
        self.combo_projetos = QComboBox()
        self.recentes_map = {Path(p).name: p for p in pu.obter_projetos_recentes()}
        self.combo_projetos.addItems(list(self.recentes_map.keys()))
        self.combo_projetos.setCurrentText(pu.PASTA_PROJETO)
        self.combo_projetos.currentTextChanged.connect(self.on_project_combo_changed)
        proj_row.addWidget(self.combo_projetos)

        btn_browse_proj = QPushButton("📁")
        btn_browse_proj.setFixedWidth(30)
        btn_browse_proj.clicked.connect(self.browse_project)
        proj_row.addWidget(btn_browse_proj)

        side_layout.addLayout(proj_row)
        side_layout.addSpacing(15)

        # BOTÕES DE NAVEGAÇÃO
        self.pages_stack = QStackedWidget()
        self.nav_buttons = {}

        nav_items = [
            ("editor", pu.tr("nav.editor", "Editor")),
            ("worldbuilder", pu.tr("nav.worldbuilder", "WorldBuilder")),
            ("chat", pu.tr("nav.chat", "Converse com Ao")),
            ("options", pu.tr("nav.options", "Opções")),
            ("models", pu.tr("nav.performance", "Performance Gemini")),
            ("log", pu.tr("nav.logs", "Log de Atividades")),
            ("manual", pu.tr("nav.guide", "📖 Manual & Guia"))
        ]

        for idx, (key, label) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setObjectName("NavBtn")
            btn.clicked.connect(lambda checked, k=key, i=idx: self.switch_page(k, i))
            side_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        side_layout.addStretch()

        # CONTROLE DE ZOOM DE FONTE
        zoom_box = QHBoxLayout()
        zoom_box.addWidget(QLabel(pu.tr("sidebar.zoom")))
        btn_z_minus = QPushButton("A-"); btn_z_minus.setFixedWidth(35); btn_z_minus.clicked.connect(lambda: self.change_font_size(-1))
        btn_z_plus = QPushButton("A+"); btn_z_plus.setFixedWidth(35); btn_z_plus.clicked.connect(lambda: self.change_font_size(1))
        zoom_box.addWidget(btn_z_minus); zoom_box.addWidget(btn_z_plus)
        side_layout.addLayout(zoom_box)

        self.lbl_discord = QLabel(pu.tr("sidebar.discord_online"))
        self.lbl_discord.setStyleSheet("color: #10b981; font-weight: bold;")
        side_layout.addWidget(self.lbl_discord)

        main_layout.addWidget(sidebar)

        # INSTANCIAÇÃO DAS ABAS DEDICADAS
        self.options_widget = st.OptionsWidget(self, self.log_activity, self.show_toast)
        self.worldbuilder_widget = wb_ui.WorldBuilderWidget(self, self.log_activity, self.show_toast)
        self.explorer_widget = expl.ExplorerWidget(
            self, self.log_activity, self.show_toast,
            self.options_widget.is_auto_expander_enabled,
            self.open_chat_with_file_context,
            lambda w, c, l, t: self.signal_stats.emit(w, c, l, t)
        )

        self.pages_stack.addWidget(self.explorer_widget)            # 0
        self.pages_stack.addWidget(self.worldbuilder_widget)        # 1
        self.pages_stack.addWidget(self.build_chat_page())           # 2
        self.pages_stack.addWidget(self.options_widget)              # 3
        self.pages_stack.addWidget(self.build_models_page())        # 4
        self.pages_stack.addWidget(self.build_log_page())           # 5
        self.pages_stack.addWidget(self.build_manual_page())        # 6

        main_layout.addWidget(self.pages_stack)
        self.switch_page("editor", 0)

    def switch_page(self, key, index):
        if key == "models": self.refresh_models_cards()
        elif key == "chat": self.reload_chat_history()
        self.pages_stack.setCurrentIndex(index)
        for k, btn in self.nav_buttons.items():
            btn.setObjectName("NavBtnActive" if k == key else "NavBtn")
            btn.setStyle(btn.style())

    def update_discord_status(self, text, color):
        self.lbl_discord.setText(f"Discord: {text}")
        self.lbl_discord.setStyleSheet(f"color: {color}; font-weight: bold;")

    def change_font_size(self, delta):
        self.current_font_size = max(8, min(24, self.current_font_size + delta))
        self.explorer_widget.update_editor_font(self.current_font_size)
        if hasattr(self, "chat_display"):
            self.chat_display.setFont(QFont("Segoe UI", self.current_font_size))

    def on_project_combo_changed(self, text):
        path = self.recentes_map.get(text)
        if path: self.switch_to_project(path)

    def browse_project(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a Pasta do Projeto", str(pu.CAMINHO_PROJETO.parent))
        if pasta: self.switch_to_project(pasta)

    def switch_to_project(self, caminho_novo):
        try:
            self.explorer_widget.save_current_file()
            pu.definir_projeto_ativo(caminho_novo)
            self.recentes_map = {Path(p).name: p for p in pu.obter_projetos_recentes()}

            self.combo_projetos.blockSignals(True)
            self.combo_projetos.clear()
            self.combo_projetos.addItems(list(self.recentes_map.keys()))
            self.combo_projetos.setCurrentText(pu.PASTA_PROJETO)
            self.combo_projetos.blockSignals(False)

            self.explorer_widget.refresh_tree()
            self.lbl_status_proj.setText(f"{pu.tr('status.project')} {pu.PASTA_PROJETO}")
            self.show_toast(f"🌐 Mundo alterado para '{pu.PASTA_PROJETO}'!")

            def _rebuild(): cg.force_rebuild_world_context()
            threading.Thread(target=_rebuild, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "Erro de Projeto", f"Falha ao abrir projeto: {e}")

    # --- CHAT LOCAL COM AO ---
    def build_chat_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        input_layout = QHBoxLayout()
        self.txt_chat_input = QLineEdit()
        self.txt_chat_input.returnPressed.connect(self.send_chat_message)
        btn_send = QPushButton("Enviar")
        btn_send.clicked.connect(self.send_chat_message)

        input_layout.addWidget(self.txt_chat_input)
        input_layout.addWidget(btn_send)

        layout.addWidget(self.chat_display)
        layout.addLayout(input_layout)
        return page

    def reload_chat_history(self):
        memorias = me.carregar_memorias(f"desktop_{pu.PASTA_PROJETO}", f"Console_{pu.PASTA_PROJETO}", "999999", self.user_name)
        self.chat_display.clear()
        historico = pu.formatar_historico_chat(memorias)

        if not historico:
            self.chat_display.append("<div style='margin-bottom:10px;'><b style='color:#888888;'>System:</b> <span style='color:#888888; font-style:italic;'>Console local conectado. Nenhuma memória anterior.</span></div>")
            return

        for role, content in historico:
            formatted_html = pu.formatar_markdown_para_chat_html(content)
            if role == "You":
                self.chat_display.append(f"<div style='margin-bottom: 12px;'><b style='color:#60a5fa; font-size:11pt;'>You:</b><br>{formatted_html}</div>")
            elif role == "Ao":
                self.chat_display.append(f"<div style='margin-bottom: 16px;'><b style='color:#34d399; font-size:11pt;'>Ao:</b><br>{formatted_html}</div>")
            else:
                self.chat_display.append(f"<div style='margin-bottom: 10px;'><b style='color:#888888;'>System:</b> <span style='color:#888888; font-style:italic;'>{content}</span></div>")

    def open_chat_with_file_context(self, caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                self.chat_attached_file = {"name": os.path.basename(caminho), "content": f.read().strip()}
            self.switch_page("chat", 2)
            self.txt_chat_input.setText(f"Analise '{os.path.basename(caminho)}': ")
            self.show_toast("Arquivo anexado na conversa!")
        except Exception as e:
            self.show_toast(f"Erro ao anexar arquivo: {e}")

    def send_chat_message(self):
        prompt = self.txt_chat_input.text().strip()
        if not prompt: return
        self.txt_chat_input.clear()

        formatted_user_prompt = pu.formatar_markdown_para_chat_html(prompt)
        self.chat_display.append(f"<div style='margin-bottom: 12px;'><b style='color:#60a5fa; font-size:11pt;'>You:</b><br>{formatted_user_prompt}</div>")

        anexo = getattr(self, "chat_attached_file", None)
        self.chat_attached_file = None

        memorias = me.carregar_memorias(f"desktop_{pu.PASTA_PROJETO}", f"Console_{pu.PASTA_PROJETO}", "999999", self.user_name)
        sys_inst, prompt_final = pu.preparar_prompt_conversa_ao(prompt, self.user_name, memorias, anexo)

        def _worker():
            resp = au.ask_ai(contents=prompt_final, system_instruction=sys_inst, temperature=0.6, use_world_context=True)
            if resp:
                me.salvar_memoria(f"desktop_{pu.PASTA_PROJETO}", f"Console_{pu.PASTA_PROJETO}", "999999", self.user_name, prompt, resp)
                formatted_resp = pu.formatar_markdown_para_chat_html(resp)
                QTimer.singleShot(0, lambda: self.chat_display.append(f"<div style='margin-bottom: 16px;'><b style='color:#34d399; font-size:11pt;'>Ao:</b><br>{formatted_resp}</div>"))

        threading.Thread(target=_worker, daemon=True).start()

    # --- DASHBOARD DE PERFORMANCE DO GEMINI ---
    def build_models_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Performance dos Modelos Gemini</b>"))
        btn_test = QPushButton("⚡ Testar Modelos Agora")
        btn_test.clicked.connect(self.run_findmodel_worker)
        header.addWidget(btn_test)
        layout.addLayout(header)

        self.scroll_models = QScrollArea()
        self.scroll_models.setWidgetResizable(True)
        self.models_container = QWidget()
        self.models_grid = QGridLayout(self.models_container)
        self.scroll_models.setWidget(self.models_container)

        layout.addWidget(self.scroll_models)
        return page

    def run_findmodel_worker(self):
        thread = QThread(self)
        worker = wb_ui.FindModelWorker() if hasattr(wb_ui, "FindModelWorker") else None
        if not worker:
            self.log_activity("Executando findmodel...")
            threading.Thread(target=ag.findmodel, daemon=True).start()
            return

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self.log_activity)
        worker.finished.connect(lambda status: self.refresh_models_cards())
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    def refresh_models_cards(self):
        for i in reversed(range(self.models_grid.count())):
            self.models_grid.itemAt(i).widget().setParent(None)

        dados = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])
        for idx, m in enumerate(dados):
            card = QGroupBox(f" #{idx+1} {m.get('display_name', m.get('name'))} ")
            l = QVBoxLayout(card)
            l.addWidget(QLabel(f"⚡ Tempo Médio: {m.get('responsetime', 0):.2f}s"))
            l.addWidget(QLabel(f"Sucesso: {m.get('success', 0)}/{m.get('attempts', 1)}"))
            l.addWidget(QLabel(f"Max Tokens: {m.get('maxinputtokens', 0):,}"))
            l.addWidget(QLabel(f"Busca Online: {'Sim' if m.get('supports_tools') else 'Não'}"))
            self.models_grid.addWidget(card, idx // 2, idx % 2)

    # --- MANUAL COMPLETO ---
    def build_manual_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setHtml("""
        <h1 style='color:#10b981;'>📖 Manual de Operações & Guia Prático</h1>
        <h3>1. Estrutura e Projetos</h3>
        <p>Use o dropdown na barra lateral para trocar de projeto. Cada projeto possui suas memórias, exportações e arquivos isolados.</p>
        <h3>2. Editor e Wikilinks</h3>
        <p>Use <b>[[Nome Do Arquivo]]</b> para criar hiperlinks entre páginas de lore. Use <b>Ctrl+P</b> para busca rápida.</p>
        <h3>3. Expander e IA</h3>
        <p>Insira a tag <b>&lt;-- TODO: comando</b> em qualquer arquivo para pedir à IA que desenvolva aquele trecho automaticamente.</p>
        """)
        layout.addWidget(txt)
        return page

    def build_log_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        sys.stdout = gl.GuiOutput()
        sys.stdout.text_written.connect(self.log_activity)
        return page

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = pu.BASE_DIR / "icon.ico"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        menu = QMenu()
        menu.addAction("Restaurar", self.show)
        menu.addAction("Sair", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def setup_status_bar(self):
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.lbl_status_proj = QLabel(f"{pu.tr('status.project')} {pu.PASTA_PROJETO}")
        self.lbl_status_stats = QLabel("PALAVRAS: 0 | TOKENS: ~0")
        bar.addWidget(self.lbl_status_proj)
        bar.addPermanentWidget(self.lbl_status_stats)

    def show_toast(self, msg):
        self.statusBar().showMessage(msg, 3500)

    def log_activity(self, msg):
        if hasattr(self, "log_display"):
            self.log_display.append(f"[{pu.currentdate()}] {msg}")

    def update_editor_stats(self, w, c, l, t):
        self.lbl_status_stats.setText(
            f"{pu.tr('status.words')} {w:,} | {pu.tr('status.lines')} {l:,} | {pu.tr('status.tokens')} {t:,}"
        )


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()