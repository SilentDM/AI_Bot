import os
# AI_PROVIDER decide, em UM ÚNICO LUGAR, qual implementação de IA o programa
# inteiro vai usar. Valores esperados: "gemini" (padrão/gratuito) ou "pro"
# (chave de outro provedor, ex: a conta paga de um amigo).
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip().lower()
# Importamos SÓ o módulo do provedor escolhido. Isso é importante porque
# cada módulo de provedor faz sua própria checagem de chave obrigatória
# no momento do import (ex: ai_gemini.py exige GOOGLE_API_KEY). Se
# importássemos os dois sempre, o programa exigiria as DUAS chaves mesmo
# quando só uma está sendo usada.
if AI_PROVIDER == "pro":
    from core.ai_pro import ask_ai as _ask_ai_impl
else:
    from core.ai_gemini import ask_ai as _ask_ai_impl




def ask_ai(contents=None, system_instruction=None, temperature=None, response_schema=None, use_world_context=True):
    """
    Ponto único de entrada para QUALQUER parte do programa que precise
    perguntar algo para a IA (memory.py, wbuilder.py, expander.py, dbot.py, gui.py).

    Quem chama esta função não precisa saber (e não deveria precisar saber)
    qual provedor está ativo no momento — Gemini gratuito ou a IA "Pro".
    Se um dia você quiser trocar de provedor, ou adicionar um terceiro,
    a mudança acontece SÓ aqui em cima, no bloco de import. Nenhum outro
    arquivo do projeto precisa ser tocado.
    """
    return _ask_ai_impl(
        contents=contents,
        system_instruction=system_instruction,
        temperature=temperature,
        response_schema=response_schema,
        use_world_context=use_world_context
    )