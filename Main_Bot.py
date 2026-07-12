from email.mime import message
import json
import unicodedata, re
from unittest import result
from distro import info
from sympy import true
import discord, os, requests, time, traceback, sys
import tiktoken
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
import google.genai 
CHANNEL_ID = 1519013814039871632
TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY, transport='rest') # transport='rest' ajuda em alguns ambientes
model = genai.GenerativeModel('gemini-3.5-flash')
enc = tiktoken.get_encoding("cl100k_base")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def gerar_resposta_google(prompt, extra, info, persona, regras, memorias):
    instrucao_sistema = f"{persona}\n{regras}\nMemorias Relevantes: {memorias}\nInformations: {info}\n"
    corpo_usuario = f"{prompt}\n{extra}"
    generation_config = {
        "temperature": 0.5,
        "top_p": 0.9,
        "max_output_tokens": 20480 # Equivalente ao seu max_length        
    }
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash",
        system_instruction=instrucao_sistema,
        generation_config=generation_config
    )
    try:
        response = model.generate_content(corpo_usuario, generation_config=generation_config)
        with open("resposta.json", "w", encoding="utf-8") as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
        return response.text
    except Exception as e:
        print("\n--- 🛑 ERRO DETECTADO ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem:{e}")

def criar_memorias_user(userid,prompt,resposta):
        arquivo = f"memorias_{userid}.txt"
        if os.path.exists(arquivo):
                ultima_mod = os.path.getmtime(arquivo)
                idade_horas = (time.time() - ultima_mod) / 3600
                if idade_horas > 168: #1 semana
                    print(f"Memória do usuário {userid} tem mais de 168 horas. Recomeçando memória!")        
                    os.remove(arquivo)
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"Prompt Usuário: {prompt}\nResposta: {resposta}\n")
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
        tamanho = len(enc.encode(conteudo))
        if tamanho > 20480: #80 mensagens de 256 tokens
            print(f"Memória do usuário {userid} excedeu tamanho máximo. Criando resumo...")
            resumo = criar_resumo_google(userid,conteudo)
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(resumo + "\n")
        
def carregarmemorias_userid(userid):
    try:
        with open(f"memorias_{userid}.txt", "r", encoding="utf-8") as f:
            memorias = f.read()
            return memorias
    except FileNotFoundError:
        return ""

def carregar_outras_memorias():
    memorias = ""
    for arquivo in os.listdir():
        if arquivo.startswith("memorias_") and arquivo.endswith(".txt"):
            with open(arquivo, "r", encoding="utf-8") as f:
                memorias += f.read() + "\n"
    return memorias

def criar_resumo_google(userid,memorias):
    instrucao_sistema = "[Personalidade]\nVocê é um assistente especializado em resumir informações em uma única frase, simples e direta. Explicando tudo que lhe for passado de forma concissa."
    corpo_usuario = f"Faça o resumo das seguintes interações:\n{memorias}"
    generation_config = {
        "temperature": 0.5,
        "top_p": 0.9,
        "max_output_tokens": 2048 # Equivalente ao seu max_length        
    }
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash",
        system_instruction=instrucao_sistema,
        generation_config=generation_config
    )
    try:
        response = model.generate_content(corpo_usuario, generation_config=generation_config)
        criar_memorias_user(userid, "Resumo de Memórias", response.text)
    except Exception as e:
        print("\n--- 🛑 ERRO DETECTADO ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem:{e}")

def trim_incomplete_sentences(texto):
    if texto:
        texto = texto.strip()
    else:
        return ""
    if texto.endswith((".", "!", "?")):
        return texto

    # Divide por finais de frase
    frases = re.split(r'(?<=[.!?])\s+', texto)

    # Se só tem uma frase, não dá pra salvar muito
    if len(frases) <= 1:
        return frases[0] if frases else texto

    # Remove última frase (provavelmente incompleta)
    frases = frases[:-1]

    resultado = " ".join(frases).strip()

    # Garantir que termina corretamente
    if not resultado.endswith((".", "!", "?")):
        resultado += "."

    return resultado

def carregar_phaeton():
    with open("Phaeton.txt", "r", encoding="latin1") as f:
        return f.read()

def detectar_intencao(pergunta):
    if "onde" in pergunta:
        return "Foque na localização"
    elif "quando" in pergunta:
        return "Foque no histórico ou cronologia"
    elif "quem" in pergunta:
        return "Foque na entidade ou pessoa"
    elif "como" in pergunta:
        return "Foque no método ou processo"
    elif "por que" in pergunta or "porque" in pergunta:
        return "Foque na causa"
    else:
        return ""


@client.event
async def on_ready():
    print(f'Logado como {client.user}')
    #channel = client.get_channel(CHANNEL_ID)
    #await channel.send(f"\u200b\nTest message from Python!")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content.lower().startswith("!ao"):
        match message.content.lower():
            case "!ao,":
                prompt = message.content.replace("!ao,", "")    
            case "!ao ":
                prompt = message.content.replace("!ao ", "")    
            case _:
                prompt = message.content.replace("!ao", "")    
                
        print(f"Mensagem recebida! {prompt}")
        userid = message.author.id
        memorias=""
        persona = """[Personalidade]\n- Você é Ao, o criador do universo. Está aqui para responder dúvidas, com gentileza e sabedoria.\n- Sempre se refira a Ao em primeira pessoa.\n- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas."""
        regras = """[REGRAS]\n- Não ofereça e não peça por mais informações;\n- Responda de forma clara e concisa;\n- Não faça julgamentos de valor;\n- Pode criar histórias e lugares fictícios, mas não altere informações já definidas;\n"""
        info = carregar_phaeton()
        print("Info Carregada!")
        extra = detectar_intencao(prompt)   
        if extra:
            print("Intenção definida!")
        else:
            print("Nenhuma intenção detectada!")
        memorias = carregarmemorias_userid(userid)
        if memorias:
            print("Memória Carregada!")
        else:
            print("Usuário sem memória! Vamos criar uma no final!")
        
        #memoriasalheias = carregar_outras_memorias()
        resposta = gerar_resposta_google(prompt,extra, info, persona, regras, memorias)
        if resposta:
            print("Resposta criada!")
        finalz=[".","!","?"]
        if resposta.rstrip()[-1] not in finalz:
            resposta = trim_incomplete_sentences(resposta)
        paragraph=[]
        
        if len(resposta)>1900:
            print("Resposta muito grande!")
            paragraph = [p for p in resposta.split("\n\n") if p.strip()]
            buffer=""
            for x,p in enumerate(paragraph):
                if buffer:
                    buffer+="\n\n"+ paragraph[x]
                    print(f"\nBuffer Atual:{buffer}")
                else:
                    buffer = paragraph[x]
                    print(f"\nBuffer Atual:{buffer}")
                
                if len(buffer)>1300:
                    await message.channel.send(buffer)
                    time.sleep(1) 
                    buffer="\u200b"
            if buffer:
                await message.channel.send(buffer) 
        else:
            await message.channel.send(resposta) 
        print("Mensagem(ns) enviada(s)")
        criar_memorias_user(userid,prompt,resposta)
        print("Memorias guardadas!")
        
        
        
        
        
        
client.run(TOKEN)


