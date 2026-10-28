#!/bin/bash
set -e

REMOTE_USER="administrator"
REMOTE_HOST="10.1.0.53"
REMOTE_PATH="/opt/odoo16/custom/project_report"
DB_NAME="digital"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOCAL_BACKUP_DIR="./backups/prod_project_report_backup_${TIMESTAMP}"

echo "=========================================================="
echo "  PRODUCTION DEPLOYMENT: project_report"
echo "  Target Host: ${REMOTE_HOST}"
echo "  Remote Path: ${REMOTE_PATH}"
echo "  Database:    ${DB_NAME}"
echo "=========================================================="

# 1. Create timestamped backup on Production server
echo ""
echo "[1/4] Creating server-side backup on Production..."
ssh -t ${REMOTE_USER}@${REMOTE_HOST} "sudo cp -r ${REMOTE_PATH} ${REMOTE_PATH}_backup_${TIMESTAMP}"
echo "✓ Server-side backup created at: ${REMOTE_PATH}_backup_${TIMESTAMP}"

# 2. Download Production copy locally before making any changes
echo ""
echo "[2/4] Downloading current Production code to local machine..."
mkdir -p "${LOCAL_BACKUP_DIR}"
scp -r ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/* "${LOCAL_BACKUP_DIR}/"
echo "✓ Local backup saved to: ${LOCAL_BACKUP_DIR}"

# 3. Upload validated changes to Production
echo ""
echo "[3/4] Uploading updated project_report files to Production..."
scp -r ./custom/project_report/* ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/
echo "✓ Files uploaded successfully."

# 4. Set permissions, upgrade module, and restart Odoo service
echo ""
echo "[4/4] Setting permissions, running module upgrade, and restarting Odoo..."
ssh -t ${REMOTE_USER}@${REMOTE_HOST} "
  echo '--> Setting file ownership to odoo:odoo...'
  sudo chown -R odoo:odoo ${REMOTE_PATH}

  echo '--> Upgrading project_report on database ${DB_NAME}...'
  if [ -f /etc/odoo.conf ]; then
    CONF_FILE=/etc/odoo.conf
  elif [ -f /etc/odoo16.conf ]; then
    CONF_FILE=/etc/odoo16.conf
  elif [ -f /opt/odoo16/odoo.conf ]; then
    CONF_FILE=/opt/odoo16/odoo.conf
  else
    CONF_FILE=\$(sudo find /etc /opt/odoo16 -name '*.conf' 2>/dev/null | grep -E 'odoo' | head -n 1)
  fi
  echo \"Using config file: \$CONF_FILE\"

  sudo su - odoo -s /bin/bash -c \"python3 /opt/odoo16/odoo-bin -c \$CONF_FILE -d ${DB_NAME} -u project_report --stop-after-init\"

  echo '--> Restarting Odoo service...'
  sudo systemctl restart odoo || sudo systemctl restart odoo16 || sudo service odoo restart

  echo '--> Checking service status...'
  sudo systemctl is-active odoo 2>/dev/null || sudo systemctl is-active odoo16 2>/dev/null || true
"

echo ""
echo "=========================================================="
echo "  DEPLOYMENT FINISHED SUCCESSFULLY!"
echo "  - Remote backup: ${REMOTE_PATH}_backup_${TIMESTAMP}"
echo "  - Local backup:  ${LOCAL_BACKUP_DIR}"
echo "=========================================================="

