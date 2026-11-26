# Migraciones SQL

Los archivos `*.sql` de este directorio se aplican en orden lexicográfico una
sola vez. `storage/db.py` registra su checksum en `schema_migrations` y falla si
un archivo ya aplicado cambia.

El esquema base de la Fase 1 vive en `storage/schema.sql` (idempotente). Las
fases siguientes añaden archivos aquí (`003_outbox.sql`, etc.).
