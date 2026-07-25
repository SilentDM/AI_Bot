import os
import tkinter as tk
import engine.project_utils as pu
from tkinter import ttk, messagebox
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(pu.PROJECT_ROOT / ".env")
load_dotenv(pu.PROJECT_ROOT / ".env")

class SetupWizard:
    """
    Janela de configuração inicial (primeira execução).
    Pede, em sequência, cada informação necessária para o .env.

    Os passos NÃO são uma lista fixa: depois que o usuário escolhe qual
    provedor de IA vai usar (Gemini gratuito ou "Pro"), o próximo passo
    muda dinamicamente para pedir a chave certa — nunca as duas juntas.
    Por isso _passos() é um MÉTODO (recalculado a cada navegação), e não
    uma lista fixa definida uma única vez.
    """

    def __init__(self):
        self.valores = {}
        self.passo_atual = 0
        self.concluido = False

        self.root = tk.Tk()
        self.root.title("Configuração Inicial — Ao Multiverse Console")
        self.root.geometry("540x340")
        self.root.resizable(False, False)
        self.root.configure(bg="#121212")
        self.root.protocol("WM_DELETE_WINDOW", self._confirmar_cancelamento)

        self._montar_estilo()
        self._montar_layout()
        self._mostrar_passo(0)

        self.root.mainloop()

    # ------------------------------------------------------------------
    # VISUAL (mesma paleta dark do resto do programa)
    # ------------------------------------------------------------------
    def _montar_estilo(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#121212", foreground="#e3e3e3",fieldbackground="#1e1e1e", font=("Segoe UI", 10))
        style.configure("TButton", background="#252526", foreground="#e3e3e3", padding=6)
        style.map("TButton", background=[("active", "#333333")])
        style.configure("TEntry", fieldbackground="#252526", foreground="#ffffff")
        style.configure("TCombobox", fieldbackground="#252526", foreground="#ffffff")
        style.map("TCombobox", fieldbackground=[("readonly", "#252526")],foreground=[("readonly", "#ffffff")])
        style.configure("Titulo.TLabel", background="#121212", foreground="#10b981",font=("Segoe UI", 13, "bold"))
        style.configure("Descricao.TLabel", background="#121212", foreground="#aaaaaa",font=("Segoe UI", 9), wraplength=460, justify="left")
        style.configure("Passo.TLabel", background="#121212", foreground="#666666",font=("Segoe UI", 8))

    def _montar_layout(self):
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)
        self._container = container

        self.lbl_passo = ttk.Label(container, style="Passo.TLabel")
        self.lbl_passo.pack(anchor=tk.W)

        self.lbl_titulo = ttk.Label(container, style="Titulo.TLabel")
        self.lbl_titulo.pack(anchor=tk.W, pady=(2, 8))

        self.lbl_descricao = ttk.Label(container, style="Descricao.TLabel")
        self.lbl_descricao.pack(anchor=tk.W, pady=(0, 15))

        # Campo de texto/senha (usado quando o passo NÃO é um dropdown)
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(container, textvariable=self.entry_var, font=("Segoe UI", 11))
        self.entry.bind("<Return>", lambda e: self._avancar())

        # Dropdown (usado quando o passo É uma escolha entre opções, ex: provedor de IA)
        self.combo = ttk.Combobox(container, state="readonly", font=("Segoe UI", 11))
        self._opcoes_atuais = []

        self.lbl_erro = ttk.Label(container, text="", foreground="#ef4444", background="#121212")
        self.lbl_erro.pack(anchor=tk.W, pady=(0, 10))

        botoes = ttk.Frame(container)
        botoes.pack(fill=tk.X, pady=(15, 0), side=tk.BOTTOM)

        self.btn_voltar = ttk.Button(botoes, text="◀ Voltar", command=self._voltar)
        self.btn_voltar.pack(side=tk.LEFT)

        self.btn_avancar = ttk.Button(botoes, text="Avançar ▶", command=self._avancar)
        self.btn_avancar.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # DEFINIÇÃO DOS PASSOS (dinâmica — depende de respostas anteriores)
    # ------------------------------------------------------------------
    def _passos(self):
        """
        Retorna a lista de passos ATUAL, considerando o que já foi
        respondido até agora. Cada item é uma tupla:
        (chave_env, título, descrição, obrigatório, tipo, valor_padrão, opções)

        tipo: "texto" | "senha" | "dropdown"
        opções: só usado quando tipo == "dropdown" -> lista de (valor_interno, rótulo_exibido)
        """
        passos = [
            ("PASTA_PROJETO", "Pasta do Projeto",
            "Nome da pasta onde o seu mundo/lore será construído.\n"
            "Ela será criada automaticamente se não existir.",
            True, "texto", "Phaeton", None),

            ("PASTA_ESTILO", "Pasta de Estilo",
            "Nome da pasta com diretrizes de estilo de escrita (opcional,\n"
            "usada pelo Expander para guiar o tom dos textos gerados).",
            False, "texto", "Style", None),

            ("AI_PROVIDER", "Qual IA você vai usar?",
            "Escolha o motor de IA que vai gerar as respostas e o conteúdo do mundo.",
            True, "dropdown", "gemini", [
                ("gemini", "Gemini (gratuito, chave do Google)"),
                ("pro", "IA Pro (chave de outro provedor)"),
            ]),
        ]

        # --- Passo condicional: a chave certa, de acordo com o provedor escolhido acima ---
        provedor = self.valores.get("AI_PROVIDER", "gemini")
        if provedor == "pro":
            passos.append((
                "PRO_API_KEY", "Chave da IA Pro",
                "Cole aqui a chave de API do provedor 'Pro' que você vai usar\n"
                "(ex: a chave da conta paga do seu amigo). OBRIGATÓRIO.",
                True, "senha", "", None
            ))
        else:
            passos.append((
                "GOOGLE_API_KEY", "Chave da API do Gemini",
                "Cole aqui sua chave gratuita da API do Google Gemini.\n"
                "Este campo é OBRIGATÓRIO — o programa não funciona sem ele.",
                True, "senha", "", None
            ))

        passos.append((
            "DISCORD_TOKEN", "Token do Discord (opcional)",
            "Cole aqui o token do seu bot do Discord.\n"
            "Deixe em branco se você não for usar o bot do Discord —\n"
            "essa parte do programa fica automaticamente desativada.",
            False, "senha", "", None
        ))

        return passos

    # ------------------------------------------------------------------
    # NAVEGAÇÃO ENTRE OS PASSOS
    # ------------------------------------------------------------------
    def _mostrar_passo(self, indice):
        passos = self._passos()
        self.passo_atual = indice
        chave, titulo, descricao, obrigatorio, tipo, padrao, opcoes = passos[indice]

        self.lbl_passo.config(text=f"Passo {indice + 1} de {len(passos)}")
        self.lbl_titulo.config(text=titulo + (" *" if obrigatorio else ""))
        self.lbl_descricao.config(text=descricao)
        self.lbl_erro.config(text="")

        valor_existente = self.valores.get(chave, padrao)

        if tipo == "dropdown":
            self.entry.pack_forget()
            self._opcoes_atuais = opcoes
            self.combo["values"] = [rotulo for _, rotulo in opcoes]
            rotulo_atual = next((r for v, r in opcoes if v == valor_existente), opcoes[0][1])
            self.combo.set(rotulo_atual)
            self.combo.pack(fill=tk.X, pady=(0, 5), before=self.lbl_erro)
            self.combo.focus_set()
        else:
            self.combo.pack_forget()
            self.entry_var.set(valor_existente)
            self.entry.config(show="*" if tipo == "senha" else "")
            self.entry.pack(fill=tk.X, pady=(0, 5), before=self.lbl_erro)
            self.entry.focus_set()
            self.entry.selection_range(0, tk.END)

        self.btn_voltar.config(state=(tk.NORMAL if indice > 0 else tk.DISABLED))
        ultimo = indice == len(passos) - 1
        self.btn_avancar.config(text="Concluir ✅" if ultimo else "Avançar ▶")

    def _voltar(self):
        if self.passo_atual > 0:
            self._salvar_passo_atual()
            self._mostrar_passo(self.passo_atual - 1)

    def _avancar(self):
        passos = self._passos()
        chave, titulo, descricao, obrigatorio, tipo, padrao, opcoes = passos[self.passo_atual]

        valor = self.combo.get() if tipo == "dropdown" else self.entry_var.get().strip()

        if obrigatorio and not valor:
            self.lbl_erro.config(text="⚠️ Este campo é obrigatório.")
            return

        self._salvar_passo_atual()

        # IMPORTANTE: recalculamos os passos DEPOIS de salvar, porque a
        # resposta que acabou de ser salva (ex: qual provedor de IA) pode
        # ter mudado quais passos vêm a seguir.
        passos_atualizados = self._passos()
        if self.passo_atual < len(passos_atualizados) - 1:
            self._mostrar_passo(self.passo_atual + 1)
        else:
            self._finalizar()

    def _salvar_passo_atual(self):
        passos = self._passos()
        chave, titulo, descricao, obrigatorio, tipo, padrao, opcoes = passos[self.passo_atual]
        if tipo == "dropdown":
            rotulo_escolhido = self.combo.get()
            # Converte o rótulo visível (ex: "Gemini (gratuito...)")
            # de volta para o valor interno gravado no .env (ex: "gemini")
            valor_interno = next((v for v, r in opcoes if r == rotulo_escolhido), padrao)
            self.valores[chave] = valor_interno
        else:
            self.valores[chave] = self.entry_var.get().strip()

    def _confirmar_cancelamento(self):
        if messagebox.askyesno(
            "Cancelar configuração",
            "O programa precisa dessas informações para funcionar.\n"
            "Deseja realmente sair sem concluir a configuração?"
        ):
            self.root.destroy()
            raise SystemExit("Configuração inicial cancelada pelo usuário.")

    # ------------------------------------------------------------------
    # FINALIZAÇÃO: GRAVA O .env
    # ------------------------------------------------------------------
    def _finalizar(self):
        linhas = [
            f"AI_PROVIDER={self.valores.get('AI_PROVIDER', 'gemini')}",
            f"DISCORD_TOKEN={self.valores.get('DISCORD_TOKEN', '')}",
            f"PASTA_PROJETO={self.valores.get('PASTA_PROJETO', 'Phaeton')}",
            f"PASTA_ESTILO={self.valores.get('PASTA_ESTILO', 'Style')}",
        ]

        # Grava só a chave do provedor que foi de fato escolhido.
        if self.valores.get("AI_PROVIDER") == "pro":
            linhas.append(f"PRO_API_KEY={self.valores.get('PRO_API_KEY', '')}")
        else:
            linhas.append(f"GOOGLE_API_KEY={self.valores.get('GOOGLE_API_KEY', '')}")

        ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        self.concluido = True

        aviso = "✅ Configuração concluída!\n\nO programa vai iniciar agora."
        if not self.valores.get("DISCORD_TOKEN"):
            aviso += "\n\nℹ️ Nenhum token do Discord informado — o bot ficará desativado."
        messagebox.showinfo("Tudo pronto!", aviso)

        self.root.destroy()


def garantir_env():
    """
    Garante que o arquivo .env exista com as configurações necessárias.
    Se não existir, abre o assistente gráfico (SetupWizard) — só acontece
    na primeira execução do programa.

    IMPORTANTE: esta função deve ser chamada bem no início de qualquer script
    de entrada (gui.py, dbot.py), ANTES de importar ai_utils, project_utils, etc.
    Esses módulos leem variáveis de ambiente assim que são importados.
    """
    if not ENV_PATH.exists():
        wizard = SetupWizard()
        if not wizard.concluido:
            raise SystemExit("Configuração inicial não foi concluída. Encerrando.")

    