# Despliegue del componente IA (MIDI) en el VPS

MIDI es un servicio FastAPI que escucha **solo en `127.0.0.1:8000`** (no se
expone a Internet). El sistema PHP (`/Chat/preguntar`) le hace de proxy.

## 1. Requisitos en el VPS

```bash
apt update
apt install -y python3 python3-venv python3-pip curl
python3 --version   # 3.10 o superior
```

## 2. Ubicar el proyecto

Recomendado fuera del webroot:

```bash
sudo mkdir -p /opt/AI-T4
# clona o copia el proyecto AI-T4 dentro de /opt/AI-T4
```

## 3. Configurar `/opt/AI-T4/.env`

Debe contener (mismos nombres que usa `config/settings.py`):

```ini
GEMINI_API_KEY=tu_clave_de_gemini
MODELO_GEMINI=gemini-2.5-flash
MODELOS_FALLBACK=gemini-2.5-flash,gemini-2.5-flash-lite
IA_TIMEOUT_MODELO=12

# URL base del sistema PHP. OJO: ya NO lleva /Sistema-del--CEM--JEHOVA-RAFA
PHP_BASE_URL=http://cemjr.duckdns.org

# Clave compartida con el PHP (debe ser IGUAL a API_KEY_IA del .env de CEMJR)
API_KEY_COMPARTIDA=una_cadena_larga_y_aleatoria
```

> `PHP_BASE_URL` se usa para que MIDI consulte `/Api/apiEspecialidades`,
> `/Api/apiDatosUsuario/...`, etc. Como el sistema ahora se sirve en la raíz,
> **no** debe incluir el prefijo del proyecto.

## 4. Instalar como servicio

```bash
cd /opt/AI-T4
sudo APP_DIR=/opt/AI-T4 RUN_USER=www bash deploy/install-midi-service.sh
```

El script crea el `.venv`, instala `requirements.txt`, genera
`/etc/systemd/system/midi.service`, lo habilita y lo arranca.

Si quieres hacerlo a mano, el unit equivalente es:

```ini
[Unit]
Description=MIDI - Componente inteligente (FastAPI) - CEM Jehova Rafa
After=network.target

[Service]
Type=simple
User=www
Group=www
WorkingDirectory=/opt/AI-T4
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/AI-T4/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now midi
```

## 5. Verificar

```bash
systemctl status midi
journalctl -u midi -f
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs   # 200
```

## 6. Conectar con el sistema PHP (`.env` de CEMJR)

En el `.env` del proyecto PHP:

```ini
IA_API_URL=http://127.0.0.1:8000/orientar
API_KEY_IA=una_cadena_larga_y_aleatoria   # igual a API_KEY_COMPARTIDA
```

Luego prueba el chat desde el sistema (botón flotante). Si falla, revisa:

```bash
journalctl -u midi -n 100 --no-pager
tail -n 100 /www/wwwlogs/cemjr.duckdns.org-error_log
```

## Notas

- El servicio escribe `storage/midi.db` (SQLite) y `knowledge/aprendido.json`.
  El usuario del servicio (`www`) debe poder escribir esas carpetas (el script
  hace `chown`).
- Si cambias el puerto, actualiza también `IA_API_URL` en el `.env` de CEMJR.
- No abras el puerto 8000 en el firewall: debe quedar solo en `127.0.0.1`.
