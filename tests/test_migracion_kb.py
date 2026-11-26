"""Fase 1: migración de la KB por tipo y seed reproducible."""

import asyncio
import sqlite3

import pytest

import ai.cuestionario as cuestionario
from storage import conocimiento, db
from storage.seed_kb import NORMALIZER_VERSION


@pytest.fixture()
def base_temporal(tmp_path, monkeypatch):
    ruta = tmp_path / "kb_test.db"
    monkeypatch.setattr(db, "DB_PATH", ruta)
    conocimiento.invalidar_cache()
    asyncio.run(db.init_db())
    yield ruta
    conocimiento.invalidar_cache()


def _con(ruta):
    con = sqlite3.connect(str(ruta))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def test_conteos_del_seed(base_temporal):
    con = _con(base_temporal)
    try:
        esperado = {
            "dominio": 4,
            "dominio_pregunta": 19,
            "dominio_palabra_clave": 39,
            "dominio_senal_alarma": 31,
            "dominio_especialidad": 5,
            "dominio_prueba": 11,
            "dominio_asociacion": 12,
            "dominio_descartar": 12,
            "dominio_ejemplo": 4,
        }
        for tabla, total in esperado.items():
            real = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            assert real == total, f"{tabla}: {real} != {total}"

        canonicas = con.execute(
            "SELECT COUNT(*) FROM dominio_palabra_clave WHERE alias_de IS NULL"
        ).fetchone()[0]
        alias = con.execute(
            "SELECT COUNT(*) FROM dominio_palabra_clave WHERE alias_de IS NOT NULL"
        ).fetchone()[0]
        assert (canonicas, alias) == (29, 10)

        senales = con.execute(
            "SELECT COUNT(*) FROM dominio_senal_alarma WHERE alias_de IS NULL"
        ).fetchone()[0]
        senales_alias = con.execute(
            "SELECT COUNT(*) FROM dominio_senal_alarma WHERE alias_de IS NOT NULL"
        ).fetchone()[0]
        assert (senales, senales_alias) == (25, 6)
    finally:
        con.close()


def test_foreign_key_check_vacio(base_temporal):
    con = _con(base_temporal)
    try:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        con.close()


def test_alias_apunta_al_canonico(base_temporal):
    con = _con(base_temporal)
    try:
        fila = con.execute(
            "SELECT a.id, a.alias_de, c.valor_normalizado AS canonico "
            "FROM dominio_senal_alarma a "
            "JOIN dominio_senal_alarma c ON c.id = a.alias_de "
            "WHERE a.valor_normalizado = 'sudoracion' AND a.alias_de IS NOT NULL"
        ).fetchone()
        assert fila is not None
        assert fila["canonico"] == "sudoracion"
    finally:
        con.close()


def test_kb_version_activa_y_snapshot(base_temporal):
    con = _con(base_temporal)
    try:
        version = con.execute(
            "SELECT * FROM kb_version WHERE activa = 1"
        ).fetchone()
        assert version is not None
        assert version["normalizer_version"] == NORMALIZER_VERSION
        assert len(version["hash"]) == 64
        items = con.execute(
            "SELECT COUNT(*) FROM kb_version_item WHERE kb_version_id = ?",
            (version["id"],),
        ).fetchone()[0]
        assert items == 133
    finally:
        con.close()


def test_deteccion_igual_tras_migrar(base_temporal):
    conocimiento.invalidar_cache()
    datos = conocimiento.snapshot_sincrono()
    assert sorted(datos) == [
        "dolor_abdominal",
        "dolor_toracico",
        "fiebre",
        "lesion_piel",
    ]
    for cfg in datos.values():
        assert cfg["preguntas"]
        assert cfg["palabras_clave"]
        assert cfg["senal_alarma"]

    assert cuestionario.detectar_dominio("me duele el pecho") == "dolor_toracico"
    assert cuestionario.detectar_dominio("tengo fiebre") == "fiebre"
    assert cuestionario.detectar_dominio("dolor de barriga") == "dolor_abdominal"
    assert cuestionario.detectar_dominio("manchas rojas en la piel") == "lesion_piel"
    assert cuestionario.detectar_dominio("no tengo dolor de pecho") is None


def test_seed_idempotente(base_temporal):
    conocimiento.invalidar_cache()
    asyncio.run(db.init_db())
    con = _con(base_temporal)
    try:
        assert con.execute("SELECT COUNT(*) FROM dominio").fetchone()[0] == 4
        assert con.execute("SELECT COUNT(*) FROM kb_version").fetchone()[0] == 1
        assert (
            con.execute(
                "SELECT COUNT(*) FROM kb_version WHERE activa = 1"
            ).fetchone()[0]
            == 1
        )
    finally:
        con.close()


def test_runtime_no_depende_del_json(base_temporal, tmp_path, monkeypatch):
    conocimiento.invalidar_cache()
    monkeypatch.setattr(conocimiento, "_RUTA_JSON", tmp_path / "no-existe.json")

    datos = conocimiento.snapshot_sincrono(recargar=True)

    assert len(datos) == 4
    assert datos["fiebre"]["preguntas"]
