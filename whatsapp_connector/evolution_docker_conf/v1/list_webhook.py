import requests

url = "http://127.0.0.1:8081/webhook/find/allan"

headers = {
    "apikey": "1234",
}

response = requests.request("GET", url, headers=headers)

print(response.text)