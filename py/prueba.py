import fastapi
from pydantic import BaseModel


router = fastapi.APIRouter(prefix="/prueba", tags=["Prueba"])

@router.get("/test")
def test():
    return {"test": "test"}

@router.get("/test2")
def test2():
    return {"mibombo": "clat"}

