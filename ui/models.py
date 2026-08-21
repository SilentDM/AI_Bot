import sys, os, threading
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QGroupBox, QScrollArea, QFrame, QProgressBar,
    QRadioButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QObject

import engine.project_utils as pu
import core.ai_gemini as ag
import ui.settings as st


class FindModelWorker(QObject):
    finished = Signal(str)
    log = Signal(str)

    def run(self):
        try:
            self.log.emit("Iniciando benchmark nos modelos Gemini...")
            ag.findmodel()
            self.finished.emit("Benchmark Concluído")
        except Exception as e:
            self.log.emit(f"Erro no teste de modelos: {e}")
            self.finished.emit("Falhou (Erro)")


class ModelsPerformanceWidget(QWidget):
    signal_log = Signal(str)
    signal_toast = Signal(str)

    def __init__(self, parent, log_cb, toast_cb):
        super().__init__(parent)
        self.log_callback = log_cb
        self.toast_callback = toast_cb

        if self.log_callback: self.signal_log.connect(self.log_callback)
        if self.toast_callback: self.signal_toast.connect(self.toast_callback)

        self.running_threads = set()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # CABEÇALHO
        header = QHBoxLayout()
        title_vbox = QVBoxLayout()

        lbl_title = QLabel(f"<b>⚡ {pu.tr('nav.performance', 'Performance dos Modelos Gemini')}</b>")
        lbl_title.setStyleSheet("font-size: 14pt; color: #10b981;")
        lbl_sub = QLabel("Análise em tempo real de latência, confiabilidade e ordem da fila de Fallback.")
        lbl_sub.setStyleSheet("color: #888888; font-size: 9pt;")

        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        header.addLayout(title_vbox)
        header.addStretch()

        btn_test = QPushButton("⚡ Testar Modelos Agora")
        btn_test.setStyleSheet("background-color: #0f766e; color: white; font-weight: bold; padding: 8px 16px;")
        btn_test.clicked.connect(self.run_findmodel_worker)
        header.addWidget(btn_test)

        layout.addLayout(header)

        # 🟢 CONTROLE DE MODO DE SELEÇÃO (AUTOMÁTICO VS MANUAL)
        box_mode = QGroupBox(" Modo de Seleção e Fila de Fallback ")
        l_mode = QHBoxLayout(box_mode)

        self.rb_auto = QRadioButton("🤖 Usar o melhor modelo (Automático por Telemetria)")
        self.rb_manual = QRadioButton("🎯 Usar ordem personalizada (Manual)")

        config = st.carregar_configuracoes()
        mode_atual = config.get("model_selection_mode", "auto")
        if mode_atual == "manual":
            self.rb_manual.setChecked(True)
        else:
            self.rb_auto.setChecked(True)

        self.rb_auto.toggled.connect(self.on_mode_changed)
        self.rb_manual.toggled.connect(self.on_mode_changed)

        l_mode.addWidget(self.rb_auto)
        l_mode.addWidget(self.rb_manual)
        l_mode.addStretch()

        layout.addWidget(box_mode)

        # ÁREA DE ROLAGEM DOS CARDS
        self.scroll_models = QScrollArea()
        self.scroll_models.setWidgetResizable(True)
        self.scroll_models.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.models_container = QWidget()
        self.models_grid = QGridLayout(self.models_container)
        self.models_grid.setSpacing(12)
        self.scroll_models.setWidget(self.models_container)

        layout.addWidget(self.scroll_models)

    def on_mode_changed(self):
        novo_modo = "manual" if self.rb_manual.isChecked() else "auto"
        config = st.carregar_configuracoes()
        config["model_selection_mode"] = novo_modo
        st.salvar_configuracoes(config)

        msg = "🎯 Modo Manual Ativado! Ajuste a ordem nos cards." if novo_modo == "manual" else "🤖 Modo Automático Ativado! Ranqueado por telemetria."
        self.signal_toast.emit(msg)
        self.refresh_models_cards()

    def run_findmodel_worker(self):
        self.signal_toast.emit("⚡ Iniciando benchmark dos modelos Gemini...")
        
        thread = QThread(self)
        worker = FindModelWorker()
        worker.moveToThread(thread)

        ref = (thread, worker)
        self.running_threads.add(ref)

        thread.started.connect(worker.run)
        worker.log.connect(self.signal_log.emit)
        worker.finished.connect(lambda status: self.refresh_models_cards())
        worker.finished.connect(lambda status: self.signal_toast.emit("✅ Teste de modelos concluído!"))
        worker.finished.connect(thread.quit)

        def _cleanup():
            self.running_threads.discard(ref)
            worker.deleteLater()
            thread.deleteLater()

        thread.finished.connect(_cleanup)
        thread.start()

    def refresh_models_cards(self):
        for i in reversed(range(self.models_grid.count())):
            item = self.models_grid.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        dados = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])
        if not dados:
            lbl_empty = QLabel("⏳ Nenhum teste de modelos realizado ainda.\nClique no botão '⚡ Testar Modelos Agora' acima para disparar o benchmark.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #888888; font-size: 11pt; padding: 40px;")
            self.models_grid.addWidget(lbl_empty, 0, 0)
            return

        config = st.carregar_configuracoes()
        modo_manual = config.get("model_selection_mode", "auto") == "manual"

        if modo_manual:
            manual_order = config.get("manual_model_order", [])
            if manual_order:
                def get_manual_idx(m):
                    name = m.get("name", "")
                    return manual_order.index(name) if name in manual_order else 999
                dados = sorted(dados, key=get_manual_idx)

        total_models = len(dados)
        for idx, m in enumerate(dados, start=1):
            card_widget = self._criar_card_modelo(m, rank=idx, is_manual=modo_manual, total_items=total_models)
            self.models_grid.addWidget(card_widget, (idx - 1) // 2, (idx - 1) % 2)

    def move_model_order(self, model_name, delta):
        config = st.carregar_configuracoes()
        manual_order = config.get("manual_model_order", [])

        if not manual_order:
            dados = pu.ler_json_seguro(pu.log_path("models.json"), pu.LOCK_MODELS, padrao=[])
            manual_order = [m["name"] for m in dados]

        if model_name not in manual_order:
            manual_order.append(model_name)

        idx = manual_order.index(model_name)
        new_idx = idx + delta

        if 0 <= new_idx < len(manual_order):
            manual_order[idx], manual_order[new_idx] = manual_order[new_idx], manual_order[idx]
            config["manual_model_order"] = manual_order
            st.salvar_configuracoes(config)
            self.refresh_models_cards()

    def _criar_card_modelo(self, m, rank, is_manual, total_items):
        card = QFrame()
        card.setObjectName("ModelCard")

        is_top = (rank == 1)
        border_color = "#10b981" if is_top else "#2d2d2d"

        card.setStyleSheet(f"""
            QFrame#ModelCard {{
                background-color: #18181c;
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame#ModelCard:hover {{
                border-color: #10b981;
                background-color: #1e1e24;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # 1. HEADER (Rank Badge + Nome do Modelo + Controles Manuais)
        header_layout = QHBoxLayout()

        if is_manual:
            rank_str = f"🎯 PRIORIDADE MANUAL #{rank}"
            rank_bg = "#0369a1" if is_top else "#1e293b"
            rank_fg = "#38bdf8" if is_top else "#94a3b8"
        else:
            rank_str = f"🤖 RANK TELEMETRIA #{rank}"
            rank_bg = "#065f46" if is_top else "#1e293b"
            rank_fg = "#34d399" if is_top else "#94a3b8"

        lbl_rank = QLabel(rank_str)
        lbl_rank.setStyleSheet(f"background-color: {rank_bg}; color: {rank_fg}; font-size: 8pt; font-weight: bold; padding: 3px 8px; border-radius: 4px;")
        header_layout.addWidget(lbl_rank)

        header_layout.addStretch()

        # 🟢 CONTROLES DE REORDENAÇÃO MANUAL (⬆️ / ⬇️)
        if is_manual:
            model_name = m.get("name", "")
            btn_up = QPushButton("⬆️")
            btn_up.setToolTip("Subir prioridade na fila")
            btn_up.setFixedWidth(32)
            btn_up.setEnabled(rank > 1)
            btn_up.clicked.connect(lambda: self.move_model_order(model_name, -1))

            btn_down = QPushButton("⬇️")
            btn_down.setToolTip("Descer prioridade na fila")
            btn_down.setFixedWidth(32)
            btn_down.setEnabled(rank < total_items)
            btn_down.clicked.connect(lambda: self.move_model_order(model_name, 1))

            header_layout.addWidget(btn_up)
            header_layout.addWidget(btn_down)

        layout.addLayout(header_layout)

        # 2. NOME DE EXIBIÇÃO E ID TÉCNICO
        display_name = m.get("display_name") or m.get("name", "Modelo Gemini")
        lbl_name = QLabel(display_name)
        lbl_name.setStyleSheet("font-size: 12pt; font-weight: bold; color: #ffffff;")
        layout.addWidget(lbl_name)

        model_id = m.get("name", "")
        lbl_id = QLabel(model_id)
        lbl_id.setStyleSheet("font-size: 8pt; color: #666666; font-family: 'Consolas';")
        layout.addWidget(lbl_id)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2d2d2d; background-color: #2d2d2d; max-height: 1px;")
        layout.addWidget(line)

        # 3. METRICAS DE TELEMETRIA

        resp_time = float(m.get("responsetime", 0.0))
        if resp_time < 1.0: speed_tag = "🚀 Ultra Rápido"; bar_color = "#10b981"
        elif resp_time < 2.5: speed_tag = "⚡ Rápido"; bar_color = "#38bdf8"
        else: speed_tag = "🐢 Moderado"; bar_color = "#f59e0b"

        lbl_speed = QLabel(f"<b>⚡ Latência Média:</b> <span style='color:{bar_color};'>{resp_time:.2f}s ({speed_tag})</span>")
        lbl_speed.setStyleSheet("font-size: 9pt;")
        layout.addWidget(lbl_speed)

        pb_speed = QProgressBar()
        pb_speed.setRange(0, 100)
        speed_pct = max(5, min(100, int((1.0 - min(resp_time, 5.0) / 5.0) * 100)))
        pb_speed.setValue(speed_pct)
        pb_speed.setTextVisible(False); pb_speed.setFixedHeight(6)
        pb_speed.setStyleSheet(f"QProgressBar {{ background-color: #252526; border-radius: 3px; border: none; }} QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 3px; }}")
        layout.addWidget(pb_speed)

        attempts = int(m.get("attempts", 1))
        success = int(m.get("success", 0))
        rate_pct = int((success / max(1, attempts)) * 100)
        rate_color = "#10b981" if rate_pct >= 80 else "#f59e0b" if rate_pct >= 50 else "#ef4444"

        lbl_success = QLabel(f"<b>🎯 Taxa de Sucesso:</b> <span style='color:{rate_color};'>{rate_pct}% ({success}/{attempts} requisições)</span>")
        lbl_success.setStyleSheet("font-size: 9pt;")
        layout.addWidget(lbl_success)

        pb_success = QProgressBar()
        pb_success.setRange(0, 100); pb_success.setValue(rate_pct)
        pb_success.setTextVisible(False); pb_success.setFixedHeight(6)
        pb_success.setStyleSheet(f"QProgressBar {{ background-color: #252526; border-radius: 3px; border: none; }} QProgressBar::chunk {{ background-color: {rate_color}; border-radius: 3px; }}")
        layout.addWidget(pb_success)

        tokens = int(m.get("maxinputtokens", 0))
        tok_str = f"{tokens/1_000_000:.1f}M Tokens" if tokens >= 1_000_000 else f"{tokens/1_000:.0f}K Tokens" if tokens >= 1_000 else f"{tokens} Tokens"
        est_words = int(tokens * 0.75)
        est_pages = int(est_words / 500)

        lbl_context = QLabel(f"<b>📚 Janela de Contexto:</b> {tok_str} <span style='color:#888888;'>(~{est_words:,} palavras | ~{est_pages:,} págs)</span>")
        lbl_context.setStyleSheet("font-size: 9pt;")
        layout.addWidget(lbl_context)

        # 4. SELOS E BADGES
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        supports_search = bool(m.get("supports_tools", False))
        lbl_search_badge = QLabel("🔍 Busca Web" if supports_search else "🔍 Sem Busca")
        lbl_search_badge.setStyleSheet(f"background-color: {'#064e3b' if supports_search else '#1e293b'}; color: {'#34d399' if supports_search else '#64748b'}; font-size: 8pt; font-weight: bold; padding: 2px 6px; border-radius: 3px;")
        badges_layout.addWidget(lbl_search_badge)

        if tokens >= 32768:
            lbl_cache_badge = QLabel("🧠 Context Caching")
            lbl_cache_badge.setStyleSheet("background-color: #3b0764; color: #c084fc; font-size: 8pt; font-weight: bold; padding: 2px 6px; border-radius: 3px;")
            badges_layout.addWidget(lbl_cache_badge)

        badges_layout.addStretch()
        layout.addLayout(badges_layout)

        return card