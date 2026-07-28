import json
import tkinter as tk
from tkinter import ttk
import engine.project_utils as pu

# Caminho central para o arquivo de configurações
SETTINGS_FILE = pu.PASTA_LOGS / "settings.json"

# Configurações padrão do sistema
DEFAULT_SETTINGS = {
    "auto_expander": True,
    # Futuras opções podem ser adicionadas aqui facilmente:
    # "temperature": 0.7,
    # "discord_autostart": False,
}

def carregar_configuracoes():
    """Lê o arquivo logs/settings.json e retorna o dicionário de configurações."""
    config = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                config.update(dados)
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
    return config

def salvar_configuracoes(config):
    """Salva o dicionário de configurações no arquivo logs/settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")


class OptionsFrame(ttk.Frame):
    """Componente visual contendo toda a interface da aba de Opções."""
    def __init__(self, parent, log_callback, toast_callback, page_header_callback):
        super().__init__(parent)
        self.log_callback = log_callback
        self.toast_callback = toast_callback
        self.settings = carregar_configuracoes()

        # Renderiza o cabeçalho padronizado da página
        page_header_callback(self, "Opções do Sistema", "Configure comportamentos automáticos e preferências do console.")

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # -------------------------------------------------------------
        # GRUPO 1: Automação do Expander
        # -------------------------------------------------------------
        expander_opt_box = ttk.LabelFrame(body, text=" Automação do Expander ")
        expander_opt_box.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            expander_opt_box, 
            text="Executar o Expander automaticamente ao salvar um arquivo com a tag <-- TODO:"
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        val_inicial = "Habilitado" if self.settings.get("auto_expander", True) else "Desabilitado"
        self.auto_expander_var = tk.StringVar(value=val_inicial)

        combo_expander = ttk.Combobox(
            expander_opt_box, 
            textvariable=self.auto_expander_var, 
            values=["Habilitado", "Desabilitado"], 
            state="readonly",
            width=15
        )
        combo_expander.pack(anchor=tk.W, padx=10, pady=(0, 10))
        combo_expander.bind("<<ComboboxSelected>>", self._on_auto_expander_change)

    def is_auto_expander_enabled(self):
        """Retorna True se a opção de Expander Automático estiver Habilitada."""
        return self.auto_expander_var.get() == "Habilitado"

    def _on_auto_expander_change(self, event=None):
        """Disparado quando o usuário altera a seleção no dropdown."""
        habilitado = self.is_auto_expander_enabled()
        self.settings["auto_expander"] = habilitado
        salvar_configuracoes(self.settings)

        status_str = "habilitado" if habilitado else "deshabilitado"
        if self.log_callback:
            self.log_callback(f"Expander Automático ao salvar: {status_str.upper()}")
        if self.toast_callback:
            self.toast_callback(f"⚙️ Expander Automático {status_str}!")