import requests

url = "http://127.0.0.1:8081/message/sendText/allan"

payload = {
    "number": "+55 83 9933-0465",
    "textMessage": {"text": "Teste enviando via python"}
}
headers = {
    "apikey": "1234",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)