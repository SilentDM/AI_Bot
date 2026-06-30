import unicodedata, re
from distro import info
import Main_def as md
import discord
import os
import requests

prompt = "Cosmologia e Phaeton"
info = md.gerar_info(prompt)
print(f"Informações geradas:\n{info}")