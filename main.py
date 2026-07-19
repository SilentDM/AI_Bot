import os, time
import re
import json
import asyncio
import discord
from pathlib import Path
from google import genai
from google.genai import types
import memory
from PIL import Image
from ai_utils import ask_gemini
from project_utils import carregar_phaeton
from dotenv import load_dotenv
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINICLIENT = genai.Client(api_key=GOOGLE_API_KEY)

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
discordclient = discord.Client(intents=intents)

TAG_ALVO = [
    "<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo",
    "<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do",
    "<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", 
    "<-- To-do", "<-- Todo:"
]
IGNORELIST = [
    "Templates", 
    "status: rascunho"
]
def detectar_intencao(pergunta):
    pergunta_lower = pergunta.lower()
    if "onde" in pergunta_lower:
        return "Foque na localização"
    elif "quando" in pergunta_lower:
        return "Foque no histórico ou cronologia"
    elif "quem" in pergunta_lower:
        return "Foque na entidade ou pessoa"
    elif "como" in pergunta_lower:
        return "Foque no método ou processo"
    elif "por que" in pergunta_lower or "porque" in pergunta_lower:
        return "Foque na causa"
    return ""

async def respondersend(message, texto):
    await message.channel.send(texto) 

async def responderreply(message, texto):
    await message.reply(texto) 

@discordclient.event
async def on_ready():
    print(f'Logado como {discordclient.user}')

@discordclient.event
async def on_message(message):
    if message.author == discordclient.user:
        return
    
    content_lower = message.content.lower()
    if content_lower.startswith("!ao"):
        if content_lower.startswith("!ao,"):
            prompt = message.content[4:]
        elif content_lower.startswith("!ao "):
            prompt = message.content[4:]
        else:
            prompt = message.content[3:]
        
        prompt = prompt.strip()
        print(f"Mensagem recebida! {prompt}")
        
        userid = message.author.id
        user_name = message.author.name
        guild_id = message.guild.id if message.guild else "dm"
        guild_name = message.guild.name if message.guild else "DM"
        
        # 1. Definindo as instruções do sistema (Persona + Regras)
        persona = (
            "[Personalidade]\n"
            "- Você é Ao, o criador do universo. Está aqui para responder dúvidas, com gentileza e sabedoria.\n"
            "- Trate o usuário falando com você como alguém importante e que você esteja orgulhoso do interesse.\n"
            "- Evite comentar assuntos que estão descritos como segredos ou secretos.\n"
            "- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas.\n"
        )
        regras = (
            "[REGRAS]\n"
            "- Não ofereça e não peça por mais informações;\n"
            "- Responda de forma clara e concisa;\n"
            "- Não faça julgamentos de valor;\n"
            "- Pode criar histórias e lugares fictícios, mas não altere as informações já definidas;\n"
        )
        
        # O system_instruction ideal do Gemini une a persona e as regras
        instrucao_sistema = f"{persona}\n\n{regras}"
        
        # Load up-to-date Phaeton information dynamically
        info = carregar_phaeton()
        print("Info Dinâmica Carregada!")
        
        extra = detectar_intencao(prompt)   
        if extra:
            print("Intenção definida!")
        else:
            print("Nenhuma intenção detectada!")
            
        memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)
        if memorias:
            print(f"Memória Carregada para o servidor/ambiente: {guild_name}!")
        else:
            print(f"Nenhum histórico encontrado para o usuário neste servidor. Inicializando...")
        
        # 2. Reunindo tudo o que é contexto para o 'contents'
        # Estruturamos o prompt de forma clara para que o modelo diferencie o histórico dos dados de Phaeton e da mensagem atual.
        conteudo_input = ""
        
        if info:
            conteudo_input += f"--- CONTEXTO ATUAL DO MUNDO (PHAETON) ---\n{info}\n\n"
            
        if memorias:
            conteudo_input += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
            
        # Adiciona a mensagem atual do usuário com o nome dele para personalização
        conteudo_input += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"
        
        if extra:
            conteudo_input += f"\n{extra}\n"
        
        # 3. Chamando o novo ask_gemini
        # Definimos a temperatura em 0.65 para permitir flexibilidade sem quebrar as regras de Phaeton.
        resposta = ask_gemini(
            contents=conteudo_input,
            system_instruction=instrucao_sistema,
            temperature=0.65
        )

        if resposta:
            print("Resposta criada!")
            finalz = [".", "!", "?"]
            if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
                resposta = memory.trim_incomplete_sentences(resposta)
            
            if len(resposta) > 1900:
                print("Resposta muito grande!")
                paragraph = [p for p in resposta.split("\n\n") if p.strip()]
                buffer = ""
                t = 1
                for p in paragraph:
                    if buffer:
                        buffer += "\n\n" + p
                    else:
                        buffer = p
                    
                    if len(buffer) > 1300:
                        if t == 1:
                            await responderreply(message, buffer)
                            print(f"Enviei a {t}º resposta!")
                        else:
                            await respondersend(message, buffer)
                            print(f"Enviei a {t}º resposta!")
                        
                        await asyncio.sleep(1) 
                        t += 1
                        buffer = "\u200b"
                
                if buffer and buffer != "\u200b":
                    await respondersend(message, buffer)
                    print("Enviei a última resposta!")
            else:
                await responderreply(message, resposta)
                print("Resposta enviada!")
            
            # Nota: Mantenha a variável ou cliente correto dependendo de como você definiu globalmente.
            # Se você usa a variável global GEMINICLIENT da sua configuração, passe ela aqui.
            memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta, GEMINICLIENT)
            print("Memórias atualizadas com sucesso!")
        else:
            print("Não foi possível processar a resposta do modelo.")

if __name__ == "__main__":
    discordclient.run(TOKEN)