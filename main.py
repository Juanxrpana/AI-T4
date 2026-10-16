from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

from ai import ProveedorGemini
from config import settings

app = FastAPI(
    title="Asistente — CEM Jehová Rafa",
    description="Componente inteligente de orientación administrativa",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # ⚠️ restringir en producción
    allow_methods=["*"],
    allow_headers=["*"],
)

proveedor = ProveedorGemini()

# Sesiones en memoria (temporal — ver guia.md sección 8)
SESIONES: dict[str, dict] = {}


class ConsultaIn(BaseModel):
    consulta: str = Field(..., min_length=2, max_length=2000)
    session_id: str | None = None


def verificar_api_key(x_api_key: str | None = Header(default=None)):
    if settings.API_KEY_COMPARTIDA and x_api_key != settings.API_KEY_COMPARTIDA:
        raise HTTPException(status_code=401, detail="API key inválida")


@app.get("/")
def raiz():
    return {"servicio": "asistente-clinica", "estado": "ok"}


@app.post("/orientar")
async def orientar(body: ConsultaIn, x_api_key: str | None = Header(default=None)):
    verificar_api_key(x_api_key)

    session_id = body.session_id or str(uuid4())
    sesion = SESIONES.setdefault(
        session_id,
        {"historial": [], "creada_en": datetime.utcnow().isoformat()},
    )

    try:
        respuesta = await proveedor.orientar(
            consulta=body.consulta,
            historial=sesion["historial"] or None,
        )
    except Exception as e:
        return {
            "session_id": session_id,
            "tipo_respuesta": "derivar",
            "mensaje": "El servicio de orientación no está disponible en este momento.",
            "especialidad_sugerida": None,
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "observacion": f"Detalle técnico: {e}",
            "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
        }

    sesion["historial"].append({"role": "user", "text": body.consulta})
    sesion["historial"].append({"role": "model", "text": respuesta["mensaje"]})

    return {"session_id": session_id, **respuesta}


@app.get("/sesiones/{session_id}")
def ver_sesion(session_id: str, x_api_key: str | None = Header(default=None)):
    verificar_api_key(x_api_key)
    if session_id not in SESIONES:
        raise HTTPException(404, "Sesión no encontrada")
    return {"session_id": session_id, "historial": SESIONES[session_id]["historial"]}


@app.delete("/sesiones/{session_id}", status_code=204)
def borrar_sesion(session_id: str, x_api_key: str | None = Header(default=None)):
    verificar_api_key(x_api_key)
    SESIONES.pop(session_id, None)
    return None