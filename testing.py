from email.mime import message
import unicodedata, re
from unittest import result
from distro import info
from sympy import true
import Main_def as md
import discord, os, requests, time, traceback, sys
import tiktoken
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY, transport='rest') # transport='rest' ajuda em alguns ambientes
model = genai.GenerativeModel('gemini-2.5-flash')

print("Modelos disponíveis para você:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
