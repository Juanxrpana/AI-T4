from pydantic import BaseModel, Field
from typing import Literal


class AccionSugerida(BaseModel):
    etiqueta: str
    ruta: str
    visible: bool


class RespuestaOrientacion(BaseModel):
    """Salida estructurada de MIDI."""

    tipo_respuesta: Literal[
        "emergencia",
        "orientacion",
        "catalogo",
        "aclaracion",
        "derivar",
        "datos",
        "navegacion",
        "registro_paciente",
    ]
    mensaje: str = Field(..., description="Texto breve para la secretaria.")
    especialidad_sugerida: str | None = None
    especialidades_disponibles: list[str] = Field(default_factory=list)
    pregunta_aclaratoria: str = ""
    # Interpretación orientativa (sin diagnóstico definitivo).
    posibles_asociaciones: list[str] = Field(default_factory=list)
    a_descartar: list[str] = Field(default_factory=list)
    pruebas_sugeridas: list[str] = Field(default_factory=list)
    recomendacion: str = ""
    observacion: str = ""
    # Módulo al que navegar cuando tipo_respuesta == "navegacion".
    modulo_sugerido: str | None = None
    # Progreso del cuestionario guiado.
    pregunta_activa: str = ""
    progreso: int = 0
    informacion_recopilada: dict = Field(default_factory=dict)
    # Borrador de paciente para el tipo "registro_paciente". El navegador lo
    # confirma y llama a /Pacientes/guardarDesdeChatbot; FastAPI no escribe.
    paciente_borrador: dict | None = None
