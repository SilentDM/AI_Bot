import os, asyncio, time
import core.ai_utils as au
import core.memory as memory
import engine.project_utils as pu
import ui.settings as st
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MESTRE_DISCORD_ID = int(os.getenv("MESTRE_DISCORD_ID") or "0")
DISCORD_ENABLED = bool(TOKEN)

# Dicionários de controle de tempo e presença
USER_COOLDOWNS = {}
ULTIMO_STATUS_PRESENCA = None

def obter_token_atual():
    return os.getenv("DISCORD_TOKEN", "").strip()

def iniciar_bot_discord():
    token = obter_token_atual()
    if not token:
        print("DISCORD_TOKEN não configurado — o bot do Discord está desativado.")
        return False
    return True

def _parse_lista_texto(raw_str: str) -> list[str]:
    """Auxiliar para converter 'canal1; canal2, canal3' em ['canal1', 'canal2', 'canal3']."""
    if not raw_str:
        return []
    raw_str = raw_str.replace(";", ",")
    return [item.strip().lower() for item in raw_str.split(",") if item.strip()]

if DISCORD_ENABLED:
    import discord
    intents = discord.Intents.default()
    intents.message_content = True
    discordclient = discord.Client(intents=intents)

    async def atualizar_presenca_bot(prefixo):
        """Atualiza o status visível do bot no Discord de forma segura."""
        global ULTIMO_STATUS_PRESENCA
        
        # 1. Proteção: Só tenta atualizar se o bot estiver 100% conectado
        if not discordclient or not discordclient.is_ready():
            return

        projeto_atual = getattr(pu, "PASTA_PROJETO", "Projeto") or "Projeto"
        chave_atual = f"{prefixo}_{projeto_atual}"
        
        # 2. Só chama a API do Discord se o status REALMENTE mudou (evita Rate Limit)
        if ULTIMO_STATUS_PRESENCA != chave_atual:
            try:
                # Texto limpo e direto
                texto_status = f"{prefixo} | {projeto_atual}"
                
                # Tipo Ouvindo (Listening) com status Online explícito
                atividade = discord.Activity(
                    type=discord.ActivityType.listening, 
                    name=texto_status
                )
                
                await discordclient.change_presence(
                    status=discord.Status.online,
                    activity=atividade
                )
                
                ULTIMO_STATUS_PRESENCA = chave_atual
                print(f" Status do Discord atualizado: Ouvindo {texto_status}")
            except Exception as e:
                print(f"Erro ao atualizar presença do bot: {e}")
                
    async def respondersend(message, texto):
        await message.channel.send(texto) 

    async def responderreply(message, texto):
        await message.reply(texto) 

    @discordclient.event
    async def on_ready():
        print(f'Logado como {discordclient.user}')
        config = st.carregar_configuracoes()
        prefixo = config.get("discord_prefix", "!ao")
        await atualizar_presenca_bot(prefixo)

    @discordclient.event
    async def on_message(message):
        if message.author == discordclient.user:
            return
        
        config = st.carregar_configuracoes()
        prefixo = config.get("discord_prefix", "!ao").strip()
        prefixo_lower = prefixo.lower()
        
        # Garante que a presença no Discord reflete o gatilho atual
        await atualizar_presenca_bot(prefixo)

        content_lower = message.content.lower()

        # 1. VERIFICAÇÃO DO GATILHO / PREFIXO
        if content_lower.startswith(prefixo_lower):
            raw_prompt = message.content[len(prefixo):]
            if raw_prompt.startswith(",") or raw_prompt.startswith(" "):
                raw_prompt = raw_prompt.lstrip(", ")
            prompt = raw_prompt.strip()

            if not prompt:
                return

            # 2. VERIFICAÇÃO DE CANAIS PERMITIDOS E BLOQUEADOS
            channel_name = message.channel.name.lower() if hasattr(message.channel, 'name') else "dm"
            channel_id = str(message.channel.id)

            canais_permitidos = _parse_lista_texto(config.get("discord_channels_allowed", ""))
            canais_bloqueados = _parse_lista_texto(config.get("discord_channels_blocked", ""))

            # Checa Blacklist
            if canais_bloqueados:
                if channel_name in canais_bloqueados or channel_id in canais_bloqueados:
                    return  # Ignora este canal

            # Checa Whitelist (se configurada, ignora canais que não estejam na lista, exceto DMs)
            if canais_permitidos and channel_name != "dm":
                if channel_name not in canais_permitidos and channel_id not in canais_permitidos:
                    return  # Ignora se não estiver na lista permitida

            # 3. VERIFICAÇÃO DE COOLDOWN POR USUÁRIO
            userid = message.author.id
            tempo_cooldown = int(config.get("discord_cooldown_seconds", 5))
            agora = time.time()
            ultimo_envio = USER_COOLDOWNS.get(userid, 0)

            if agora - ultimo_envio < tempo_cooldown:
                # Usuário em cooldown: ignora a mensagem para evitar spam
                return
            USER_COOLDOWNS[userid] = agora

            # 4. VERIFICAÇÃO DE PERMISSÃO DE MESTRE (IS_DM)
            user_name = message.author.name
            guild_id = message.guild.id if message.guild else "dm"
            guild_name = message.guild.name if message.guild else "DM"
            
            cargos_mestre = _parse_lista_texto(config.get("discord_roles_dm", "Mestre, DM, GM"))
            eh_mestre = (userid == MESTRE_DISCORD_ID) or isinstance(message.channel, discord.DMChannel)

            if not eh_mestre and hasattr(message.author, "roles"):
                cargos_usuario = [r.name.lower() for r in message.author.roles]
                if any(cargo in cargos_usuario for cargo in cargos_mestre):
                    eh_mestre = True

            # 5. INSTRUÇÃO DO SISTEMA
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
            instrucao_sistema = f"{persona}\n\n{regras}"
            
            extra = pu.detectar_intencao(prompt)   
            memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)
            
            conteudo_input = ""
            if memorias:
                conteudo_input += f"--- HISTÓRICO RECENTE DE CONVERSAS ---\n{memorias}\n\n"
            conteudo_input += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"
            if extra:
                conteudo_input += f" {extra}\n"
            
            # 6. CHAMADA DA IA PASSANDO A FLAG IS_DM
            try:
                resposta = await asyncio.to_thread(
                    au.ask_ai,
                    contents=conteudo_input,
                    system_instruction=instrucao_sistema,
                    temperature=0.65,
                    use_world_context=True,
                    is_dm=eh_mestre  # 🟢 Define se carrega o bundle Full ou Player
                )
            except Exception as e:
                print(f"Erro ao processar: {e}")
                resposta = ("Me perdoe, mortal, estou ocupado com outros afazeres cósmicos!")
                
            if resposta:
                finalz = [".", "!", "?"]
                if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
                    resposta = memory.trim_incomplete_sentences(resposta)
                
                if len(resposta) > 1900:
                    chunks = []
                    texto_restante = resposta
                    while len(texto_restante) > 1800:
                        ponto_corte = texto_restante.rfind('\n', 0, 1800)
                        if ponto_corte == -1:
                            ponto_corte = 1800
                        chunks.append(texto_restante[:ponto_corte])
                        texto_restante = texto_restante[ponto_corte:].lstrip()
                    if texto_restante:
                        chunks.append(texto_restante)

                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await responderreply(message, chunk)
                        else:
                            await respondersend(message, chunk)
                        await asyncio.sleep(1.5)
                else:
                    await responderreply(message, resposta)
                
                memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta)

else:
    discordclient = None
    print("DISCORD_TOKEN não configurado — o bot do Discord está desativado.")

if __name__ == "__main__":
    discordclient.run(TOKEN)