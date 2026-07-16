import os
import re
import json
import asyncio
import discord
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Import our custom memory manager
import memory

load_dotenv()

CHANNEL_ID = 1519013814039871632
TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
modelo = "gemini-2.5-flash"

intents = discord.Intents.default()
intents.message_content = True
discordclient = discord.Client(intents=intents)
geminiclient = genai.Client(api_key=GOOGLE_API_KEY)

# Target variations for identifying pending to-do segments
TAG_ALVO = [
    "<-- TO DO:", "<-- TO DO", "<-- TODO:", "<-- TODO", "<-- todo",
    "<-- To do:", "<-- to-do:", "<-- to-do", "<-- to do:", "<-- to do",
    "<-- To Do:", "<-- To Do", "<-- To-Do:", "<-- To-Do", "<-- To-do:", 
    "<-- To-do", "<-- Todo:"
]

def gerar_resposta_google(prompt, extra, info, persona, regras, memorias):
    instrucao_sistema = f"{persona}\n{regras}\nMemorias Relevantes: {memorias}\nInformations: {info}\n"
    corpo_usuario = f"{prompt}\n{extra}"
    prompt_final = f"{instrucao_sistema}\n{corpo_usuario}"
    config = types.GenerateContentConfig(
        system_instruction=instrucao_sistema,
        temperature=0.5,
        top_p=0.9,
        max_output_tokens=20480,
        tools=[
            types.Tool(
                google_search=types.GoogleSearch()
            )
        ]
    )
    try:
        
        response = geminiclient.models.generate_content(
            model=modelo,
            contents=corpo_usuario,
            config=config
        )
        with open("resposta.json", "w", encoding="utf-8") as f:
            f.write(response.model_dump_json(indent=2))
        with open("ultimoprompt.txt", "w", encoding="utf-8") as f: 
            f.write(prompt_final)
        
        return response.text
    except Exception as e:
        print("\n--- 🛑 ERRO NO MODELO ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem: {e}")
        return None

def carregar_phaeton():
    """
    Crawls the 'Phaeton' folder dynamically.
    1. Tracks only the latest revision of each markdown file (e.g. history_v2 over history_v1 or history).
    2. Excludes any file containing unresolved TODO tags.
    3. Merges the content to form the background knowledge payload.
    """
    pasta_phaeton = Path(os.getcwd()) / "Phaeton"
    if not pasta_phaeton.exists():
        print(f"⚠️ Alerta: Pasta '{pasta_phaeton}' não encontrada.")
        return ""
    
    # Retrieve all Markdown files recursively
    all_files = list(pasta_phaeton.rglob("*.md"))
    
    # Group files by parent directory and base name (ignoring version suffixes like _v1, _v2)
    groups = {}
    for f in all_files:
        base_name = re.sub(r'_v\d+$', '', f.stem)
        key = (f.parent, base_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(f)
        
    # Isolate the highest available version of each document
    latest_files = []
    for key, files in groups.items():
        def get_version(path):
            match = re.search(r'_v(\d+)$', path.stem)
            return int(match.group(1)) if match else 0
        
        files.sort(key=get_version, reverse=True)
        latest_files.append(files[0]) # Newest/expanded revision goes first

    conteudo_total = []
    for f_path in latest_files:
        try:
            with open(f_path, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
        except UnicodeDecodeError:
            try:
                with open(f_path, "r", encoding="latin1") as file_obj:
                    content = file_obj.read()
            except Exception:
                continue
        
        # Verify if the file is clean of TODO markers
        if any(tag in content for tag in TAG_ALVO):
            print(f"ℹ️ Excluindo '{f_path.name}' do conhecimento por possuir tags TODO.")
            continue
            
        conteudo_total.append(f"--- INÍCIO DO ARQUIVO: {f_path.name} ---\n{content}\n--- FIM DO ARQUIVO: {f_path.name} ---")
        
    return "\n\n".join(conteudo_total)

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
        
        persona = (
            "[Personalidade]\n"
            "- Você é Ao, o criador do universo. Está aqui para responder dúvidas, com gentileza e sabedoria.\n"
            "- Sempre se refira a Ao em primeira pessoa.\n"
            "- Você pode gerar e criar histórias para aqueles que desejam, mas jamais altere informações já definidas."
        )
        regras = (
            "[REGRAS]\n"
            "- Não ofereça e não peça por mais informações;\n"
            "- Responda de forma clara e concisa;\n"
            "- Não faça julgamentos de valor;\n"
            "- Pode criar histórias e lugares fictícios, mas não altere informações já definidas;\n"
        )
        
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
        
        resposta = gerar_resposta_google(prompt, extra, info, persona, regras, memorias)
        
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
            
            memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta, geminiclient)
            print("Memórias atualizadas com sucesso!")
        else:
            print("Não foi possível processar a resposta do modelo.")

if __name__ == "__main__":
    discordclient.run(TOKEN)