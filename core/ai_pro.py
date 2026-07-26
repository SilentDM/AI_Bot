# Exemplo básico para ai_pro.py usando OpenAI
import os
from openai import OpenAI

PRO_API_KEY = os.getenv("PRO_API_KEY")
client = OpenAI(api_key=PRO_API_KEY) if PRO_API_KEY else None

def ask_ai(contents, system_instruction=None, temperature=0.7, response_schema=None, **kwargs):
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