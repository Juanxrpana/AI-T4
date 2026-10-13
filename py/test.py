import requests
var = requests.post("http://127.0.0.1:8000/pregunta_ia", json={"prompt": "hola si tuviera diarrea que dirías?"})
print("hola soy omelo chino")
print(var.text)