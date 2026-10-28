#!/bin/bash
set -e

REMOTE_USER="administrator"
REMOTE_HOST="10.1.0.53"
REMOTE_PATH="/opt/odoo16/custom/project_report"
DB_NAME="digital"

echo "=========================================================="
echo "  EMERGENCY ROLLBACK: project_report on Production (10.1.0.53)"
echo "=========================================================="

echo "Available backups on Production server:"
ssh -t ${REMOTE_USER}@${REMOTE_HOST} "ls -ld ${REMOTE_PATH}_backup_*"

read -p "Enter the full path of the backup to restore: " BACKUP_PATH

if [ -z "$BACKUP_PATH" ]; then
  echo "No backup path provided. Aborting rollback."
  exit 1
fi

ssh -t ${REMOTE_USER}@${REMOTE_HOST} "
  echo '--> Stopping Odoo service...'
  sudo systemctl stop odoo || sudo systemctl stop odoo16 || true

  echo '--> Restoring from backup: $BACKUP_PATH...'
  sudo rm -rf ${REMOTE_PATH}
  sudo cp -r ${BACKUP_PATH} ${REMOTE_PATH}
  sudo chown -R odoo:odoo ${REMOTE_PATH}

  echo '--> Re-running module upgrade with restored code...'
  if [ -f /etc/odoo.conf ]; then
    CONF_FILE=/etc/odoo.conf
  elif [ -f /etc/odoo16.conf ]; then
    CONF_FILE=/etc/odoo16.conf
  elif [ -f /opt/odoo16/odoo.conf ]; then
    CONF_FILE=/opt/odoo16/odoo.conf
  else
    CONF_FILE=\$(sudo find /etc /opt/odoo16 -name '*.conf' 2>/dev/null | grep -E 'odoo' | head -n 1)
  fi

  sudo su - odoo -s /bin/bash -c \"python3 /opt/odoo16/odoo-bin -c \$CONF_FILE -d ${DB_NAME} -u project_report --stop-after-init\"

  echo '--> Restarting Odoo service...'
  sudo systemctl start odoo || sudo systemctl start odoo16 || sudo service odoo start

  echo '--> Service status:'
  sudo systemctl is-active odoo 2>/dev/null || sudo systemctl is-active odoo16 2>/dev/null || true
"

echo "=========================================================="
echo "  ROLLBACK COMPLETED!"
echo "=========================================================="

