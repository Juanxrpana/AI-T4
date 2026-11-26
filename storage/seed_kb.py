"""Semilla de la base de conocimiento por tipo.

Los JSON de `knowledge/` son **solo insumo de migración**. El seed:
* separa canónicos y alias por `valor_normalizado` (primer valor = canónico);
* inserta una fila por elemento en la tabla de su tipo;
* publica una `kb_version` con hash SHA-256 del snapshot canónico y sus
  `kb_version_item`;
* es idempotente vía `sembrar_si_vacio()`.

Conteos esperados con los datos actuales: 4 dominios, 19 preguntas, 39 palabras
(29 canónicas + 10 alias), 31 señales (25 + 6), 5 especialidades (2 nombres),
11 pruebas, 12 asociaciones, 12 descartes y 4 ejemplos aprendidos.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from ai.evidencia import normalizar

_RUTA_DOMINIOS = Path("knowledge/dominios.json")
_RUTA_APRENDIDO = Path("knowledge/aprendido.json")
NORMALIZER_VERSION = "evidencia-v1"
AUTOR = "seed"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _leer_json(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _separar(valores: list[str]) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
    """(canónicos, alias) agrupando por valor normalizado.

    El primer valor de cada grupo es el canónico; los siguientes son alias que
    apuntan a él. Es determinista respecto del orden del JSON.
    """
    canonicos: list[tuple[str, str]] = []
    alias: list[tuple[str, str, str]] = []
    vistos: dict[str, str] = {}

    for valor in valores or []:
        texto = (valor or "").strip()
        norm = normalizar(texto)
        if not norm:
            continue
        if norm in vistos:
            alias.append((texto, norm, vistos[norm]))
        else:
            vistos[norm] = texto
            canonicos.append((texto, norm))
    return canonicos, alias


async def sembrar_si_vacio(con: aiosqlite.Connection) -> int | None:
    async with con.execute("SELECT COUNT(*) FROM dominio") as cur:
        total = (await cur.fetchone())[0]
    if total:
        return None
    return await sembrar(con)


async def sembrar(con: aiosqlite.Connection) -> int:
    base = _leer_json(_RUTA_DOMINIOS)
    if not base:
        raise RuntimeError(f"No se pudo leer la semilla {_RUTA_DOMINIOS}")

    aprendido = _leer_json(_RUTA_APRENDIDO)
    ahora = _ahora()
    snapshot: dict = {}
    items: list[dict] = []

    for clave, cfg in base.items():
        cur = await con.execute(
            "INSERT INTO dominio "
            "(clave, nombre, min_preguntas, max_preguntas, activo, "
            " creado_en, actualizado_en) VALUES (?, ?, ?, ?, 1, ?, ?)",
            (
                clave,
                cfg.get("nombre", clave),
                int(cfg.get("min_preguntas", 3)),
                int(cfg.get("max_preguntas", 5)),
                ahora,
                ahora,
            ),
        )
        did = cur.lastrowid

        palabras, palabras_alias = _separar(cfg.get("palabras_clave", []))
        ids_palabra: dict[str, int] = {}
        for valor, norm in palabras:
            c = await con.execute(
                "INSERT INTO dominio_palabra_clave "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'seed', 1, 'aprobado', NULL, ?)",
                (did, valor, norm, ahora),
            )
            ids_palabra[norm] = c.lastrowid
            items.append(_item("palabra", c.lastrowid, did, None, valor, norm))
        for valor, norm, objetivo in palabras_alias:
            c = await con.execute(
                "INSERT INTO dominio_palabra_clave "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'seed', 1, 'aprobado', ?, ?)",
                (did, valor, norm, ids_palabra[normalizar(objetivo)], ahora),
            )
            items.append(
                _item(
                    "palabra", c.lastrowid, did, None, valor, norm,
                    alias_de=ids_palabra[normalizar(objetivo)],
                )
            )

        # Palabras aprendidas que todavía no estén en la curada.
        for palabra in (aprendido.get(clave, {}) or {}).get("palabras_clave", []):
            texto = (palabra or "").strip()
            norm = normalizar(texto)
            if not norm or norm in ids_palabra:
                continue
            c = await con.execute(
                "INSERT INTO dominio_palabra_clave "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'aprendido', 1, 'aprobado', NULL, ?)",
                (did, texto, norm, ahora),
            )
            ids_palabra[norm] = c.lastrowid
            items.append(
                _item("palabra", c.lastrowid, did, None, texto, norm,
                      origen="aprendido")
            )

        senales, senales_alias = _separar(cfg.get("senal_alarma", []))
        ids_senal: dict[str, int] = {}
        for valor, norm in senales:
            c = await con.execute(
                "INSERT INTO dominio_senal_alarma "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'seed', 1, 'aprobado', NULL, ?)",
                (did, valor, norm, ahora),
            )
            ids_senal[norm] = c.lastrowid
            items.append(_item("senal", c.lastrowid, did, None, valor, norm))
        for valor, norm, objetivo in senales_alias:
            c = await con.execute(
                "INSERT INTO dominio_senal_alarma "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'seed', 1, 'aprobado', ?, ?)",
                (did, valor, norm, ids_senal[normalizar(objetivo)], ahora),
            )
            items.append(
                _item(
                    "senal", c.lastrowid, did, None, valor, norm,
                    alias_de=ids_senal[normalizar(objetivo)],
                )
            )

        for orden, pregunta in enumerate(cfg.get("preguntas", [])):
            clave_pregunta = pregunta.get("id") or f"p{orden + 1}"
            c = await con.execute(
                "INSERT INTO dominio_pregunta "
                "(dominio_id, clave, texto, orden, activo, estado, creado_en) "
                "VALUES (?, ?, ?, ?, 1, 'aprobado', ?)",
                (did, clave_pregunta, pregunta.get("texto", ""), orden, ahora),
            )
            items.append(
                _item(
                    "pregunta", c.lastrowid, did, clave_pregunta,
                    pregunta.get("texto", ""), normalizar(pregunta.get("texto", "")),
                )
            )

        for tabla, tipo, campo in (
            ("dominio_especialidad", "especialidad", "especialidades"),
            ("dominio_prueba", "prueba", "pruebas"),
        ):
            for orden, valor in enumerate(cfg.get(campo, [])):
                c = await con.execute(
                    f"INSERT INTO {tabla} "
                    "(dominio_id, nombre, nombre_normalizado, orden, activo, "
                    " estado, creado_en) VALUES (?, ?, ?, ?, 1, 'aprobado', ?)",
                    (did, valor, normalizar(valor), orden, ahora),
                )
                items.append(
                    _item(tipo, c.lastrowid, did, None, valor, normalizar(valor))
                )

        for tabla, tipo, campo in (
            ("dominio_asociacion", "asociacion", "posibles_asociaciones"),
            ("dominio_descartar", "descartar", "a_descartar"),
        ):
            for orden, valor in enumerate(cfg.get(campo, [])):
                c = await con.execute(
                    f"INSERT INTO {tabla} "
                    "(dominio_id, valor, valor_normalizado, orden, activo, "
                    " estado, creado_en) VALUES (?, ?, ?, ?, 1, 'aprobado', ?)",
                    (did, valor, normalizar(valor), orden, ahora),
                )
                items.append(
                    _item(tipo, c.lastrowid, did, None, valor, normalizar(valor))
                )

        ejemplos_vistos: set[str] = set()
        ejemplos: list[str] = []
        for origen, lista in (
            ("seed", cfg.get("ejemplos", [])),
            ("aprendido", (aprendido.get(clave, {}) or {}).get("ejemplos", [])),
        ):
            for texto in lista or []:
                texto = (texto or "").strip()
                norm = normalizar(texto)
                if len(texto) < 3 or not norm or norm in ejemplos_vistos:
                    continue
                ejemplos_vistos.add(norm)
                ejemplos.append(texto)
                c = await con.execute(
                    "INSERT INTO dominio_ejemplo "
                    "(dominio_id, texto, texto_normalizado, origen, "
                    " creado_por, activo, estado, creado_en) "
                    "VALUES (?, ?, ?, ?, NULL, 1, 'aprobado', ?)",
                    (did, texto, norm, origen, ahora),
                )
                items.append(
                    _item("ejemplo", c.lastrowid, did, None, texto, norm,
                          origen=origen)
                )

        snapshot[clave] = {
            "nombre": cfg.get("nombre", clave),
            "min_preguntas": int(cfg.get("min_preguntas", 3)),
            "max_preguntas": int(cfg.get("max_preguntas", 5)),
            "palabras_clave": [valor for valor, _ in palabras],
            "senal_alarma": [valor for valor, _ in senales],
            "preguntas": [
                {"id": p.get("id"), "texto": p.get("texto", "")}
                for p in cfg.get("preguntas", [])
            ],
            "especialidades": list(cfg.get("especialidades", [])),
            "pruebas": list(cfg.get("pruebas", [])),
            "posibles_asociaciones": list(cfg.get("posibles_asociaciones", [])),
            "a_descartar": list(cfg.get("a_descartar", [])),
            "ejemplos": ejemplos,
        }

    payload = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    huella = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async with con.execute(
        "SELECT id FROM kb_version WHERE hash = ?", (huella,)
    ) as cur:
        existente = await cur.fetchone()
    if existente:
        await _activar(con, existente["id"])
        await con.commit()
        return existente["id"]

    await con.execute("UPDATE kb_version SET activa = 0")
    cur = await con.execute(
        "INSERT INTO kb_version "
        "(descripcion, autor, hash, normalizer_version, snapshot_json, "
        " creada_en, activa) VALUES (?, ?, ?, ?, ?, ?, 1)",
        (
            "Semilla inicial de la base de conocimiento por tipo",
            AUTOR,
            huella,
            NORMALIZER_VERSION,
            payload,
            ahora,
        ),
    )
    version_id = cur.lastrowid

    for item in items:
        await con.execute(
            "INSERT INTO kb_version_item "
            "(kb_version_id, tipo, elemento_id, dominio_id, clave, valor, "
            " valor_normalizado, estado, alias_de) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                version_id,
                item["tipo"],
                item["elemento_id"],
                item["dominio_id"],
                item["clave"],
                item["valor"],
                item["valor_normalizado"],
                "aprobado",
                item.get("alias_de"),
            ),
        )

    await con.commit()
    return version_id


def _item(
    tipo: str,
    elemento_id: int,
    dominio_id: int,
    clave: str | None,
    valor: str,
    valor_normalizado: str,
    alias_de: int | None = None,
    origen: str | None = None,
) -> dict:
    return {
        "tipo": tipo,
        "elemento_id": elemento_id,
        "dominio_id": dominio_id,
        "clave": clave,
        "valor": valor,
        "valor_normalizado": valor_normalizado,
        "alias_de": alias_de,
        "origen": origen,
    }


async def _activar(con: aiosqlite.Connection, version_id: int) -> None:
    await con.execute("UPDATE kb_version SET activa = 0 WHERE id != ?", (version_id,))
    await con.execute("UPDATE kb_version SET activa = 1 WHERE id = ?", (version_id,))
