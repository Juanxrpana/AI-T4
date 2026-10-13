import os
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from prueba import router as router_prueba
from ai.gemini import Gemini


# --- FastAPI Configuration ---
app = FastAPI()

# --- Load Environment Variables ---
load_dotenv() 

# --- AI Configuration ---
def load_guia():
    try:
        with open("prompts/guia.md", "r") as f:
            return f.read()
    except FileNotFoundError:
        return None
 
app.include_router(router_prueba, tags=["Prueba"])

guia = load_guia()
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY no fue seteada.")

#mezcla de la configuración de la IA
ai_platform = Gemini(api_key=gemini_api_key, guia=guia)

class ChatRequest(BaseModel):
    prompt: str #esto deberia tomar la pregunta q se enviará, en json obligado

class ChatResponse(BaseModel):
    response: str #esto es como deberia devolver la respuesta, en json obligado



@app.get("/") 
async def read_root():
    return {"message:": "Hello World u gonna die, la ia es la que la ia"}

@app.post("/pregunta_ia")
async def pregunta_ia(request: ChatRequest):
    response_text = ai_platform.chat(request.prompt) #aqui se llama a la función chat de la plataforma de IA, pasando el prompt recibido en la solicitud    
    return response_text #se devuelve la respuesta obtenida de la IA como respuesta a la solicitud HTTP

