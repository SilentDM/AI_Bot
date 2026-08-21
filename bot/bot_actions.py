import discord, asyncio
import core.ai_utils as au
import core.memory as memory
import engine.project_utils as pu


def _parse_lista_texto(raw_str: str) -> list[str]:
    if not raw_str:
        return []
    raw_str = raw_str.replace(";", ",")
    return [item.strip().lower() for item in raw_str.split(",") if item.strip()]


def verificar_permissao_mestre(message, config: dict, mestre_id: int) -> bool:
    userid = message.author.id
    user_name = message.author.name

    if userid == mestre_id and mestre_id != 0:
        print(f"👑 [DISCORD-TRACE] Permissão para '{user_name}': 👑 MESTRE SUPREMO (ID no .env).")
        return True

    cargos_mestre = _parse_lista_texto(config.get("discord_roles_dm", "Mestre, DM, GM"))
    if hasattr(message.author, "roles"):
        cargos_usuario = [r.name.lower() for r in message.author.roles]
        if any(cargo in cargos_usuario for cargo in cargos_mestre):
            print(f"👑 [DISCORD-TRACE] Permissão para '{user_name}': 👑 MESTRE (Cargo no Servidor).")
            return True

    print(f"📜 [DISCORD-TRACE] Permissão para '{user_name}': 📜 JOGADOR (Lore Pública).")
    return False


async def processar_mensagem_ia(prompt: str, eh_mestre: bool, user_name: str, guild_id: str, guild_name: str, userid: str) -> str:
    persona = (
        "[Personalidade]\n"
        "- Você é Ao, o criador do universo de RPG. Responda com sabedoria, mistério e gentileza.\n"
        "- Evite comentar assuntos descritos como segredos para jogadores comuns.\n"
    )
    regras = (
        "[REGRAS E LINKS DE REFERÊNCIA]\n"
        "- Responda de forma clara, concisa e imersiva;\n"
        "- Não altere informações já definidas no universo;\n"
        "- JAMAIS mencione nomes de arquivos de texto como 'regraslocais.md' ou pastas de computador.\n"
        "- REGRA OBRIGATÓRIA DE LINK: Se a resposta utilizar regras ou registros do servidor que possuem um link '🔗 [Ver no Discord](URL)', INCLUA o link no final da sua explicação.\n\n"
        "[EXEMPLO OBRIGATÓRIO]\n"
        "Pergunta: Como funcionam as poções de cura?\n"
        "Resposta: As poções de cura exigem Ação Bônus e curam os dados + Mod de Constituição + Nível do personagem.\n"
        "🔗 [Ver no Discord](https://discord.com/channels/715118508916080713/1438017916573323264/1438021543694176257)\n"
    )
    instrucao_sistema = f"{persona}\n\n{regras}"

    extra = pu.detectar_intencao(prompt)
    if extra:
        print(f"🎯 [DISCORD-TRACE] Intenção detectada: '{extra}'")

    conhecimento_discord = pu.carregar_conhecimento_discord(guild_id=guild_id)
    len_know = len(conhecimento_discord) if conhecimento_discord else 0
    print(f"📚 [DISCORD-TRACE] Registros do servidor carregados ({len_know:,} caracteres).")

    memorias = memory.carregar_memorias(guild_id, guild_name, userid, user_name)
    len_mem = len(memorias) if memorias else 0
    print(f"🧠 [DISCORD-TRACE] Histórico recente de memórias carregado ({len_mem:,} caracteres).")

    conteudo_input = ""
    if conhecimento_discord:
        conteudo_input += f"--- REGISTROS DO SERVIDOR DISCORD ---\n{conhecimento_discord}\n\n"

    if memorias:
        conteudo_input += f"--- HISTÓRICO RECENTE ---\n{memorias}\n\n"

    conteudo_input += f"--- MENSAGEM DO USUÁRIO ({user_name}) ---\n{prompt}"
    if extra:
        conteudo_input += f" {extra}\n"

    print(f"🤖 [DISCORD-TRACE] Enviando requisição para a IA (is_dm={eh_mestre})... Aguardando resposta...")
    try:
        resposta = await asyncio.to_thread(
            au.ask_ai,
            contents=conteudo_input,
            system_instruction=instrucao_sistema,
            temperature=0.65,
            use_world_context=True,
            is_dm=eh_mestre
        )
    except Exception as e:
        print(f"❌ [DISCORD-TRACE] Erro durante chamada da IA: {e}")
        resposta = "Me perdoe, mortal. Estou ocupado ajustando as estrelas do cosmos!"

    if resposta:
        len_resp = len(resposta)
        print(f"✅ [DISCORD-TRACE] Resposta recebida da IA ({len_resp:,} caracteres).")

        finalz = [".", "!", "?"]
        if resposta.rstrip() and resposta.rstrip()[-1] not in finalz:
            resposta = memory.trim_incomplete_sentences(resposta)

        memory.salvar_memoria(guild_id, guild_name, userid, user_name, prompt, resposta)
        print(f"💾 [DISCORD-TRACE] Interação salva na memória do usuário '{user_name}'.")

    return resposta or ""


def criar_embed_resposta(texto_chunk: str, eh_mestre: bool, idx: int, total_chunks: int) -> discord.Embed:
    embed = discord.Embed(
        description=texto_chunk,
        color=0x10b981 if eh_mestre else 0x3b82f6
    )
    if idx == 0:
        embed.set_author(name="🌌 Ao - O Criador do Universo")
        acesso_txt = "👑 Mestre (Lore Completa)" if eh_mestre else "📜 Jogador (Lore Pública)"
        embed.set_footer(text=f"Acesso: {acesso_txt}")
    return embed


def criar_embed_help() -> discord.Embed:
    embed = discord.Embed(
        title="🌌 Ao - Guia de Comandos e Ajuda",
        description="Eu sou Ao, o criador do universo de RPG. Aqui estão as instruções nos canais do servidor:",
        color=0x10b981
    )
    embed.add_field(
        name="📜 Dúvidas de Lore e Regras",
        value="Envie mensagens nos canais autorizados usando o prefixo (ex: `!ao O que é a Catedral de Prata?`).",
        inline=False
    )
    embed.add_field(
        name="🎲 Rolagem de Dados",
        value="Use `!r 1d20+5`, `!rolar 2d6+3` ou `!r 2d20kh1+3` para rolar dados.",
        inline=False
    )
    embed.add_field(
        name="🔄 Sincronização do Mestre",
        value="Mestres podem usar `!ao sincronizar` para atualizar as regras e crônicas lidas pelo Bot.",
        inline=False
    )
    embed.set_footer(text="Silent Multiverse Nexus Console")
    return embed