import traceback

import requests
from django.conf import settings


def clean_number_whatsapp(number: str) -> str:
    try:
        if not number:
            return ""
        # remover sufixos comuns de JID
        for suffix in ["@s.whatsapp.net", "@c.us", "@lid", "@g.us"]:
            if number.endswith(suffix):
                number = number.replace(suffix, "")
        # manter apenas dígitos
        number = "".join(filter(str.isdigit, number))
        return number
    except Exception:
        traceback.print_exc()
        return ""

def transcribe_audio_from_bytes(audio_bytes: bytes, language="pt-BR") -> str:
    """
    Transcribe audio (in bytes) using Deepgram and return the text.
    """
    deepgram_key = getattr(settings, 'DEEPGRAM_API_KEY', None)
    if not deepgram_key:
        print("DEEPGRAM_API_KEY not configured")
        return "Áudio recebido (transcrição não disponível)"
    
    url = "https://api.deepgram.com/v1/listen"

    headers = {
        "Authorization": f"Token {deepgram_key}",
        "Content-Type": "audio/ogg"  # important for Deepgram to understand the format
    }

    params = {
        "model": "nova-2",
        "language": language,
        "punctuate": "true",
        "smart_format": "true",
    }

    try:
        response = requests.post(url, headers=headers, params=params, data=audio_bytes)
        
        if response.status_code != 200:
            print(f"Deepgram error: {response.status_code}, {response.text}")
            return "Erro na transcrição do áudio"

        result = response.json()
        transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
        
        return transcript if transcript.strip() else "Áudio sem conteúdo detectável"
        
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return "Erro na transcrição do áudio"