"""Carga de la base de conocimiento activa desde SQLite.

El cuestionario es síncrono, así que este módulo expone un snapshot síncrono
(`sqlite3`) con la misma forma que el antiguo `knowledge/dominios.json`:
`{clave: {nombre, min_preguntas, max_preguntas, palabras_clave, senal_alarma,
preguntas, especialidades, pruebas, posibles_asociaciones, a_descartar,
ejemplos}}`.

Los JSON quedan solo como semilla de migración (`scripts/seed_kb.py`). Si la
base todavía no tiene la KB (arranque muy temprano o base antigua), se usa el
JSON como respaldo para no romper el servicio.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai.evidencia import normalizar
from config import settings
from storage import db as db_mod

_CACHE: dict | None = None
_RUTA_JSON = Path("knowledge/dominios.json")


def invalidar_cache() -> None:
    global _CACHE
    _CACHE = None


def _conectar() -> sqlite3.Connection:
    con = sqlite3.connect(str(db_mod.DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _lista(con: sqlite3.Connection, sql: str, dominio_id: int) -> list[str]:
    return [fila[0] for fila in con.execute(sql, (dominio_id,)).fetchall()]


def _cargar_db() -> dict:
    con = _conectar()
    try:
        filas = con.execute(
            "SELECT id, clave, nombre, min_preguntas, max_preguntas "
            "FROM dominio WHERE activo = 1 ORDER BY id"
        ).fetchall()
        if not filas:
            return {}

        datos: dict = {}
        for fila in filas:
            did = fila["id"]
            palabras = _lista(
                con,
                "SELECT valor FROM dominio_palabra_clave "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "AND alias_de IS NULL ORDER BY id",
                did,
            )
            senales = _lista(
                con,
                "SELECT valor FROM dominio_senal_alarma "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "AND alias_de IS NULL ORDER BY id",
                did,
            )
            especialidades = _lista(
                con,
                "SELECT nombre FROM dominio_especialidad "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY orden, id",
                did,
            )
            pruebas = _lista(
                con,
                "SELECT nombre FROM dominio_prueba "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY orden, id",
                did,
            )
            asociaciones = _lista(
                con,
                "SELECT valor FROM dominio_asociacion "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY orden, id",
                did,
            )
            descartes = _lista(
                con,
                "SELECT valor FROM dominio_descartar "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY orden, id",
                did,
            )
            ejemplos = _lista(
                con,
                "SELECT texto FROM dominio_ejemplo "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY id",
                did,
            )
            preguntas = [
                {"id": p["clave"], "texto": p["texto"]}
                for p in con.execute(
                    "SELECT clave, texto FROM dominio_pregunta "
                    "WHERE dominio_id = ? AND activo = 1 "
                    "AND estado = 'aprobado' ORDER BY orden, id",
                    (did,),
                ).fetchall()
            ]

            datos[fila["clave"]] = {
                "_id": did,
                "nombre": fila["nombre"],
                "min_preguntas": fila["min_preguntas"],
                "max_preguntas": fila["max_preguntas"],
                "palabras_clave": palabras,
                "senal_alarma": senales,
                "especialidades": especialidades,
                "pruebas": pruebas,
                "posibles_asociaciones": asociaciones,
                "a_descartar": descartes,
                "preguntas": preguntas,
                "ejemplos": ejemplos,
            }
        return datos
    finally:
        con.close()


def _cargar_json() -> dict:
    try:
        base = json.loads(_RUTA_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    try:
        ruta = Path(settings.APRENDIZAJE_PATH)
        aprendido = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except (OSError, ValueError):
        aprendido = {}

    for clave, extra in (aprendido or {}).items():
        if clave not in base:
            continue
        actual = base[clave]
        palabras = list(actual.get("palabras_clave", []))
        for palabra in extra.get("palabras_clave", []):
            if palabra not in palabras:
                palabras.append(palabra)
        actual["palabras_clave"] = palabras
        actual["ejemplos"] = list(extra.get("ejemplos", []))
    return base


def snapshot_sincrono(recargar: bool = False) -> dict:
    """Snapshot de la KB activa, cacheado hasta `invalidar_cache()`."""
    global _CACHE
    if _CACHE is not None and not recargar:
        return _CACHE

    try:
        datos = _cargar_db()
        if not datos:
            datos = _cargar_json()
    except sqlite3.Error:
        datos = _cargar_json()

    _CACHE = datos
    return datos


def id_dominio(clave: str) -> int | None:
    try:
        con = _conectar()
    except sqlite3.Error:
        return None
    try:
        fila = con.execute(
            "SELECT id FROM dominio WHERE clave = ? AND activo = 1", (clave,)
        ).fetchone()
        return fila["id"] if fila else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def listar_aprendido() -> dict:
    """Palabras y ejemplos con `origen = 'aprendido'`, por dominio."""
    resultado: dict = {}
    try:
        con = _conectar()
    except sqlite3.Error:
        return _aprendido_json()

    try:
        palabras = con.execute(
            "SELECT d.clave AS dominio, p.valor AS valor "
            "FROM dominio_palabra_clave p JOIN dominio d ON d.id = p.dominio_id "
            "WHERE p.origen = 'aprendido' AND p.activo = 1 "
            "AND p.estado = 'aprobado' ORDER BY p.id"
        ).fetchall()
        ejemplos = con.execute(
            "SELECT d.clave AS dominio, e.texto AS valor "
            "FROM dominio_ejemplo e JOIN dominio d ON d.id = e.dominio_id "
            "WHERE e.origen = 'aprendido' AND e.activo = 1 "
            "AND e.estado = 'aprobado' ORDER BY e.id"
        ).fetchall()
    except sqlite3.Error:
        return _aprendido_json()
    finally:
        con.close()

    for fila in palabras:
        entrada = resultado.setdefault(
            fila["dominio"], {"palabras_clave": [], "ejemplos": []}
        )
        entrada["palabras_clave"].append(fila["valor"])
    for fila in ejemplos:
        entrada = resultado.setdefault(
            fila["dominio"], {"palabras_clave": [], "ejemplos": []}
        )
        entrada["ejemplos"].append(fila["valor"])
    return resultado


def _aprendido_json() -> dict:
    try:
        ruta = Path(settings.APRENDIZAJE_PATH)
        if ruta.exists():
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def agregar_ejemplo(dominio: str, frase: str) -> bool:
    """Marca una frase como ejemplo aprendido del dominio."""
    frase = (frase or "").strip()
    if len(frase) < 3:
        return False

    did = id_dominio(dominio)
    if did is None:
        return False

    con = _conectar()
    try:
        con.execute(
            "INSERT INTO dominio_ejemplo "
            "(dominio_id, texto, texto_normalizado, origen, creado_por, "
            " activo, estado, creado_en) "
            "VALUES (?, ?, ?, 'aprendido', NULL, 1, 'aprobado', datetime('now')) "
            "ON CONFLICT(dominio_id, texto_normalizado) DO UPDATE SET "
            "origen = 'aprendido', activo = 1, estado = 'aprobado'",
            (did, frase, normalizar(frase)),
        )
        con.commit()
    finally:
        con.close()

    invalidar_cache()
    return True


def agregar_palabra(dominio: str, palabra: str) -> bool:
    """Añade una palabra clave canónica y la marca como aprendida."""
    palabra = (palabra or "").strip()
    if not palabra:
        return False

    did = id_dominio(dominio)
    if did is None:
        return False

    norm = normalizar(palabra)
    con = _conectar()
    try:
        fila = con.execute(
            "SELECT id FROM dominio_palabra_clave "
            "WHERE dominio_id = ? AND valor_normalizado = ? LIMIT 1",
            (did, norm),
        ).fetchone()
        if fila:
            con.execute(
                "UPDATE dominio_palabra_clave SET origen = 'aprendido', "
                "activo = 1, estado = 'aprobado' WHERE id = ?",
                (fila["id"],),
            )
        else:
            con.execute(
                "INSERT INTO dominio_palabra_clave "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'aprendido', 1, 'aprobado', NULL, "
                "datetime('now'))",
                (did, palabra, norm),
            )
        con.commit()
    finally:
        con.close()

    invalidar_cache()
    return True

async def publicar_version(descripcion: str, autor: str) -> int:
    """Publica el estado actual de las tablas como una nueva `kb_version`.

    Si el snapshot ya existe (mismo hash), solo la reactiva. La publicación es
    idempotente y se usa al aprobar propuestas.
    """
    datos = snapshot_sincrono(recargar=True)
    payload = json.dumps(
        datos, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    huella = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    creada = datetime.now(timezone.utc).isoformat()

    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT id FROM kb_version WHERE hash = ?", (huella,)
        ) as cur:
            existente = await cur.fetchone()

        if existente:
            await _activar(con, existente["id"])
            await con.commit()
            invalidar_cache()
            return int(existente["id"])

        await con.execute("UPDATE kb_version SET activa = 0")
        cur = await con.execute(
            "INSERT INTO kb_version "
            "(descripcion, autor, hash, normalizer_version, snapshot_json, "
            " creada_en, activa) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (
                descripcion, autor, huella, "evidencia-v1", payload, creada,
            ),
        )
        version_id = int(cur.lastrowid)

        for item in _items_actuales():
            await con.execute(
                "INSERT INTO kb_version_item "
                "(kb_version_id, tipo, elemento_id, dominio_id, clave, valor, "
                " valor_normalizado, estado, alias_de) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (version_id, *item),
            )

        await con.commit()
    finally:
        await con.close()

    invalidar_cache()
    return version_id


async def _activar(con, version_id: int) -> None:
    await con.execute("UPDATE kb_version SET activa = 0 WHERE id != ?", (version_id,))
    await con.execute("UPDATE kb_version SET activa = 1 WHERE id = ?", (version_id,))


def _items_actuales() -> list[tuple]:
    """Elementos aprobados y activos para el snapshot de `kb_version_item`."""
    con = _conectar()
    try:
        items: list[tuple] = []
        for dominio in con.execute(
            "SELECT id FROM dominio WHERE activo = 1 ORDER BY id"
        ).fetchall():
            did = dominio["id"]
            for fila in con.execute(
                "SELECT id, valor, valor_normalizado, estado, alias_de "
                "FROM dominio_palabra_clave WHERE dominio_id = ? AND activo = 1 "
                "AND estado = 'aprobado' ORDER BY id",
                (did,),
            ).fetchall():
                items.append((
                    "palabra", fila["id"], did, None, fila["valor"],
                    fila["valor_normalizado"], fila["estado"], fila["alias_de"],
                ))
            for fila in con.execute(
                "SELECT id, valor, valor_normalizado, estado, alias_de "
                "FROM dominio_senal_alarma WHERE dominio_id = ? AND activo = 1 "
                "AND estado = 'aprobado' ORDER BY id",
                (did,),
            ).fetchall():
                items.append((
                    "senal", fila["id"], did, None, fila["valor"],
                    fila["valor_normalizado"], fila["estado"], fila["alias_de"],
                ))
            for fila in con.execute(
                "SELECT id, clave, texto, estado FROM dominio_pregunta "
                "WHERE dominio_id = ? AND activo = 1 AND estado = 'aprobado' "
                "ORDER BY orden, id",
                (did,),
            ).fetchall():
                items.append((
                    "pregunta", fila["id"], did, fila["clave"], fila["texto"],
                    normalizar(fila["texto"]), fila["estado"], None,
                ))
            for tabla, tipo in (
                ("dominio_especialidad", "especialidad"),
                ("dominio_prueba", "prueba"),
            ):
                for fila in con.execute(
                    f"SELECT id, nombre, nombre_normalizado, estado FROM {tabla} "
                    "WHERE dominio_id = ? AND activo = 1 "
                    "AND estado = 'aprobado' ORDER BY orden, id",
                    (did,),
                ).fetchall():
                    items.append((
                        tipo, fila["id"], did, None, fila["nombre"],
                        fila["nombre_normalizado"], fila["estado"], None,
                    ))
            for tabla, tipo in (
                ("dominio_asociacion", "asociacion"),
                ("dominio_descartar", "descartar"),
                ("dominio_ejemplo", "ejemplo"),
            ):
                columna = "texto" if tipo == "ejemplo" else "valor"
                normalizada = f"{columna}_normalizado"
                for fila in con.execute(
                    f"SELECT id, {columna} AS valor, {normalizada} AS norm, "
                    "estado FROM " + tabla + " WHERE dominio_id = ? AND activo = 1 "
                    "AND estado = 'aprobado' ORDER BY id",
                    (did,),
                ).fetchall():
                    items.append((
                        tipo, fila["id"], did, None, fila["valor"],
                        fila["norm"], fila["estado"], None,
                    ))
        return items
    finally:
        con.close()
