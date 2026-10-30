import os
import uuid
from openai import OpenAI

# 1. Genera un ID de sesión único para esta conversación.
#    Debe mantenerse igual durante toda la conversación.
session_id = str(uuid.uuid4())

# 2. Crea el cliente con la cabecera que exige OpenCode Go
client = OpenAI(
    base_url="https://opencode.ai/zen/go/v1",
    api_key="",
    default_headers={"x-opencode-session": session_id},
)

def chat():
    print(f"Chat con OpenCode Go (escribe 'salir' para terminar)")
    print(f"Sesión: {session_id[:8]}...")
    messages = [
        {"role": "system", "content": "Eres un asistente útil y amigable."}
    ]

    while True:
        user_input = input("\nTú: ")
        if user_input.lower() == 'salir':
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model="deepseek-v4.1-flash",
                messages=messages,
                temperature=0.7,
            )

            assistant_reply = response.choices[0].message.content
            print(f"\nAsistente: {assistant_reply}")
            messages.append({"role": "assistant", "content": assistant_reply})

        except Exception as e:
            print(f"\nError: {e}")
            if messages[-1]["role"] == "user":
                messages.pop()

if __name__ == "__main__":
    chat()