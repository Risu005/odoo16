#!/bin/bash
set -e

MODULE_NAME="${1:-cctz_warranty}"
REMOTE_USER="administrator"
REMOTE_HOST="10.1.0.50"
REMOTE_PATH="/opt/odoo16/custom/${MODULE_NAME}"

echo "=========================================================="
echo "  UAT DEPLOYMENT: ${MODULE_NAME}"
echo "  Target Host: ${REMOTE_HOST}"
echo "  Remote Path: ${REMOTE_PATH}"
echo "=========================================================="

# 1. Upload validated changes to UAT
echo ""
echo "[1/2] Uploading updated ${MODULE_NAME} files to UAT..."
scp -r ./custom/${MODULE_NAME}/* ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/
echo "✓ Files uploaded successfully."

# 2. Set permissions, upgrade module on UAT database(s), and restart Odoo service
echo ""
echo "[2/2] Setting permissions, running module upgrade, and restarting Odoo..."
ssh -t ${REMOTE_USER}@${REMOTE_HOST} "
  set -e
  REMOTE_PATH=\"/opt/odoo16/custom/${MODULE_NAME}\"

  echo \"--> Detecting Odoo user, Python interpreter, odoo-bin, and config...\"
  ODOO_USER=\$(ps -eo user:30,args | grep \"[o]doo-bin\" | head -n 1 | tr -s \" \" | cut -d\" \" -f1)
  if [ -z \"\$ODOO_USER\" ]; then
    ODOO_USER=\$(stat -c \"%U\" /opt/odoo16)
  fi
  ODOO_GROUP=\$(stat -c \"%G\" /opt/odoo16)
  echo \"Detected Odoo owner: \${ODOO_USER}:\${ODOO_GROUP}\"

  echo \"--> Cleaning stale __pycache__ files and setting ownership...\"
  sudo find \"\$REMOTE_PATH\" -name \"__pycache__\" -type d -exec rm -rf {} + 2>/dev/null || true
  sudo chown -R \"\${ODOO_USER}:\${ODOO_GROUP}\" \"\$REMOTE_PATH\"

  ODOO_ARGS=\$(ps -eo args | grep \"[o]doo-bin\" | head -n 1 | sed \"s/^ *//\")
  PYTHON_BIN=\$(echo \"\$ODOO_ARGS\" | cut -d\" \" -f1)
  if [ -z \"\$PYTHON_BIN\" ] || [ ! -x \"\$PYTHON_BIN\" ]; then
    for candidate in /opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/venv/bin/python3 /opt/odoo16/.venv/bin/python3 /opt/odoo/venv/bin/python3 /usr/bin/python3; do
      if [ -x \"\$candidate\" ]; then
        PYTHON_BIN=\"\$candidate\"
        break
      fi
    done
  fi

  ODOO_BIN=\$(echo \"\$ODOO_ARGS\" | cut -d\" \" -f2)
  if [ -z \"\$ODOO_BIN\" ] || [ ! -f \"\$ODOO_BIN\" ]; then
    if [ -f /opt/odoo16/odoo-bin ]; then
      ODOO_BIN=/opt/odoo16/odoo-bin
    else
      ODOO_BIN=\$(sudo find /opt /usr /var -name \"odoo-bin\" 2>/dev/null | head -n 1)
    fi
  fi

  CONF_FILE=\$(echo \"\$ODOO_ARGS\" | sed -n \"s/.*-c \([^ ]*\).*/\1/p\")
  if [ -z \"\$CONF_FILE\" ] || [ ! -f \"\$CONF_FILE\" ]; then
    for c in /etc/odoo16.conf /etc/odoo.conf /opt/odoo16/odoo.conf /etc/odoo/odoo.conf; do
      if [ -f \"\$c\" ]; then
        CONF_FILE=\"\$c\"
        break
      fi
    done
  fi

  echo \"Using Python:   \$PYTHON_BIN\"
  echo \"Using odoo-bin: \$ODOO_BIN\"
  echo \"Using config:   \$CONF_FILE\"

  ALL_DBS=\$(sudo -u postgres psql -tAc \"SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres')\" | tr -d \" \r\")
  for db in \$ALL_DBS; do
    HAS_MODULE=\$(sudo -u postgres psql -d \"\$db\" -tAc \"SELECT 1 FROM ir_module_module WHERE name='${MODULE_NAME}' AND state IN ('installed', 'to upgrade')\" 2>/dev/null | tr -d \" \r\" || true)
    if [ \"\$HAS_MODULE\" = \"1\" ]; then
      echo \"--> Upgrading ${MODULE_NAME} on UAT database: \$db ...\"
      sudo -u \"\$ODOO_USER\" -H \"\$PYTHON_BIN\" \"\$ODOO_BIN\" -c \"\$CONF_FILE\" -d \"\$db\" -u ${MODULE_NAME} --stop-after-init --no-http
    fi
  done

  echo \"--> Restarting Odoo service...\"
  SERVICE_NAME=\$(systemctl list-units --type=service --state=running | grep -oE \"odoo[^ ]*\.service\" | head -n 1)
  if [ -n \"\$SERVICE_NAME\" ]; then
    echo \"Restarting service: \$SERVICE_NAME\"
    sudo systemctl restart \"\$SERVICE_NAME\"
    sudo systemctl is-active \"\$SERVICE_NAME\"
  else
    sudo systemctl restart odoo16 || sudo systemctl restart odoo || sudo service odoo restart
  fi
"

echo ""
echo "=========================================================="
echo "  UAT DEPLOYMENT FINISHED SUCCESSFULLY!"
echo "=========================================================="
