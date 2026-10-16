from pydantic import BaseModel, Field
from typing import Literal


class AccionSugerida(BaseModel):
    etiqueta: str
    ruta: str
    visible: bool


class RespuestaOrientacion(BaseModel):
    """Salida estructurada del asistente. Coincide con guia.md sección 7."""

    tipo_respuesta: Literal[
        "emergencia", "orientacion", "catalogo", "aclaracion", "derivar"
    ]
    mensaje: str = Field(..., description="Texto breve para la secretaria.")
    especialidad_sugerida: str | None = None
    especialidades_disponibles: list[str] = Field(default_factory=list)
    pregunta_aclaratoria: str = ""
    observacion: str = ""