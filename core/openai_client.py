# core/openai_client.py
import os
from openai import OpenAI

"""
Cliente unificado para Groq (endpoint compatible con OpenAI) u OpenAI oficial.
Priorizamos GROQ_API_KEY + https://api.groq.com/openai/v1
Si no hay GROQ_API_KEY, intentamos con OPENAI_API_KEY (OpenAI).
"""

def get_openai_client():
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No hay GROQ_API_KEY ni OPENAI_API_KEY configurada")

    # Si usas Groq (por defecto)
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    return OpenAI(api_key=api_key, base_url=base_url)
