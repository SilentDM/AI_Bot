import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import engine.project_utils as pu

# Caminho central para o arquivo de configurações
SETTINGS_FILE = pu.PASTA_LOGS / "settings.json"
SISTEMAS_RPG = {
    "D&D 5e": "DnD5e.md",
    "Tormenta20": "Tormenta20.md",
    "Pathfinder 2e": "Pathfinder2e.md",
    "Generic / Regras Livres": "Generico.md"
}

PERFIS_TOM = {
    "Dark Fantasy (Grimdark)": (
        "# DIRETRIZ DE TOM E CLIMA: DARK FANTASY (GRIMDARK)\n\n"
        "- As descrições devem focar em atmosfera sombria, visceral, perigo iminente e decadência.\n"
        "- Evite resoluções fáceis, vilões caricatos ou maniqueísmo puro (bem vs mal absoluto).\n"
        "- Destaque detalhes sensoriais: o frio, o cheiro de ferrugem, o ranger de madeira, a penumbra e o silêncio desconfortável.\n"
        "- A magia e o desconhecido devem parecer perigosos e imprevisíveis."
    ),
    "High Fantasy Épico": (
        "# DIRETRIZ DE TOM E CLIMA: HIGH FANTASY ÉPICO\n\n"
        "- As descrições devem ser grandiosas, vibrantes e solenes, destacando o heroísmo e maravilhas mágicas.\n"
        "- Destaque arquiteturas imponentes, linhagens nobres, relíquias reluzentes e grande profundidade histórica.\n"
        "- A magia é uma força presente e visível no mundo, moldando paisagens e reinos."
    ),
    "Mistério & Investigação": (
        "# DIRETRIZ DE TOM E CLIMA: MISTÉRIO E INVESTIGAÇÃO\n\n"
        "- Foque em pistas sutis, segredos velados, meias-verdades e motivações ocultas.\n"
        "- As descrições devem instigar a curiosidade, deixando lacunas para o leitor ou jogador conectar os pontos.\n"
        "- Mantenha um tom sóbrio, analítico e repleto de suspense."
    ),
    "Cyberpunk / Sci-Fi": (
        "# DIRETRIZ DE TOM E CLIMA: CYBERPUNK / SCI-FI\n\n"
        "- Descrições focadas no contraste entre alta tecnologia e decadência urbana/social.\n"
        "- Use terminologias técnicas, luzes de neon na escuridão, intriga corporativa e atmosferas cínicas."
    ),
    "Nenhum / Neutro": (
        "# DIRETRIZ DE TOM E CLIMA: NEUTRO\n\n"
        "- Mantenha um tom informativo, claro e descritivo padrão para worldbuilding de RPG sem viés de gênero."
    )
}

DEFAULT_SETTINGS = {
    "auto_expander": False,
    "wb_allow_create_folder": True,
    "wb_allow_create_file": True,
    "wb_allow_improve_file": True,
    "tom_clima_perfil": "Dark Fantasy (Grimdark)",
    "rpg_sistema_ativo": "D&D 5e"
}

def carregar_configuracoes():
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
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

def escrever_arquivo_estilo_tom(nome_perfil):
    """Cria/sobrescreve o arquivo Tom_e_Clima.md na pasta de Estilo configurada no .env."""
    try:
        pasta_estilo = pu.CAMINHO_ESTILO
        pasta_estilo.mkdir(parents=True, exist_ok=True)
        
        caminho_arquivo = pasta_estilo / "Tom_e_Clima.md"
        conteudo = PERFIS_TOM.get(nome_perfil, PERFIS_TOM["Nenhum / Neutro"])
        
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo)
            
        print(f"Arquivo de tom atualizado em Style: {caminho_arquivo.name} ({nome_perfil})")
    except Exception as e:
        print(f"Erro ao escrever arquivo de tom em Style: {e}")


class OptionsFrame(ttk.Frame):
    def __init__(self, parent, log_callback, toast_callback, page_header_callback):
        super().__init__(parent)
        self.log_callback = log_callback
        self.toast_callback = toast_callback
        self.settings = carregar_configuracoes()

        page_header_callback(self, "Opções do Sistema", "Configure comportamentos automáticos e estilo do cenário.")

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # -------------------------------------------------------------
        # GRUPO 1: Tom e Clima do Cenário (Salva em Style/*.md)
        # -------------------------------------------------------------
        tom_box = ttk.LabelFrame(body, text=" Tom e Clima do Cenário (Style/*.md) ")
        tom_box.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            tom_box,
            text="Escolha o tom do cenário. Esta opção atualiza o arquivo 'Tom_e_Clima.md' na pasta de Estilo:"
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        self.combo_tom = ttk.Combobox(
            tom_box,
            state="readonly",
            values=list(PERFIS_TOM.keys()),
            font=("Segoe UI", 10)
        )
        perfil_atual = self.settings.get("tom_clima_perfil", "Dark Fantasy (Grimdark)")
        self.combo_tom.set(perfil_atual)
        self.combo_tom.pack(fill=tk.X, padx=10, pady=(0, 12))
        self.combo_tom.bind("<<ComboboxSelected>>", self._on_tom_change)

        # Garante que o arquivo de tom existe no disco na inicialização
        escrever_arquivo_estilo_tom(perfil_atual)

        # -------------------------------------------------------------
        # GRUPO 2: Sistema do Jogo
        # -------------------------------------------------------------
        sistem_box = ttk.LabelFrame(body, text=" Sistema de Regras de RPG ")
        sistem_box.pack(fill=tk.X, pady=(0, 15))

        self.combo_sistema = ttk.Combobox(
            sistem_box, state="readonly", 
            values=list(SISTEMAS_RPG.keys()), font=("Segoe UI", 10)
        )
        self.combo_sistema.set(self.settings.get("rpg_sistema_ativo", "D&D 5e"))
        self.combo_sistema.pack(fill=tk.X, padx=10, pady=10)
        # -------------------------------------------------------------
        # GRUPO 3: Automação do Expander
        # -------------------------------------------------------------
        expander_opt_box = ttk.LabelFrame(body, text=" Automação do Expander ")
        expander_opt_box.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            expander_opt_box, 
            text="Executar o Expander automaticamente ao salvar um arquivo com a tag <-- TODO:"
        ).pack(anchor=tk.W, padx=10, pady=(10, 8))

        valor_inicial = bool(self.settings.get("auto_expander", False))
        self.auto_expander_var = tk.BooleanVar(value=valor_inicial)

        radio_frame = ttk.Frame(expander_opt_box)
        radio_frame.pack(anchor=tk.W, padx=10, pady=(0, 12))

        ttk.Radiobutton(
            radio_frame, text="Desabilitado", value=False,
            variable=self.auto_expander_var, command=self._on_auto_expander_change
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            radio_frame, text="Habilitado", value=True,
            variable=self.auto_expander_var, command=self._on_auto_expander_change
        ).pack(side=tk.LEFT)

        # -------------------------------------------------------------
        # GRUPO 4: Permissões do WorldBuilder
        # -------------------------------------------------------------
        wb_opt_box = ttk.LabelFrame(body, text=" WorldBuilder - Permissões de Ação ")
        wb_opt_box.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            wb_opt_box,
            text="Selecione quais ações o WorldBuilder está autorizado a executar autonomamente:"
        ).pack(anchor=tk.W, padx=10, pady=(10, 8))

        self._criar_opcao_wb(wb_opt_box, "Criar Pastas (CreateFolder):", "wb_allow_create_folder")
        self._criar_opcao_wb(wb_opt_box, "Criar Arquivos (CreateFile):", "wb_allow_create_file")
        self._criar_opcao_wb(wb_opt_box, "Melhorar Arquivos (ImproveFile):", "wb_allow_improve_file")

    def _on_tom_change(self, event):
        novo_tom = self.combo_tom.get()
        self.settings["tom_clima_perfil"] = novo_tom
        salvar_configuracoes(self.settings)
        escrever_arquivo_estilo_tom(novo_tom)

        if self.log_callback:
            self.log_callback(f"Tom do Cenário alterado para: {novo_tom}")
        if self.toast_callback:
            self.toast_callback(f"🎨 Estilo '{novo_tom}' salvo na pasta Style!")

    def is_auto_expander_enabled(self):
        return bool(self.auto_expander_var.get())

    def _on_auto_expander_change(self):
        habilitado = self.is_auto_expander_enabled()
        self.settings["auto_expander"] = habilitado
        salvar_configuracoes(self.settings)

        status_str = "Habilitado" if habilitado else "Desabilitado"
        if self.log_callback:
            self.log_callback(f"Expander Automático ao salvar: {status_str.upper()}")
        if self.toast_callback:
            self.toast_callback(f"⚙️ Expander Automático {status_str}!")

    def _criar_opcao_wb(self, parent_box, titulo, chave_setting):
        frame_linha = ttk.Frame(parent_box)
        frame_linha.pack(fill=tk.X, padx=10, pady=4)

        ttk.Label(frame_linha, text=titulo, width=30, anchor="w").pack(side=tk.LEFT)

        var = tk.BooleanVar(value=bool(self.settings.get(chave_setting, True)))
        setattr(self, f"var_{chave_setting}", var)

        ttk.Radiobutton(
            frame_linha, text="Desabilitado", value=False, variable=var,
            command=lambda: self._on_wb_setting_change(chave_setting, var, titulo)
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            frame_linha, text="Habilitado", value=True, variable=var,
            command=lambda: self._on_wb_setting_change(chave_setting, var, titulo)
        ).pack(side=tk.LEFT)

    def _on_wb_setting_change(self, chave_setting, var, titulo):
        habilitado = bool(var.get())
        self.settings[chave_setting] = habilitado
        salvar_configuracoes(self.settings)

        status_str = "HABILITADO" if habilitado else "DESABILITADO"
        if self.log_callback:
            self.log_callback(f"WorldBuilder -> {titulo} {status_str}")
        if self.toast_callback:
            self.toast_callback(f"⚙️ {titulo.split('(')[0].strip()}: {status_str.title()}!")