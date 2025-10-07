import requests

import base64

with open("star-wars.jpg", "rb") as image_file:
    image_data = image_file.read()
    base64_string = base64.b64encode(image_data).decode('utf-8')

url = "http://127.0.0.1:8081/message/sendMedia/allan"



# Novo payload corrigido
payload = {
    "number": "+55 83 999330465",
    "mediatype": "image",  # <- Fora de mediaMessage
    "media": base64_string,  # <- Fora de mediaMessage
    "fileName": "evolution-api.jpeg",
    "caption": "Enviado via python backend",
    "options": {
        "delay": 123,
        "presence": "composing"
    }
}

headers = {
    "apikey": "1234",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)
