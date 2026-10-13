from abc import ABC, abstractmethod

class APIplataform(ABC):
    
    @abstractmethod
    def chat(self, prompt: str) -> str:
       #Envío de prompt para la IA y retorno de respuesta"""
        pass    