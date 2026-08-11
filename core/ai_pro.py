import os
from typing import Any, Optional, Type
from pydantic import BaseModel
from openai import OpenAI, APIError
import engine.project_utils as pu

# Modelo padrão usado nas chamadas da API "Pro". Pode ser sobrescrito via
# variável de ambiente PRO_MODEL, sem precisar editar o código.
DEFAULT_MODEL = os.getenv("PRO_MODEL", "gpt-4o-mini").strip()
DEFAULT_TEMPERATURE = 0.7
DEFAULT_SYSTEM_INSTRUCTION = "You are a helpful assistant that explains things and creates what is requested."
DEFAULT_CONTENTS = "Please repeat: I did not receive a correct prompt, your coding has failed somewhere."


def get_pro_client():
    """Obtém o cliente Pro (OpenAI) atualizado dinamicamente com base nas variáveis de ambiente."""
    key = os.getenv("PRO_API_KEY", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)


def _montar_contexto_mundo(is_dm: bool = True) -> str:
    """
    Monta o mesmo 'bundle' de conhecimento do projeto usado pelos outros
    provedores (estrutura de pastas + índice + conteúdo filtrado por
    permissão), já que a API "Pro" não tem um mecanismo de cache/upload
    de arquivos equivalente ao Files API do Gemini.
    """
    try:
        return (
            pu.carregar_estrutura_projeto() + "\n\n" +
            pu.gerar_indice() + "\n\n" +
            pu.carregar_projeto(is_dm=is_dm)
        )
    except Exception as e:
        print(f"⚠️ Erro ao montar contexto do mundo para o Pro: {e}")
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
    Ponto de entrada equivalente ao ask_ai() do ai_gemini.py e ai_claude.py.
    Usado automaticamente por core/ai_utils.py quando AI_PROVIDER=pro.
    """
    client = get_pro_client()
    if not client:
        return "❌ Nenhuma chave Pro (PRO_API_KEY) configurada. Acesse a aba 'Opções' para cadastrar sua chave."

    if not system_instruction:
        system_instruction = DEFAULT_SYSTEM_INSTRUCTION
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if contents is None:
        contents = DEFAULT_CONTENTS

    # 🛡️ Igualando o comportamento ao Gemini/Claude: injeta o bundle do
    # mundo dentro da instrução de sistema, já que aqui não existe cache
    # de contexto do lado do provedor.
    instrucao_final = system_instruction
    if use_world_context:
        contexto_mundo = _montar_contexto_mundo(is_dm=is_dm)
        if contexto_mundo:
            instrucao_final = (
                f"{system_instruction}\n\n"
                f"### CONTEXTO COMPLETO DO PROJETO (MUNDO) ###\n{contexto_mundo}"
            )

    messages = [
        {"role": "system", "content": instrucao_final},
        {"role": "user", "content": str(contents)}
    ]

    kwargs_call = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        if response_schema:
            # Structured outputs: só usa o método .parse() quando um
            # schema Pydantic foi explicitamente pedido.
            kwargs_call["response_format"] = response_schema
            response = client.beta.chat.completions.parse(**kwargs_call)
        else:
            response = client.chat.completions.create(**kwargs_call)
    except APIError as e:
        print(f"❌ Erro na chamada da API Pro/OpenAI: {e}")
        return f"❌ Erro ao consultar a IA Pro: {e}"
    except Exception as e:
        print(f"❌ Erro inesperado na chamada da API Pro/OpenAI: {e}")
        return f"❌ Erro ao consultar a IA Pro: {e}"

    conteudo_resposta = response.choices[0].message.content
    return conteudo_resposta.strip() if conteudo_resposta else ""