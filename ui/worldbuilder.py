import sys, os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QTextEdit, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QObject

import engine.project_utils as pu
import engine.compiler as comp
import engine.expander as ex
import engine.wbuilder as wb
import core.ai_utils as au
import core.cache_gemini as cg
import core.memory as me


# --- WORKERS NATIVOS DO QT (QTHREAD) ---

class ExpanderWorker(QObject):
    finished = Signal(str)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("Iniciando varredura do Expander...")
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
            self.log.emit(f"Iniciando WorldBuilder autônomo. Objetivo: '{self.objective}'")
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
            self.log.emit("Reconstruindo contexto para auditoria de lore...")
            cg.force_rebuild_world_context()
            sys_inst, prompt = pu.obter_prompts_auditoria_lore()

            self.log.emit("Analisando consistência do universo com a IA...")
            relatorio = au.ask_ai(contents=prompt, system_instruction=sys_inst, temperature=0.2, use_world_context=True)
            self.finished.emit("Concluído", relatorio or "Sem erros detectados.")
        except Exception as e:
            self.log.emit(f"Erro na auditoria: {e}")
            self.finished.emit("Falhou", f"Erro: {e}")


class RebuildContextWorker(QObject):
    finished = Signal(str)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("🌐 Reconstruindo contexto do mundo em segundo plano...")
            cg.force_rebuild_world_context()
            self.log.emit("✅ Contexto do mundo recriado com sucesso!")
            self.finished.emit("Contexto Recriado")
        except Exception as e:
            self.log.emit(f"Erro ao recriar contexto: {e}")
            self.finished.emit("Falhou")


class CompileBookWorker(QObject):
    finished = Signal(str, object)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("📄 Compilando Livro do Cenário...")
            path = comp.compilar_livro_cenario()
            if path:
                self.log.emit(f"✅ Livro do Cenário compilado: {path.name}")
                self.finished.emit("Concluído", path)
            else:
                self.log.emit("❌ Falha ao compilar o livro.")
                self.finished.emit("Falhou", None)
        except Exception as e:
            self.log.emit(f"Erro na compilação: {e}")
            self.finished.emit("Erro", None)


class BackupWorker(QObject):
    finished = Signal(str, object, int)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("💾 Criando backup completo (.zip)...")
            z, n = pu.criar_backup_projeto()
            self.log.emit(f"✅ Backup concluído ({n} arquivos): {z.name}")
            self.finished.emit("Concluído", z, n)
        except Exception as e:
            self.log.emit(f"Erro no backup: {e}")
            self.finished.emit("Erro", None, 0)


# --- PAINEL PRINCIPAL DEDICADO DO WORLDBUILDER ---

class WorldBuilderWidget(QWidget):
    signal_log = Signal(str)
    signal_toast = Signal(str)
    signal_wb_log = Signal(str)

    def __init__(self, parent, log_cb, toast_cb):
        super().__init__(parent)
        self.log_callback = log_cb
        self.toast_callback = toast_cb

        if self.log_callback: self.signal_log.connect(self.log_callback)
        if self.toast_callback: self.signal_toast.connect(self.toast_callback)

        self.signal_wb_log.connect(self._safe_append_wb_log)
        self.running_threads = set()
        self.setup_ui()

    @Slot(str)
    def _safe_append_wb_log(self, msg):
        timestamp = pu.currentdate()
        formatted_msg = f"[{timestamp}] {msg}"
        self.txt_wb_log.append(formatted_msg)
        self.signal_log.emit(msg)

    def append_wb_log(self, msg):
        self.signal_wb_log.emit(msg)

    def _start_worker_thread(self, worker, on_finished=None):
        thread = QThread(self)
        worker.moveToThread(thread)

        ref = (thread, worker)
        self.running_threads.add(ref)

        thread.started.connect(worker.run)
        worker.log.connect(self.append_wb_log)

        if on_finished:
            worker.finished.connect(on_finished)

        worker.finished.connect(thread.quit)

        def _cleanup():
            self.running_threads.discard(ref)
            worker.deleteLater()
            thread.deleteLater()

        thread.finished.connect(_cleanup)
        thread.start()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)

        # 1. CONTROLE DE EMERGÊNCIA
        box_stop = QGroupBox(pu.tr("actions.stop_all", " Controle de Emergência "))
        l_stop = QVBoxLayout(box_stop)
        btn_stop = QPushButton(pu.tr("actions.stop_all", "⛔ PARAR QUALQUER EXECUÇÃO ATUAL"))
        btn_stop.setStyleSheet("background-color: #7f1d1d; color: white; font-weight: bold;")
        btn_stop.clicked.connect(self.stop_all)
        l_stop.addWidget(btn_stop)
        layout.addWidget(box_stop)

        # 2. EXPANDER E CONTEXTO
        box_exp = QGroupBox(pu.tr("actions.expander_title", " Expander & Contexto "))
        l_exp = QVBoxLayout(box_exp)
        btn_exp = QPushButton(pu.tr("actions.expander_btn", "▶ Executar Tarefa do Expander"))
        btn_exp.clicked.connect(self.run_expander_worker)
        btn_reb = QPushButton(pu.tr("actions.rebuild_ctx_btn", "🌐 Reconstruir Contexto do Mundo"))
        btn_reb.clicked.connect(self.rebuild_context)
        l_exp.addWidget(btn_exp)
        l_exp.addWidget(btn_reb)
        layout.addWidget(box_exp)

        # 3. WORLDBUILDER AUTÔNOMO
        box_wb = QGroupBox(pu.tr("wb.title", " WorldBuilder "))
        l_wb = QVBoxLayout(box_wb)
        self.txt_wb_obj = QLineEdit(pu.tr("wb.goal_placeholder", "Completar o Projeto"))
        btn_wb = QPushButton(pu.tr("wb.btn_run", "▶ Executar WorldBuilder"))
        btn_wb.clicked.connect(lambda: self.run_worldbuilder_worker(self.txt_wb_obj.text()))
        l_wb.addWidget(QLabel(pu.tr("wb.goal_label", "Objetivo do WorldBuilder:")))
        l_wb.addWidget(self.txt_wb_obj)
        l_wb.addWidget(btn_wb)
        layout.addWidget(box_wb)

        # 4. AUDITORIA DE LORE
        box_aud = QGroupBox(pu.tr("actions.audit_title", " Auditoria de Lore "))
        l_aud = QVBoxLayout(box_aud)
        btn_aud = QPushButton(pu.tr("actions.audit_btn", "▶ Auditar Lore do Mundo (Buscar Incoerências)"))
        btn_aud.clicked.connect(self.run_lore_audit_worker)
        l_aud.addWidget(btn_aud)
        layout.addWidget(box_aud)

        # 5. EXPORTAÇÃO E BACKUP
        box_tools = QGroupBox(pu.tr("actions.mgmt_title", " Exportação & Backup "))
        l_tools = QHBoxLayout(box_tools)
        btn_comp = QPushButton(pu.tr("actions.export_btn", "📄 Compilar Livro (HTML)"))
        btn_comp.clicked.connect(self.export_sourcebook)
        btn_back = QPushButton(pu.tr("actions.backup_btn", "💾 Backup ZIP"))
        btn_back.clicked.connect(self.create_backup)
        btn_del_mem = QPushButton(pu.tr("actions.del_memories_btn", "🗑️ Excluir Memórias"))
        btn_del_mem.clicked.connect(self.delete_memories)
        l_tools.addWidget(btn_comp)
        l_tools.addWidget(btn_back)
        l_tools.addWidget(btn_del_mem)
        layout.addWidget(box_tools)

        # 6. CAIXA DE LOGS DO WORLDBUILDER
        box_wb_log = QGroupBox(pu.tr("wb.log_title", " 📜 Progresso & Logs de Atividades do WorldBuilder "))
        l_wb_log = QVBoxLayout(box_wb_log)

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Acompanhamento em tempo real dos processos:"))
        btn_clear_log = QPushButton(pu.tr("wb.clear_log", "Limpar Log Local"))
        btn_clear_log.setFixedWidth(120)
        btn_clear_log.clicked.connect(self.clear_wb_log)
        log_header.addWidget(btn_clear_log)
        l_wb_log.addLayout(log_header)

        self.txt_wb_log = QTextEdit()
        self.txt_wb_log.setReadOnly(True)
        self.txt_wb_log.setMinimumHeight(180)
        self.txt_wb_log.setPlaceholderText("Aguardando início de tarefas...")
        l_wb_log.addWidget(self.txt_wb_log)

        layout.addWidget(box_wb_log)

    def clear_wb_log(self):
        self.txt_wb_log.clear()

    def stop_all(self):
        pu.request_cancellation()
        self.append_wb_log("🛑 Solicitação de interrupção enviada...")
        self.signal_toast.emit("🛑 Interrompendo tarefas...")

    def rebuild_context(self):
        worker = RebuildContextWorker()
        self._start_worker_thread(worker, lambda s: self.signal_toast.emit("🌐 Contexto atualizado!"))

    def run_expander_worker(self):
        pu.reset_cancellation()
        worker = ExpanderWorker()
        self._start_worker_thread(worker, lambda s: self.signal_toast.emit(f"Expander: {s}"))

    def run_worldbuilder_worker(self, obj):
        pu.reset_cancellation()
        worker = WorldBuilderWorker(obj)
        self._start_worker_thread(worker, lambda s: self.signal_toast.emit(f"WorldBuilder: {s}"))

    def run_lore_audit_worker(self):
        pu.reset_cancellation()
        worker = LoreAuditWorker()

        def _on_finished(status, report):
            self.signal_toast.emit(f"Auditoria: {status}")
            QMessageBox.information(self, "Relatório de Auditoria de Lore", report)

        self._start_worker_thread(worker, _on_finished)

    def export_sourcebook(self):
        worker = CompileBookWorker()

        def _on_finished(status, path):
            if path:
                pu.abrir_no_explorador_nativo(str(path))

        self._start_worker_thread(worker, _on_finished)

    def create_backup(self):
        worker = BackupWorker()

        def _on_finished(status, path, total):
            if path:
                QMessageBox.information(self, "Backup Concluído", f"Backup com {total} arquivos salvo em:\n{path}")

        self._start_worker_thread(worker, _on_finished)

    def delete_memories(self):
        if QMessageBox.question(self, "Excluir Memórias", "Deseja excluir todas as memórias salvas?") == QMessageBox.Yes:
            me.delete_all_memories()
            self.append_wb_log("🗑️ Todas as memórias do projeto foram excluídas.")
            self.signal_toast.emit("🗑️ Memórias apagadas!")