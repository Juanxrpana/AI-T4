"""Motor de evidencia compartido para detección de dominio y alarma.

Reglas fijas:
- Normaliza (NFD, minúsculas, sin acentos).
- Tokeniza con offsets sobre el texto normalizado.
- Para hacer matching ignora stopwords y tokens de menos de 4 letras, pero
  conserva la lista completa para evaluar la negación.
- Una coincidencia es negativa si en su ventana hay un número impar de
  marcadores de negación; dos marcadores (doble negación) la vuelven positiva.
"""

import re
import unicodedata

NEGACIONES = {"no", "sin", "niega", "nunca"}
# Conectores y puntuación que cierran el alcance de una negación.
CORTES = {"pero", "aunque", "sino", "embargo", "mas", ",", ";", "."}

# Palabras que no aportan al comparar frases (misma lista que el cuestionario).
VACIAS = {
    "de", "la", "el", "en", "con", "que", "por", "para", "los", "las", "un",
    "una", "unos", "unas", "y", "o", "mi", "me", "se", "al", "del", "es",
    "son", "tengo", "tiene", "como", "desde", "esta", "este", "hace", "dias",
    "día", "hola", "problema", "mucho", "poco", "muy", "solo", "sólo",
    "tambien", "también", "pero", "porque", "cuando", "donde", "dónde",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def tokenizar(texto: str) -> list[tuple[str, int, int]]:
    """Devuelve [(token, inicio, fin)] sobre el texto normalizado.

    Incluye la puntuación de cierre de cláusula (`,`, `;`, `.`) para que la
    negación no cruce de una cláusula a otra.
    """
    plano = normalizar(texto)
    return [
        (m.group(0), m.start(), m.end())
        for m in re.finditer(r"[a-z0-9]+|[,;.]", plano)
    ]


def tokens(texto: str) -> set[str]:
    """Tokens significativos para similitud (sin stopwords, longitud >= 4)."""
    return {
        token for token, _, _ in tokenizar(texto)
        if len(token) >= 4 and token not in VACIAS
    }


def similitud(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _contar_negaciones(lista_tokens: list[str]) -> int:
    total = 0
    i = 0
    while i < len(lista_tokens):
        if lista_tokens[i] in NEGACIONES:
            total += 1
        elif (
            lista_tokens[i] == "ausencia"
            and i + 1 < len(lista_tokens)
            and lista_tokens[i + 1] == "de"
        ):
            total += 1
            i += 1
        i += 1
    return total


def _tokens_filtrados(texto: str) -> list[tuple[str, int]]:
    completos = tokenizar(texto)
    return [
        (token, indice)
        for indice, (token, _, _) in enumerate(completos)
        if len(token) >= 4 and token not in VACIAS
    ]


def detectar_evidencia(
    texto: str,
    terminos,
    ventana: int = 8,
) -> list[dict]:
    """Busca cada término y devuelve coincidencias con polaridad.

    La negación se evalúa dentro de la cláusula del término: se mira hacia la
    izquierda hasta `ventana` tokens, pero se corta en el último conector de
    contraste o signo de puntuación (`,`, `;`, `.`). Así «no tengo dolor de
    pecho» es negativa y «no tengo fiebre, me duele el pecho» es positiva para
    el pecho. Un número impar de marcadores niega; dos (doble negación) no.
    """
    completos = tokenizar(texto)
    filtrados = _tokens_filtrados(texto)
    resultados: list[dict] = []

    for termino in terminos or []:
        termino_tokens = [
            token for token, _, _ in tokenizar(termino)
            if len(token) >= 4 and token not in VACIAS
        ]
        if not termino_tokens:
            # Términos de una sola palabra corta o solo stopwords: match exacto.
            termino_tokens = [token for token, _, _ in tokenizar(termino)]
        if not termino_tokens:
            continue

        n = len(termino_tokens)
        for i in range(len(filtrados) - n + 1):
            if [token for token, _ in filtrados[i:i + n]] != termino_tokens:
                continue

            indices = [indice for _, indice in filtrados[i:i + n]]
            primero, ultimo = indices[0], indices[-1]
            inicio = max(0, primero - ventana)
            for j in range(primero - 1, inicio - 1, -1):
                if completos[j][0] in CORTES:
                    inicio = j + 1
                    break
            fin = min(len(completos), ultimo + 2)
            texto_ventana = [token for token, _, _ in completos[inicio:fin]]
            negaciones = _contar_negaciones(texto_ventana)

            resultados.append({
                "termino": termino,
                "polaridad": "negativa" if negaciones % 2 else "positiva",
                "offset": primero,
                "ventana": (inicio, fin),
            })

    return resultados


def coincide(texto: str, terminos) -> bool:
    """True si hay al menos una coincidencia con polaridad positiva."""
    return any(
        item["polaridad"] == "positiva"
        for item in detectar_evidencia(texto, terminos)
    )


def hay_alarma(texto: str, terminos) -> bool:
    """La alarma usa la misma regla de polaridad que el dominio."""
    return coincide(texto, terminos)


def contar_negaciones(texto: str) -> int:
    """Número de marcadores de negación en el texto (ausencia de = 1)."""
    return _contar_negaciones([token for token, _, _ in tokenizar(texto)])
