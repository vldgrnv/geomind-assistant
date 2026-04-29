#!/bin/bash
# =================================================================
# Скрипт установки GeoMind Assistant на VPS (Ubuntu 22.04+)
# Запуск: sudo bash deploy/setup.sh
# =================================================================

set -e

APP_DIR="/opt/geomind-assistant"
DOMAIN="geomind.ru"  # ← Заменить на ваш домен

echo "==== 1. Обновление системы ===="
apt update && apt upgrade -y

echo "==== 2. Установка зависимостей ===="
apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git gdal-bin

echo "==== 3. Создание директории ===="
mkdir -p $APP_DIR

echo "==== 4. Копирование проекта ===="
echo "Скопируйте проект в $APP_DIR, затем продолжите:"
echo "  scp -r ./* user@server:$APP_DIR/"
echo "  Или: git clone <repo> $APP_DIR"
echo ""

echo "==== 5. Виртуальное окружение ===="
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==== 6. Настройка .env ===="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.production" "$APP_DIR/.env"
    echo "⚠️  Отредактируйте $APP_DIR/.env — заполните YANDEX_API_KEY и JWT_SECRET"
fi

echo "==== 7. Nginx ===="
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/geomind
ln -sf /etc/nginx/sites-available/geomind /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==== 8. Systemd ===="
cp "$APP_DIR/deploy/geomind.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable geomind
systemctl start geomind

echo "==== 9. SSL (Let's Encrypt) ===="
echo "Для получения SSL-сертификата выполните:"
echo "  sudo certbot --nginx -d $DOMAIN"
echo ""

echo "==== ✅ Готово! ===="
echo "Проверка статуса:  systemctl status geomind"
echo "Логи:             journalctl -u geomind -f"
echo "Сайт:             http://$DOMAIN"
