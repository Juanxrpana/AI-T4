from abc import ABC, abstractmethod


class ProveedorIA(ABC):
    """Interfaz común para cualquier proveedor de IA.

    Permite cambiar Gemini por otro modelo sin tocar el resto del sistema.
    """

    @property
    def nombre_modelo(self) -> str:
        """Identificador legible del modelo, usado en auditoría."""
        return type(self).__name__

    async def precargar_catalogo(self) -> None:
        """Hook opcional para calentar el catálogo al arrancar."""
        return None

    @abstractmethod
    async def orientar(
        self,
        consulta: str,
        historial: list[dict] | None = None,
    ) -> dict:
        """Recibe la consulta y devuelve un dict conforme a RespuestaOrientacion."""
        ...