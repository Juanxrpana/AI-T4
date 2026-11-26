# Despliegue del servicio MIDI (`deploy`)

## Overview

`deploy` contiene el instalador del componente FastAPI como servicio `systemd` en un VPS Linux. El servicio escucha solo en `127.0.0.1:8000`; el sistema PHP le hace de proxy. El instalador crea un entorno virtual, instala `requirements.txt`, ajusta permisos, escribe la unidad de `systemd` y arranca el servicio.

No instala paquetes del sistema, no abre puertos y no configura el proxy PHP. El `.env` del proyecto debe existir antes de ejecutar el script.

## Interface

### `deploy/install-midi-service.sh`

Variables de entorno:

- `APP_DIR` (por defecto `/opt/AI-T4`): ruta del proyecto.
- `RUN_USER` (por defecto `www`): usuario del servicio.
- `SERVICE_NAME` (por defecto `midi`): nombre de la unidad.
- `PORT` (por defecto `8000`): puerto local de `uvicorn`.
- `PYTHON_BIN` (por defecto `python3`): intérprete para crear el entorno.

Funciones internas:

- `log(mensaje)`: imprime un mensaje con hora.
- `fail(mensaje)`: imprime un error y termina con código distinto de cero.

Secuencia:

1. Exige ejecución como root (`EUID`/`id -u`).
2. Verifica `APP_DIR`, `requirements.txt`, `.env`, `python3`, `venv` y que `RUN_USER` exista.
3. Crea `APP_DIR/.venv` e instala `requirements.txt`.
4. Crea `storage/` y `knowledge/`, hace `chown -R RUN_USER:RUN_USER APP_DIR` y `chmod 600 .env`.
5. Escribe `/etc/systemd/system/${SERVICE_NAME}.service` con `uvicorn main:app --host 127.0.0.1 --port ${PORT}`.
6. Ejecuta `systemctl daemon-reload`, `enable` y `restart`.
7. Comprueba `systemctl is-active` y, si existe `curl`, hace `GET /docs` en `127.0.0.1:${PORT}`.

## Invariants

- **Root obligatorio.** El script aborta si no se ejecuta como root.
- **Rutas obligatorias.** `APP_DIR` debe existir y contener `requirements.txt` y `.env`; si falta cualquiera, aborta.
- **Usuario existente.** `RUN_USER` debe existir en el sistema; el script no lo crea.
- **Entorno aislado.** Las dependencias se instalan en `APP_DIR/.venv`, no en el Python del sistema.
- **Permisos.** El script hace `chown -R` de todo `APP_DIR` e intenta dejar `.env` en modo `600`.
- **Escucha local.** La unidad usa `--host 127.0.0.1`; el puerto no se expone a Internet.
- **Reinicio automático.** La unidad usa `Restart=always` y `RestartSec=5`.
- **Sin instalación de paquetes.** El script asume que `python3`, `python3-venv` y `curl` ya están instalados; no instala paquetes del sistema.
- **Sin configuración de PHP.** El script solo recuerda que el `.env` de CEMJR debe tener `IA_API_URL` y `API_KEY_IA`; no los escribe.

## Side Effects

- Creación de `APP_DIR/.venv`.
- Instalación de paquetes con `pip`.
- Cambio de propietario y permisos en `APP_DIR`, incluido `.env`.
- Escritura de `/etc/systemd/system/${SERVICE_NAME}.service`.
- `systemctl daemon-reload`, `enable` y `restart`.
- Petición HTTP GET a `http://127.0.0.1:${PORT}/docs` si `curl` está disponible.
- Sin cambios en la base de datos clínica, sin apertura de puertos y sin configuración del proxy PHP.

## Verification

- Run: `pytest`
- Verificación del script: `bash -n deploy/install-midi-service.sh` si hay Bash disponible.
- Nota: la ejecución real requiere un VPS Linux, root y un `.env` configurado. No ejecutar el instalador en el entorno de desarrollo Windows.
