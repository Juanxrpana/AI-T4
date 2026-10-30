#!/usr/bin/env bash
#
# Instala MIDI (componente IA / FastAPI) como servicio systemd.
#
# Uso:
#   sudo APP_DIR=/opt/AI-T4 RUN_USER=www bash deploy/install-midi-service.sh
#
# Variables opcionales:
#   APP_DIR       Ruta del proyecto AI-T4            (default: /opt/AI-T4)
#   RUN_USER      Usuario con el que corre el servicio (default: www)
#   SERVICE_NAME  Nombre del servicio                (default: midi)
#   PORT          Puerto local de uvicorn            (default: 8000)
#   PYTHON_BIN    Binario de Python                  (default: python3)
#
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/AI-T4}"
RUN_USER="${RUN_USER:-www}"
SERVICE_NAME="${SERVICE_NAME:-midi}"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    fail "Ejecuta como root: sudo APP_DIR=$APP_DIR bash deploy/install-midi-service.sh"
fi

[[ -d "$APP_DIR" ]] || fail "No existe APP_DIR=$APP_DIR. Clona/mueve el proyecto ahi o pasa APP_DIR=/ruta."
[[ -f "$APP_DIR/requirements.txt" ]] || fail "No se encontro $APP_DIR/requirements.txt (¿es la carpeta de AI-T4?)."
[[ -f "$APP_DIR/.env" ]] || fail "Falta $APP_DIR/.env. Copia .env.example y configuralo antes de continuar."

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "No se encontro '$PYTHON_BIN'. Instala Python 3: apt install -y python3 python3-venv python3-pip"
"$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1 || fail "Falta el modulo venv. Instala: apt install -y python3-venv"
id "$RUN_USER" >/dev/null 2>&1 || fail "No existe el usuario '$RUN_USER'."

log "Creando entorno virtual en $APP_DIR/.venv"
"$PYTHON_BIN" -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

log "Ajustando permisos a $RUN_USER:$RUN_USER"
mkdir -p "$APP_DIR/storage" "$APP_DIR/knowledge"
chown -R "$RUN_USER":"$RUN_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env" 2>/dev/null || true

UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
log "Escribiendo unit: $UNIT"
cat >"$UNIT" <<UNIT_EOF
[Unit]
Description=MIDI - Componente inteligente (FastAPI) - CEM Jehova Rafa
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT_EOF

log "Recargando systemd y activando $SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Servicio activo. Comprobando HTTP en 127.0.0.1:${PORT} ..."
    if command -v curl >/dev/null 2>&1; then
        code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/docs" || true)"
        log "GET /docs -> HTTP ${code:-sin respuesta} (200 esperado)"
    else
        log "curl no esta instalado; revisa con: journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
    fi
else
    printf '\nEl servicio NO quedo activo. Revisa el log:\n' >&2
    journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
    exit 1
fi

cat <<MSG_EOF

Listo.

  Estado : systemctl status ${SERVICE_NAME}
  Logs   : journalctl -u ${SERVICE_NAME} -f
  Reiniciar: systemctl restart ${SERVICE_NAME}

Recuerda que en el .env de CEMJR (PHP) debe estar:
  IA_API_URL=http://127.0.0.1:${PORT}/orientar
  API_KEY_IA=<mismo valor que API_KEY_COMPARTIDA del .env de AI-T4>
MSG_EOF
