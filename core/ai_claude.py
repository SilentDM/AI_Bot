import os
from typing import Any, Optional, Type
from pydantic import BaseModel
import anthropic
import engine.project_utils as pu

# Modelo padrão usado nas chamadas da API do Claude.
# Pode ser sobrescrito via variável de ambiente CLAUDE_MODEL, caso queira
# trocar para outro modelo (ex: um mais rápido/barato) sem editar o código.
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5").strip()
MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.6
DEFAULT_SYSTEM_INSTRUCTION = "You are a helpful assistant that explains things and creates what is requested."
DEFAULT_CONTENTS = "Please repeat: I did not receive a correct prompt, your coding has failed somewhere."


def get_claude_client():
    """Obtém o cliente Claude atualizado dinamicamente com base nas variáveis de ambiente."""
    api_key = os.getenv("CLAUDE_TOKEN", "").strip()
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _montar_contexto_mundo(is_dm: bool = True) -> str:
    """
    Monta o mesmo 'bundle' de conhecimento do projeto usado pelo Gemini
    (estrutura de pastas + índice + conteúdo filtrado por permissão),
    porém enviado diretamente no system prompt, já que a API do Claude
    não usa Files API / Context Cache explícito da mesma forma do Gemini.
    """
    try:
        return (
            pu.carregar_estrutura_projeto() + "\n\n" +
            pu.gerar_indice() + "\n\n" +
            pu.carregar_projeto(is_dm=is_dm)
        )
    except Exception as e:
        print(f"⚠️ Erro ao montar contexto do mundo para o Claude: {e}")
        return ""


def ask_ai(
    contents: Any = None,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None,
    use_world_context: Optional[bool] = True,
    is_dm: Optional[bool] = True,
    **kwargs
) -> str:
    """
    Ponto de entrada equivalente ao ask_ai() do ai_gemini.py e ai_pro.py.
    Usado automaticamente por core/ai_utils.py quando AI_PROVIDER=claude.
    """
    client = get_claude_client()
    if not client:
        return "❌ Nenhuma chave da API Claude (CLAUDE_TOKEN) foi configurada. Acesse a aba 'Opções' para cadastrar sua chave."

    if not system_instruction:
        system_instruction = DEFAULT_SYSTEM_INSTRUCTION
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if contents is None:
        contents = DEFAULT_CONTENTS

    # O system prompt do Claude aceita uma lista de blocos de texto.
    # Colocamos o contexto do mundo em um bloco separado com cache_control
    # para que chamadas seguidas dentro da janela de cache (~5 min) não
    # precisem reprocessar o bundle inteiro do projeto a cada pergunta.
    system_blocks = [
        {"type": "text", "text": system_instruction}
    ]

    if use_world_context:
        contexto_mundo = _montar_contexto_mundo(is_dm=is_dm)
        if contexto_mundo:
            system_blocks.append({
                "type": "text",
                "text": f"### CONTEXTO COMPLETO DO PROJETO (MUNDO) ###\n{contexto_mundo}",
                "cache_control": {"type": "ephemeral"}
            })

    if response_schema:
        try:
            schema_json = response_schema.model_json_schema()
        except Exception:
            schema_json = None
        if schema_json:
            system_blocks.append({
                "type": "text",
                "text": (
                    "Você DEVE responder APENAS com um JSON válido, sem comentários, "
                    "sem markdown (` ```json `) e sem nenhum texto fora do JSON, seguindo "
                    f"rigorosamente este schema:\n{schema_json}"
                )
            })

    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=system_blocks,
            messages=[
                {"role": "user", "content": str(contents)}
            ]
        )
    except anthropic.APIStatusError as e:
        print(f"❌ Erro na chamada da API Claude ({e.status_code}): {e}")
        return f"❌ Erro ao consultar a IA Claude ({e.status_code}): {e}"
    except Exception as e:
        print(f"❌ Erro inesperado na chamada da API Claude: {e}")
        return f"❌ Erro ao consultar a IA Claude: {e}"

    texto_partes = [
        bloco.text for bloco in response.content
        if getattr(bloco, "type", "") == "text"
    ]
    return "".join(texto_partes).strip()