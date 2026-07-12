from email.mime import message
import unicodedata, re
from unittest import result
from distro import info
from sympy import true
import discord, os, requests, time, traceback, sys
import tiktoken
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY, transport='rest') # transport='rest' ajuda em alguns ambientes
model = genai.GenerativeModel('gemini-2.5-flash')




