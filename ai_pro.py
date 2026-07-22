"""
Implementação do provedor de IA "Pro" — usa uma chave de API de terceiros
(ex: a conta paga do seu amigo) em vez do Gemini gratuito.

Este arquivo precisa expor uma função ask_ai() com a MESMA assinatura de
ai_gemini.py, para que ai_utils.py (o roteador) consiga alternar entre os
dois provedores sem que nenhum outro módulo do programa precise saber a
diferença.

⚠️ AINDA NÃO IMPLEMENTADO: falta saber qual serviço/SDK seu amigo usa
(OpenAI, Anthropic Claude, outro) para escrever a chamada real à API.
Assim que isso for definido, o corpo de ask_ai() abaixo será preenchido.
"""
import os
from typing import Any, Optional, Type
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
PRO_API_KEY = os.getenv("PRO_API_KEY")
_faltando = []
if not PRO_API_KEY:
    _faltando.append("PRO_API_KEY")
if _faltando:
    raise SystemExit(
        f"❌ Erro de configuração: variável(is) ausente(s) no .env: {', '.join(_faltando)}.\n"
        f"Verifique se o arquivo .env existe na raiz do projeto e contém essas chaves.\n"
        f"(Esta checagem só roda quando AI_PROVIDER=pro está ativo em ai_utils.py)"
    )


def ask_ai(
    contents: Any = None,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    response_schema: Optional[Type[BaseModel]] = None
) -> str:
    """
    Implementação do provedor Pro. Precisa devolver uma string de resposta,
    igual ai_gemini.ask_ai() devolve — inclusive suportando response_schema
    (saída estruturada em JSON) se o provedor escolhido permitir, já que
    wbuilder.py depende disso para o ActionPlan.
    """
    raise NotImplementedError(
        "Provedor 'pro' ainda não implementado. Defina qual API seu amigo "
        "usa (OpenAI, Anthropic, outro) para completar este arquivo."
    )