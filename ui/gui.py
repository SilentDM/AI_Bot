import sys, os, threading
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QStatusBar, QFrame,
    QTextEdit, QLineEdit, QSplitter, QMessageBox, QFileDialog, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QObject
from PySide6.QtGui import QIcon, QFont

import engine.project_utils as pu
import engine.compiler as comp
import engine.expander as ex
import engine.wbuilder as wb
import core.ai_utils as au
import core.cache_gemini as cg
import core.memory as me
import ui.explorer as expl
import ui.settings as st
import ui.gui_logger as gl


# --- WORKERS NATIVOS DO QT (QTHREAD) ---

class ExpanderWorker(QObject):
    finished = Signal(str)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("Iniciando tarefa do Expander...")
            ex.processar_arquivos()
            self.finished.emit("Tarefa Concluída")
        except Exception as e:
            self.log.emit(f"Erro no Expander: {e}")
            self.finished.emit("Falhou (Erro)")


class WorldBuilderWorker(QObject):
    finished = Signal(str)
    log = Signal(str)

    def __init__(self, objective):
        super().__init__()
        self.objective = objective

    def run(self):
        try:
            self.log.emit("Iniciando WorldBuilder autônomo...")
            wb.taskplanner(self.objective)
            self.finished.emit("WorldBuilder Concluído")
        except Exception as e:
            self.log.emit(f"Erro no WorldBuilder: {e}")
            self.finished.emit("Falhou (Erro)")


class LoreAuditWorker(QObject):
    finished = Signal(str, str)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("Reconstruindo contexto para auditoria...")
            cg.force_rebuild_world_context()
            sys_inst, prompt = pu.obter_prompts_auditoria_lore()

            relatorio = au.ask_ai(contents=prompt, system_instruction=sys_inst, temperature=0.2, use_world_context=True)
            self.finished.emit("Concluído", relatorio or "Sem erros detectados.")
        except Exception as e:
            self.log.emit(f"Erro na auditoria: {e}")
            self.finished.emit("Falhou", f"Erro: {e}")


class MainWindow(QMainWindow):
    signal_log = Signal(str)
    signal_toast = Signal(str)
    signal_stats = Signal(int, int, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silent Multiverse Nexus")
        self.resize(1300, 700)

        self.user_name = "Silent Dungeon Master"
        self.current_font_size = 11

        self.signal_log.connect(self.log_activity)
        self.signal_toast.connect(self.show_toast)
        self.signal_stats.connect(self.update_editor_stats)

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

        lbl_logo = QLabel("🜂 Silent Console")
        lbl_logo.setStyleSheet("color: #10b981; font-size: 16px; font-weight: bold;")
        side_layout.addWidget(lbl_logo)

        self.pages_stack = QStackedWidget()
        self.nav_buttons = {}

        nav_items = [
            ("editor", "Editor"),
            ("worldbuilder", "WorldBuilders"),
            ("chat", "Converse com Ao"),
            ("options", "Opções"),
            ("log", "Log de Atividades")
        ]

        for idx, (key, label) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setObjectName("NavBtn")
            btn.clicked.connect(lambda checked, k=key, i=idx: self.switch_page(k, i))
            side_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        side_layout.addStretch()

        self.lbl_discord = QLabel("Discord: Online")
        self.lbl_discord.setStyleSheet("color: #10b981; font-weight: bold;")
        side_layout.addWidget(self.lbl_discord)

        main_layout.addWidget(sidebar)

        # PÁGINAS DA APLICAÇÃO
        self.options_widget = st.OptionsWidget(self, self.log_activity, self.show_toast)
        self.explorer_widget = expl.ExplorerWidget(
            self, self.log_activity, self.show_toast,
            self.options_widget.is_auto_expander_enabled,
            self.open_chat_with_file_context,
            lambda w, c, l, t: self.signal_stats.emit(w, c, l, t)
        )

        self.pages_stack.addWidget(self.explorer_widget)          # 0
        self.pages_stack.addWidget(self.build_worldbuilder_page()) # 1
        self.pages_stack.addWidget(self.build_chat_page())         # 2
        self.pages_stack.addWidget(self.options_widget)            # 3
        self.pages_stack.addWidget(self.build_log_page())          # 4

        main_layout.addWidget(self.pages_stack)
        self.switch_page("editor", 0)

    def switch_page(self, key, index):
        self.pages_stack.setCurrentIndex(index)
        for k, btn in self.nav_buttons.items():
            btn.setObjectName("NavBtnActive" if k == key else "NavBtn")
            btn.setStyle(btn.style())

    def build_worldbuilder_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        btn_stop = QPushButton("⛔ PARAR EXECUÇÃO ATUAL")
        btn_stop.setStyleSheet("background-color: #7f1d1d; color: white;")
        btn_stop.clicked.connect(pu.request_cancellation)

        btn_expander = QPushButton("▶ Executar Tarefa do Expander (QThread)")
        btn_expander.clicked.connect(self.run_expander_worker)

        btn_audit = QPushButton("▶ Auditar Lore do Mundo (QThread)")
        btn_audit.clicked.connect(self.run_lore_audit_worker)

        btn_compiler = QPushButton("▶ Gerar e Abrir Livro do Cenário (HTML)")
        btn_compiler.clicked.connect(self.export_sourcebook)

        btn_backup = QPushButton("▶ Criar Backup Completo (.zip)")
        btn_backup.clicked.connect(self.create_backup)

        layout.addWidget(btn_stop)
        layout.addWidget(btn_expander)
        layout.addWidget(btn_audit)
        layout.addWidget(btn_compiler)
        layout.addWidget(btn_backup)
        layout.addStretch()
        return page

    # --- EXECUÇÃO DE WORKERS EM QTHREAD ---
    def run_expander_worker(self):
        pu.reset_cancellation()
        self.thread = QThread()
        self.worker = ExpanderWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_activity)
        self.worker.finished.connect(lambda status: self.show_toast(f"Expander: {status}"))
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def run_lore_audit_worker(self):
        pu.reset_cancellation()
        self.thread = QThread()
        self.worker = LoreAuditWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_activity)
        self.worker.finished.connect(self.on_audit_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_audit_finished(self, status, report):
        self.show_toast(f"Auditoria: {status}")
        QMessageBox.information(self, "Relatório de Auditoria", report)

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
        if icon_path.exists(): self.tray.setIcon(QIcon(str(icon_path)))

        menu = QMenu()
        menu.addAction("Restaurar", self.show)
        menu.addAction("Sair", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def setup_status_bar(self):
        bar = QStatusBar()
        self.setStatusBar(bar)

        self.lbl_status_proj = QLabel(f"Projeto: {pu.PASTA_PROJETO}")
        self.lbl_status_stats = QLabel("PALAVRAS: 0 | TOKENS: ~0")
        bar.addWidget(self.lbl_status_proj)
        bar.addPermanentWidget(self.lbl_status_stats)

    def show_toast(self, msg): self.statusBar().showMessage(msg, 3500)

    def log_activity(self, msg):
        if hasattr(self, "log_display"):
            self.log_display.append(f"[{pu.currentdate()}] {msg}")

    def update_editor_stats(self, w, c, l, t):
        self.lbl_status_stats.setText(f"PALAVRAS: {w:,} | LINHAS: {l:,} | TOKENS: ~{t:,}")

    def open_chat_with_file_context(self, caminho):
        self.switch_page("chat", 2)
        self.txt_chat_input.setText(f"Analise '{os.path.basename(caminho)}': ")

    def send_chat_message(self):
        prompt = self.txt_chat_input.text().strip()
        if not prompt: return
        self.txt_chat_input.clear()
        self.chat_display.append(f"<b>You:</b> {prompt}\n")

        def _worker():
            resp = au.ask_ai(contents=prompt, system_instruction="Você é Ao.", use_world_context=True)
            QTimer.singleShot(0, lambda: self.chat_display.append(f"<b>Ao:</b> {resp}\n"))

        threading.Thread(target=_worker, daemon=True).start()

    def export_sourcebook(self):
        path = comp.compilar_livro_cenario()
        if path: pu.abrir_no_explorador_nativo(str(path))

    def create_backup(self):
        zip_p, total = pu.criar_backup_projeto()
        QMessageBox.information(self, "Backup", f"Backup com {total} arquivos criado em:\n{zip_p}")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()