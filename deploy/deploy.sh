#!/bin/bash
# ============================================================
# デプロイスクリプト（更新時に使用）
# 使い方: bash deploy.sh
# ============================================================
set -euo pipefail

APP_NAME="eikaiwa"
APP_DIR="/var/www/${APP_NAME}"
APP_USER="www-data"
REPO_URL="https://github.com/moaimoaimoai/eikaiwa-backend.git"
BRANCH="main"

echo "=== [1/5] 最新コードを取得 ==="
if [ ! -d "${APP_DIR}/.git" ]; then
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
else
    sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch origin
    sudo -u "${APP_USER}" git -C "${APP_DIR}" reset --hard "origin/${BRANCH}"
fi

echo "=== [2/5] 依存パッケージの更新 ==="
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "=== [3/5] マイグレーション ==="
sudo bash -c "
    set -a
    source /etc/eikaiwa.env
    set +a
    cd ${APP_DIR}
    ./venv/bin/python manage.py migrate --noinput
"

echo "=== [4/5] 静的ファイルの収集 ==="
sudo bash -c "
    set -a
    source /etc/eikaiwa.env
    set +a
    cd ${APP_DIR}
    ./venv/bin/python manage.py collectstatic --noinput
"

echo "=== [5/5] Gunicorn の再起動 ==="
systemctl restart "${APP_NAME}"
systemctl status "${APP_NAME}" --no-pager

echo "=== デプロイ完了 ==="
