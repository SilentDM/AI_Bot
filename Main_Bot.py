from email.mime import message
import unicodedata, re
from unittest import result
from distro import info
from sympy import true
import Main_def as md
import discord
import os
import requests
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def gerar_resposta_kobold(prompt, extra, info, persona, regras):
    url = "http://localhost:5001/api/v1/generate"
    contexto = f"""
    <|im_start|>system{persona}{regras}<|im_end|>
    Informations: {info}
    <|im_start|>User:{prompt}{extra}<|im_end|>
    <|im_start|>assistant:<|im_end|>
    """
    data = {"prompt": contexto,       
    "max_length": 256,
    "temperature": 0.5,
    "top_p": 0.9,
    "rep_pen": 1.1,
    "stop_sequence": ["User:", "Assistant:", "USER:", "ASSISTANT:", "<|im_end|>"]}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"\nResultado completo do Kobold:\n{result}")
        return result["results"][0]["text"].strip()
    else:
        return "Me desculpe, mortal, no momento estou ocupado com outros afazeres cósmicos!"

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
        promptfix = md.normalize_text(prompt)
        persona = """[Personalidade]\nVocê é Ao, o sobredeus, criador do universo. Responda com gentileza, mas como um ser imensamente poderoso falando com suas criações: com bondade, proteção — e ainda assim um pouco de arrogância, pois você é o criador do universo. Você é um ser de grande sabedoria e discernimento, e está sempre disposto a compartilhar seu conhecimento com aqueles que o buscam.Sempre se refira a Ao em primeira pessoa."""
        regras = """[REGRAS]\n- Não ofereça e não peça por mais informações;\n- Responda apenas com as informações fornecidas;\n- Dê respostas de no máximo dois parágrafos;\n- Responda de forma clara e concisa;"""
        
        if not md.kobold_online():
            await message.channel.send("Me desculpe, mortal, no momento estou ocupado com outros afazeres cósmicos!")
            return
        info = md.gerar_info(promptfix)     
        extra = md.detectar_intencao(prompt)   
        resposta = gerar_resposta_kobold(prompt,extra, info, persona, regras)
        resposta = md.trim_incomplete_sentences(resposta)
        await message.channel.send(resposta[:1900])
        
client.run(TOKEN)


