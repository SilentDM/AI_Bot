import os
import asyncio
from ai_utils import ask_ai
import memory
import project_utils as pu
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_ENABLED = bool(TOKEN)

if DISCORD_ENABLED:
    import discord
    intents = discord.Intents.default()
    intents.message_content = True
    discordclient = discord.Client(intents=intents)
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
            
            extra = pu.detectar_intencao(prompt)   
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
            conteudo_input = ""
            
            if memorias:
                conteudo_input += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
                
            # Adiciona a mensagem atual do usuário com o nome dele para personalização
            conteudo_input += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"
            
            if extra:
                conteudo_input += f" {extra}\n"
            
            # 3. Chamando o novo ask_ai
            # Definimos a temperatura em 0.65 para permitir flexibilidade sem quebrar as regras.
            try:
                resposta = ask_ai(
                    contents=conteudo_input,
                    system_instruction=instrucao_sistema,
                    temperature=0.65,
                    use_world_context=True
                )
            except Exception as e:
                print(f"Erro ao processar: {e}")
                resposta = "Me perdoe, mortal, estou ocupado com outros afazeres cósmicos!"
                
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
                            
                            await asyncio.sleep(2) 
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
                memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta)
                print("Memórias atualizadas com sucesso!")
            else:
                print("Não foi possível processar a resposta do modelo.")
else:
    # discordclient fica como None quando não há token, para que qualquer
    # tentativa acidental de uso sem checar DISCORD_ENABLED primeiro falhe
    # de forma clara (AttributeError em None) em vez de silenciosamente.
    discordclient = None
    print("DISCORD_TOKEN não configurado — o bot do Discord está desativado.")

if __name__ == "__main__":
    discordclient.run(TOKEN)
    