from email.mime import message
import unicodedata, re
from unittest import result
from distro import info
from sympy import true
import Main_def as md
import discord, os, requests, time, traceback, sys
import tiktoken
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai

TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY, transport='rest') # transport='rest' ajuda em alguns ambientes
model = genai.GenerativeModel('gemini-2.5-flash')
enc = tiktoken.get_encoding("cl100k_base")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def gerar_resposta_google(prompt, extra, info, persona, regras, memorias):
    instrucao_sistema = f"{persona}\n{regras}\nMemorias Relevantes: {memorias}\nInformations: {info}"
    corpo_usuario = f"{prompt}\n{extra}"
    generation_config = {
        "temperature": 0.5,
        "top_p": 0.9,
        "max_output_tokens": 2048 # Equivalente ao seu max_length        
    }
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", # Ou "gemini-1.5-pro"
        system_instruction=instrucao_sistema,
        generation_config=generation_config
    )
    print("Modelo configurado, pronto para gerar resposta.")

    try:
        response = model.generate_content(corpo_usuario, generation_config=generation_config)
        for candidate in response.candidates:
            termino=candidate.finish_reason
            match termino:
                case 1:
                    print("A IA achou que terminou ou encontrou uma Stop Sequence.")
                case 2:
                    print("A resposta foi cortada porque atingiu o max_output_tokens. Solução: Aumente o limite.")
                case 3:
                    print("A resposta foi cortada porque o modelo começou a gerar algo que viola os filtros de segurança.")    
        
        return response.text
    except Exception as e:
        print("\n--- 🛑 ERRO DETECTADO ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem:{e}")


def gerar_resposta_kobold(prompt, extra, info, persona, regras, memorias):
    url = "http://localhost:5001/api/v1/generate"
    contexto = f"""
    <|im_start|>system{persona}\n{regras}\n Memorias Relevantes:{memorias}<|im_end|>
    Informations: {info}\n
    <|im_start|>User:{prompt}\n{extra}\n<|im_end|>
    <|im_start|>assistant:<|im_end|>
    """
    data = {"prompt": contexto,       
    "max_length": 256,
    "temperature": 0.5,
    "top_p": 0.9,
    "rep_pen": 1.1,
    "stop_sequence": ["User:", "Assistant:", "USER:", "ASSISTANT:", "<|im_end|>", "\n<|im_start|>"]}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"\nResultado completo do Kobold:\n{result}")
        return result["results"][0]["text"].strip()
    else:
        return "Me desculpe, mortal, no momento estou ocupado com outros afazeres cósmicos!"

def criar_memorias_user(userid, resposta):
        arquivo = f"memorias_{userid}.txt"
        if os.path.exists(arquivo):
                ultima_mod = os.path.getmtime(arquivo)
                idade_horas = (time.time() - ultima_mod) / 3600
                if idade_horas > 18:
                    print(f"Memória do usuário {userid} tem mais de 18 horas. Recomeçando memória!")        
                    os.remove(arquivo)
        
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(resposta + "\n")
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        tamanho = len(enc.encode(conteudo))
        print (f"Tamanho da memória do usuário {userid}: {tamanho} tokens")
        if tamanho > 2048: #8 mensagens de 256 tokens
            print(f"Memória do usuário {userid} excedeu tamanho máximo. Criando resumo...")
            resumo = criar_resumo(conteudo)
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(resumo + "\n")
            
        
def carregarmemorias_userid(userid):
    try:
        with open(f"memorias_{userid}.txt", "r", encoding="utf-8") as f:
            memorias = f.read()
            return memorias
    except FileNotFoundError:
        return ""

def criar_resumo(prompt, resposta=""):
    resumo = ""
    url = "http://localhost:5001/api/v1/generate"
    contexto = f"""
    <|im_start|>system:[Personalidade]\nVocê é um assistente especializado em resumir informações em uma única frase, simples e direta. Explicando o que o usuário deseja entender e qual resposta foi dada a ele.
    <|im_start|>User:\nPergunta:{prompt}\nResposta:{resposta}\n
    <|im_start|>assistant:\n<|im_end|>
    """
    data = {"prompt": contexto,       
    "max_length": 256,
    "temperature": 0.5,
    "top_p": 0.9,
    "rep_pen": 1.1,
    "stop_sequence": ["User:", "Assistant:", "USER:", "ASSISTANT:", "<|im_end|>", "\n<|im_start|>"]}
    resumo = requests.post(url, json=data)
    if resumo.status_code == 200:
        resumo = resumo.json()
        print(f"\nResultado completo do Kobold:\n{resumo}")
        return resumo["results"][0]["text"].strip()
    return resumo

@client.event
async def on_ready():
    print(f'Logado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content.lower().startswith("!ao"):
        prompt = message.content.replace("!Ao ", "")
        prompt = message.content.replace(",", "",1)
        userid = message.author.id
        memorias=""
        promptfix = md.normalize_text(prompt)
        persona = """[Personalidade]\nVocê é Ao, o criador do universo. Está aqui para responder dúvidas, com gentileza e sabedoria. Você é um ser de grande sabedoria e discernimento, e está sempre disposto a compartilhar seu conhecimento com aqueles que o buscam. Sempre se refira a Ao em primeira pessoa."""
        regras = """[REGRAS]\n- Não ofereça e não peça por mais informações;\n- Responda apenas com as informações fornecidas;\n- Dê respostas de no máximo dois parágrafos;\n- Responda de forma clara e concisa;"""
        
        if not md.kobold_online():
            await message.channel.send("Me desculpe, mortal, no momento estou ocupado com outros afazeres cósmicos!")
            return
        info = md.gerar_info(promptfix)     
        extra = md.detectar_intencao(prompt)   
        memorias = carregarmemorias_userid(userid)
        #resposta = gerar_resposta_kobold(prompt,extra, info, persona, regras, memorias)
        resposta = gerar_resposta_google(prompt,extra, info, persona, regras, memorias)
        #resposta = md.trim_incomplete_sentences(resposta)
        await message.channel.send(resposta[:1900])
        #resumo = criar_resumo(prompt, resposta)
        criar_memorias_user(userid, resposta)
        
        
        
        
client.run(TOKEN)


