# 🜂 Silent Multiverse Nexus

> **Plataforma inteligente de Worldbuilding, Gestão de Lore para RPG e Assistente IA com Bot de Discord Integrado.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Gemini API](https://img.shields.io/badge/Google%20Gemini-Context%20Caching-orange?style=for-the-badge&logo=google)
![Discord.py](https://img.shields.io/badge/Discord.py-Bot-5865F2?style=for-the-badge&logo=discord)
![Obsidian Compatible](https://img.shields.io/badge/Obsidian-Native%20Vault%20Support-7A3EE8?style=for-the-badge&logo=obsidian)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

O **Silent Multiverse Nexus** é uma suíte completa de ferramentas para Mestres de RPG, Escritores e Criadores de Cenários. Ele combina a escrita nativa em Markdown, o poder do ecossistema do **Obsidian.md**, automação com modelos de Inteligência Artificial e um Bot de Discord com **filtro mecânico de segredos** para interagir com jogadores e mestres.

---

## Principais Funcionalidades

### 1. Integração Nascida para o Obsidian.md
* **Suporte Direto a Cofres (Vaults)**: Aponte o programa diretamente para a pasta do seu Cofre no Obsidian.
* **Leitura de Wikilinks (`[[Nota]]`) e Frontmatter YAML**: Compatibilidade nativa com tags e links internos do Obsidian.
* **Trabalho em Paralelo**: Escreva e visualize grafos no Obsidian enquanto a IA do Silent Multiverse expande a lore em tempo real.

---

### 2. Bot de Discord "Ao" com Filtro Mecânico de Segredos
* **Persona de Criador ("Ao")**: Responde dúvidas sobre o universo em tempo real nos canais do seu servidor.
* **Segurança Anti-Vazamento (100% Determinística)**: 
  * Não depende do modelo de IA decidir o que é segredo.
  * **Seções Secretas**: Adicione `[SEGREDO]` em qualquer cabeçalho (`## O Culto [SEGREDO]`) para que o texto e suas subseções sejam **cortados do contexto** enviado aos jogadores.
  * **Arquivos Secretos**: Adicione `status: segredo` para ocultar o arquivo inteiro.
* **Bundle Duplo na Nuvem**: O sistema mantém automaticamente 2 contextos em cache no Gemini API (Visão do Mestre e Visão do Jogador) via Files API / Context Caching.
* **Identificação do Mestre**: Mensagens privadas (DMs) ou comandos enviados pelo ID do Mestre acessam a visão 100% completa com todos os segredos.

---

### 3. WorldBuilder & Expander Autônomo
* **Expander por Tags**: Preenche lacunas marcadas com `<-- TO DO:` analisando o contexto de todo o projeto e arquivos relacionados.
* **Versionamento Não-Destrutivo**: Nenhuma alteração da IA sobrescreve seu trabalho direto. Versões anteriores são arquivadas automaticamente em `logs/history/` (`_v01`, `_v02`).
* **WorldBuilder com Pydantic**: Planeja e executa etapas de expansão estruturadas (`CreateFolder`, `CreateFile`, `ImproveFile`) respeitando permissões configuráveis.
* **Templates Dinâmicos**: Crie novos arquivos com estruturas pré-definidas para *Aventuras, Cidades, Locais, NPCs e Reinados* (varredura dinâmica da pasta `Templates/`).

---

### 4. Compilador de Livro do Cenário
* Converte todo o seu projeto de lore em um **Livro Digital Único em HTML/PDF** no estilo *Dark Fantasy*.
* Sumário automático (TOC) gerado a partir da ordem das pastas.
* Pronto para navegação interna, leitura off-line ou impressão em formato de compêndio.

---

### 5. Auditoria de Lore Integrada
* Varre todo o universo em busca de **incoerências históricas, contradições geográficas, furos de cronologia e conceitos órfãos**.
* Gera relatórios detalhados em Markdown com sugestões de correção.

---

### 6. Console Desktop Leve & System Tray
* **Interface Tkinter Dark Mode**: Explorer de arquivos com *Drag & Drop*, busca global instantânea e editor embutido.
* **Modo Bandeja (System Tray)**: Minimiza para os ícones ocultos ao lado do relógio do Windows, permitindo que o Bot do Discord continue online 24/7.
* **Otimização Extrema de RAM**: Libera memória inativa ao minimizar, reduzindo o consumo de **~116 MB para cerca de 15 MB de RAM** em segundo plano.
* **Assistente de Configuração Inicial (`setup_env.py`)**: Configura as chaves de API (`.env`) no primeiro acesso de forma 100% visual.

### 7. Sistema de Tags do Projeto
* **<-- TO DO: motivo:**	Em qualquer arquivo .md,	sinaliza para o Expander preencher aquela lacuna com IA.
* **[SEGREDO]:**	Em um título (## O Culto [SEGREDO]),	remove a seção e suas subseções mecanicamente das consultas dos jogadores.
* **status: segredo:**	No cabeçalho YAML do arquivo,	oculta o arquivo inteiro das consultas dos jogadores.
* **status: rascunho:**	No cabeçalho do arquivo,	oculta o arquivo das leituras do contexto de IA até estar pronto.

---

## Como Usar

### Opção A: Executável para Usuários (Recomendado)
1. Vá até a aba [**Releases**](../../releases) do repositório.
2. Baixe o arquivo `SilentMultiverse.zip`.
3. Descompacte e execute o `SilentMultiverse.exe`. 
4. O assistente de configuração abrirá automaticamente para você inserir sua chave de API gratuita do Google Gemini e/ou Token do Discord.

---

### Opção B: Executando a partir do Código-Fonte (Desenvolvedores)

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/SilentDM/AI_Bot
   cd SEU_REPOSITORIO
2. **Crie e ative um ambiente virtual:**
python -m venv venv
- No Windows (CMD):
> venv\Scripts\activate.bat
- No Windows (PowerShell):
> .\venv\Scripts\Activate.ps1

3. **Instale as dependências:**
> pip install google-genai discord.py python-dotenv pydantic openai pystray Pillow

4. **Execute a aplicação:**
- Crie um arquivo run.vbs
   ```bash
  Set objShell = CreateObject("WScript.Shell")
  Set objFSO = CreateObject("Scripting.FileSystemObject")
  strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
  objShell.CurrentDirectory = strPath
  ' Usa o pythonw de dentro da build_env para garantir que todas as bibliotecas existam
  objShell.Run "build_env\Scripts\pythonw.exe main.py", 0, False

----

# Melhorias futuras

- Permitir escolher a invocação de comando para fazer perguntas ao bot do discord (Atualmente !ao está hardcoded)
