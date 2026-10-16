import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai import ProveedorGemini
from config import settings
import tools.php_client as php_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("asistente")

proveedor = ProveedorGemini()

# Sesiones en memoria (temporal): se pierden al reiniciar el proceso.
SESIONES: dict[str, dict] = {}

# Cuántos turnos previos se reenvían a Gemini por consulta.
# 4 mensajes = 2 turnos (user + model, user + model).
MAX_HISTORIAL = 4


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga el catálogo al arrancar.

    Si PHP no responde en este momento, no se aborta: el catálogo se
    reintenta en cada /orientar (ver ai/gemini.py).
    """
    try:
        await proveedor.precargar_catalogo()
    except Exception:
        logger.exception("No se pudo precargar el catálogo al arrancar; se reintentará en cada consulta")
    yield


app = FastAPI(
    title="Asistente — CEM Jehová Rafa",
    description="Componente inteligente de orientación administrativa",
    version="1.0.0",
    lifespan=lifespan,
)

# El navegador nunca llama directo a esta API (lo hace PHP como proxy), así que
# CORS no hace falta. Solo se habilita si CORS_ORIGINS trae orígenes explícitos.
if settings.CORS_ORIGINS.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ConsultaIn(BaseModel):
    consulta: str = Field(..., min_length=2, max_length=2000)
    session_id: str | None = None


def verificar_api_key(x_api_key: str | None) -> None:
    """Valida la API key compartida (fail-closed).

    Si el servicio no tiene key configurada, rechaza TODAS las peticiones en
    lugar de quedar abierto.
    """
    esperada = settings.API_KEY_COMPARTIDA
    if not esperada:
        raise HTTPException(status_code=503, detail="Servicio no configurado")
    if not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(status_code=401, detail="API key inválida")


def _datos_usuario(request: Request) -> dict:
    """Datos del usuario que consulta, enviados por PHP en headers X-Usuario-*."""
    return {
        "id": request.headers.get("X-Usuario-Id"),
        "rol": request.headers.get("X-Usuario-Rol"),
        "nombre": request.headers.get("X-Usuario-Nombre"),
    }


@app.get("/")
def raiz():
    return {"servicio": "asistente-clinica", "estado": "ok"}


@app.post("/orientar")
async def orientar(
    body: ConsultaIn,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)

    usuario = _datos_usuario(request)
    session_id = body.session_id or str(uuid4())
    sesion = SESIONES.setdefault(
        session_id,
        {"historial": [], "creada_en": datetime.now(timezone.utc).isoformat()},
    )

    logger.info(
        "Consulta (session=%s usuario=%r rol=%r id=%r): %.80s",
        session_id, usuario["nombre"], usuario["rol"], usuario["id"], body.consulta,
    )

    # Recortar historial a los últimos MAX_HISTORIAL mensajes
    historial_recortado = sesion["historial"][-MAX_HISTORIAL:] or None

    # El id_usuario viaja por contexto para que la tool `mis_datos` sepa de
    # quién leer, sin que Gemini pueda elegir a otra persona.
    token_usuario = php_client.usuario_actual.set(usuario["id"])
    try:
        respuesta = await proveedor.orientar(
            consulta=body.consulta,
            historial=historial_recortado,
        )
    except Exception:
        # El detalle va al log del servidor; al cliente solo un mensaje neutro.
        logger.exception("Fallo al orientar (session=%s usuario=%r)", session_id, usuario["nombre"])
        return {
            "session_id": session_id,
            "tipo_respuesta": "derivar",
            "mensaje": "El servicio de orientación no está disponible en este momento.",
            "especialidad_sugerida": None,
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "observacion": "",
            "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
        }
    finally:
        php_client.usuario_actual.reset(token_usuario)

    sesion["historial"].append({"role": "user", "text": body.consulta})
    sesion["historial"].append({"role": "model", "text": respuesta["mensaje"]})

    return {"session_id": session_id, **respuesta}


@app.get("/sesiones/{session_id}")
def ver_sesion(
    session_id: str,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    if session_id not in SESIONES:
        raise HTTPException(404, "Sesión no encontrada")
    return {"session_id": session_id, "historial": SESIONES[session_id]["historial"]}


@app.delete("/sesiones/{session_id}", status_code=204)
def borrar_sesion(
    session_id: str,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    SESIONES.pop(session_id, None)
    return None
