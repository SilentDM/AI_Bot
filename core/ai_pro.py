import os
from openai import OpenAI

def get_pro_client():
    key = os.getenv("PRO_API_KEY", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)

def ask_ai(contents, system_instruction=None, temperature=0.7, response_schema=None, **kwargs):
    client = get_pro_client()
    if not client:
        return "❌ Nenhuma chave Pro (PRO_API_KEY) configurada. Acesse a aba 'Opções' para cadastrar sua chave."

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": str(contents)})
    
    kwargs_call = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
    }
    if response_schema:
        kwargs_call["response_format"] = response_schema

    response = client.beta.chat.completions.parse(**kwargs_call)
    return response.choices[0].message.content