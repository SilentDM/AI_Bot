import os
import time
import re
import glob
import tiktoken
from google import genai
from google.genai import types

MEMORIES_DIR = "memories"
enc = tiktoken.get_encoding("cl100k_base")

# Garante que a pasta memories exista no caminho do projeto
os.makedirs(MEMORIES_DIR, exist_ok=True)

def sanitize_name(name):
    """Substitui caracteres inválidos de nomes por sublinhados para segurança do arquivo."""
    if not name:
        return "unknown"
    # Remove qualquer caractere que não seja alfanumérico, hífen ou sublinhado
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    # Remove repetições de sublinhados e limpa as pontas
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized or "unknown"

def _buscar_arquivo_existente(guild_id, userid):
    """Procura na pasta se existe um arquivo que termine com o ID do servidor e do usuário."""
    g_id = guild_id if guild_id else "dm"
    # Padrão de busca: memoria_*_IDSERVIDOR_*_IDUSUARIO.txt
    pattern = os.path.join(MEMORIES_DIR, f"memoria_*_{g_id}_*_{userid}.txt")
    arquivos = glob.glob(pattern)
    if arquivos:
        return arquivos[0]
    return None

def _obter_caminho_alvo(guild_id, guild_name, userid, user_name):
    """Gera o caminho ideal com os nomes e IDs atuais."""
    g_id = guild_id if guild_id else "dm"
    g_name = sanitize_name(guild_name) if guild_id else "DM"
    u_name = sanitize_name(user_name)
    return os.path.join(MEMORIES_DIR, f"memoria_{g_name}_{g_id}_{u_name}_{userid}.txt")

def trim_incomplete_sentences(texto):
    if not texto:
        return ""
    texto = texto.strip()
    if texto.endswith((".", "!", "?")):
        return texto

    frases = re.split(r'(?<=[.!?])\s+', texto)
    if len(frases) <= 1:
        return frases[0] if frases else texto

    frases = frases[:-1]
    resultado = " ".join(frases).strip()

    if not resultado.endswith((".", "!", "?")):
        resultado += "."

    return resultado

def criar_resumo_google(geminiclient, memorias):
    instrucao_sistema = (
        "[Personalidade]\n"
        "Você é um assistente especializado em resumir informações em uma única frase, "
        "simples e direta. Explicando tudo que lhe for passado de forma concisa."
    )
    corpo_usuario = f"Faça o resumo das seguintes interações:\n{memorias}"
    config = types.GenerateContentConfig(
        system_instruction=instrucao_sistema,
        temperature=0.5,
        top_p=0.9,
        max_output_tokens=2048
    )
    try:
        response = geminiclient.models.generate_content(
            model="gemini-3.5-flash",
            contents=corpo_usuario,
            config=config
        )
        return trim_incomplete_sentences(response.text)
    except Exception as e:
        print(f"\n--- 🛑 ERRO AO GERAR RESUMO EM MEMORIES ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem: {e}")
        return ""

def carregar_memorias(guild_id, guild_name, userid, user_name):
    """
    Busca o arquivo de memórias. Se encontrar um correspondente por ID, mas com nomes antigos,
    o arquivo é renomeado automaticamente para os nomes atualizados.
    """
    arquivo_existente = _buscar_arquivo_existente(guild_id, userid)
    caminho_ideal = _obter_caminho_alvo(guild_id, guild_name, userid, user_name)
    
    if arquivo_existente:
        # Se o arquivo físico encontrado tem um nome diferente do ideal (servidor/user mudou de nome)
        if os.path.abspath(arquivo_existente) != os.path.abspath(caminho_ideal):
            try:
                os.rename(arquivo_existente, caminho_ideal)
                print(f"Renomeando memória de {arquivo_existente} para {caminho_ideal} (Atualização de Nomes)")
            except OSError:
                pass
            arquivo_final = caminho_ideal
        else:
            arquivo_final = arquivo_existente
    else:
        arquivo_final = caminho_ideal

    try:
        with open(arquivo_final, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta, geminiclient):
    """Salva a interação atual, aplicando a expiração por idade e resumo por token."""
    arquivo_existente = _buscar_arquivo_existente(guild_id, userid)
    caminho_ideal = _obter_caminho_alvo(guild_id, guild_name, userid, user_name)
    
    if arquivo_existente:
        if os.path.abspath(arquivo_existente) != os.path.abspath(caminho_ideal):
            try:
                os.rename(arquivo_existente, caminho_ideal)
            except OSError:
                pass
            arquivo_final = caminho_ideal
        else:
            arquivo_final = arquivo_existente
    else:
        arquivo_final = caminho_ideal

    # Verifica tempo de validade do arquivo (7 dias)
    if os.path.exists(arquivo_final):
        ultima_mod = os.path.getmtime(arquivo_final)
        idade_horas = (time.time() - ultima_mod) / 3600
        if idade_horas > 168:
            print(f"Memória do usuário {user_name} ({userid}) expirou. Limpando arquivo...")
            try:
                os.remove(arquivo_final)
            except OSError:
                pass

    # Registra a nova mensagem
    with open(arquivo_final, "a", encoding="utf-8") as f:
        f.write(f"Prompt Usuário: {prompt}\nResposta: {resposta}\n")

    # Avaliação de tamanho do arquivo
    with open(arquivo_final, "r", encoding="utf-8") as f:
        conteudo = f.read()

    tamanho = len(enc.encode(conteudo))
    if tamanho > 20480:
        print(f"Memória de {user_name} excedeu o tamanho máximo. Gerando resumo...")
        resumo = criar_resumo_google(geminiclient, conteudo)
        if resumo:
            with open(arquivo_final, "w", encoding="utf-8") as f:
                f.write(f"Resumo de Memórias: {resumo}\n")