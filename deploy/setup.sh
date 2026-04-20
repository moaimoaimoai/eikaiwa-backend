#!/bin/bash
# ============================================================
# EC2 初回セットアップスクリプト
# 使い方: sudo bash setup.sh
# ============================================================
set -euo pipefail

APP_NAME="eikaiwa"
APP_DIR="/var/www/${APP_NAME}"
APP_USER="www-data"
PYTHON_VERSION="python3.11"

echo "=== [1/7] パッケージのインストール ==="
apt-get update -y
apt-get install -y \
    ${PYTHON_VERSION} \
    ${PYTHON_VERSION}-venv \
    ${PYTHON_VERSION}-dev \
    python3-pip \
    git \
    nginx \
    postgresql-client \
    libpq-dev \
    build-essential

echo "=== [2/7] アプリディレクトリの作成 ==="
mkdir -p "${APP_DIR}"
chown "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "=== [3/7] Python 仮想環境の作成 ==="
if [ ! -d "${APP_DIR}/venv" ]; then
    sudo -u "${APP_USER}" ${PYTHON_VERSION} -m venv "${APP_DIR}/venv"
fi

echo "=== [4/7] 依存パッケージのインストール ==="
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "=== [5/7] Gunicorn systemd サービスの設定 ==="
cp "$(dirname "$0")/gunicorn.service" "/etc/systemd/system/${APP_NAME}.service"
systemctl daemon-reload
systemctl enable "${APP_NAME}"

echo "=== [6/7] Nginx の設定 ==="
cp "$(dirname "$0")/nginx.conf" "/etc/nginx/sites-available/${APP_NAME}"
ln -sf "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
nginx -t && systemctl reload nginx

echo "=== [7/7] 静的ファイルの収集 & マイグレーション ==="
sudo -u "${APP_USER}" bash -c "
    source /etc/eikaiwa.env
    cd ${APP_DIR}
    ./venv/bin/python manage.py migrate --noinput
    ./venv/bin/python manage.py collectstatic --noinput
"

systemctl start "${APP_NAME}"
echo "=== セットアップ完了 ==="
echo "サービス状態: $(systemctl is-active ${APP_NAME})"
