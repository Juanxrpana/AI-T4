from abc import ABC, abstractmethod


class ProveedorIA(ABC):
    """Interfaz común para cualquier proveedor de IA.

    Permite cambiar Gemini por otro modelo sin tocar el resto del sistema.
    """

    @abstractmethod
    async def orientar(
        self,
        consulta: str,
        historial: list[dict] | None = None,
    ) -> dict:
        """Recibe la consulta y devuelve un dict conforme a RespuestaOrientacion."""
        ...