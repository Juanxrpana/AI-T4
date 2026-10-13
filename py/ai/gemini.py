import os
from google import genai
from google.genai import types
from ai.base import APIplataform


class Gemini(APIplataform):

    def __init__(self, api_key: str, guia: str = None):
        self.client = genai.Client(api_key = api_key)
        doctor_function = {
            "name": "componente_inteligente",
            "description": guia,
            "parameters": {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "Infomración puntual, corta, especifica, concisa, y sin embelesamiento, completamente medica y en españoll",
                    },
                },
                #"required": ["location"],
            },
        }

        tools = types.Tool(function_declarations=[doctor_function])
        self.config = types.GenerateContentConfig(tools=[tools])


        self.api_key = api_key
        self.guia = guia
    
      
        #self.model = genai.GenerativeModel("gemini-3.5-flash")

    def chat(self, prompt: str) -> str:

       #response = self.model.generate_content(prompt)
        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=self.config,)

        
        r = response.candidates[0].content.parts[0].function_call.args["response"]
        return {"response": r}