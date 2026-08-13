# NetVault - Network Device Configuration Backup System

Полнофункциональное веб-приложение для резервного копирования конфигураций сетевого оборудования.

> ⚠️ **ВНИМАНИЕ: Проект находится на этапе активного тестирования!**
>
> Данное ПО предоставляется "как есть" без каких-либо гарантий. Автор не несёт ответственности за любые последствия использования данного программного обеспечения, включая, но не ограничиваясь: потерю данных, сбои в работе production-систем, простои сетевого оборудования и прочие инциденты.
>
> **Используйте на свой страх и риск. Рекомендуется тестирование в изолированной среде перед внедрением.**

## Технологии

- **Backend:** Django + Django REST Framework
- **Frontend:** React + TypeScript
- **Database:** MariaDB
- **Authentication:** JWT tokens
- **OS:** Ubuntu Server 20.04 LTS

## Особенности

### Аутентификация и безопасность
- JWT токены с автоматическим обновлением
- Двухфакторная аутентификация (2FA/TOTP), либо WebAuthn/passkeys как альтернативный второй фактор
- LDAP/Active Directory интеграция
- SAML SSO поддержка (Azure AD, Okta, и др.)
- Шифрование credentials и backup-ов (AES-256)
- Управление пользователями и ролями (Administrator, Operator, Auditor, Viewer)
- Group/tag-scoped RBAC — пользователя можно ограничить подмножеством устройств (по тегам/критичности), а не только ролью
- Полный audit logging всех действий

### Резервное копирование
- **Автоматическое резервное копирование по расписанию (Celery Beat)**
  - Поддержка расписаний: hourly, daily, weekly
  - Полное управление через Web UI (расписания, устройства, статистика)
  - Параллельное выполнение бекапов (настраиваемое количество воркеров)
- Поддержка SSH/Telnet подключений
- Настраиваемые команды бекапа для каждого вендора
- Автоматическое определение изменений конфигурации
- Retention policy (автоматическое удаление старых бекапов)
- CSV импорт устройств
- Bulk-действия на устройствах (массовый запуск бэкапа, массовое редактирование тегов)

### Соответствие требованиям (Compliance)
- Правила compliance-проверки конфигураций (по тегам/критичности устройств)
- Автоматическая проверка конфигурации сразу после успешного бэкапа
- Журнал нарушений (violations) с привязкой к устройству и правилу

### Мониторинг и уведомления
- **Гибридная проверка статуса устройств (экономия VTY линий)**
  - Level 1: Быстрая TCP проверка порта (не занимает VTY)
  - Level 2: SSH проверка только при недоступности TCP
  - Экономия ~95% VTY линий!
- **Email, Telegram и generic webhook уведомления**
  - Настраиваемые правила уведомлений (по событию, устройству/тегам, каналу)
  - Тестирование настроек прямо из UI
- Виджет "устаревшие бэкапы" на дашборде + дайджест по расписанию
- WebSocket real-time логи выполнения бекапов
- Device health check с настраиваемым интервалом

### Интерфейс
- Monaco Editor для просмотра конфигураций с подсветкой синтаксиса
- Diff viewer для сравнения версий конфигураций
- 5 готовых тем оформления (Industrial, Neumorphism, Isometric, Glassmorphism, Blueprint)
- Многоязычность (Русский, Английский, Казахский)
- Responsive design для мобильных устройств

### Настройки системы (System Settings UI)
- Email SMTP настройки с тестированием
- Telegram Bot интеграция
- Настройки уведомлений
- LDAP/Active Directory конфигурация
- SAML SSO конфигурация
- JWT сессии (время жизни токенов)
- Redis подключение
- Backup параметры (retention, workers)
- Device check настройки (интервал, таймауты)
- Управление vendors и device types

## Быстрая установка (рекомендуется)

### Установка из GitHub

```bash
# Установка git (если не установлен)
sudo apt update && sudo apt install -y git

# Клонирование репозитория
git clone https://github.com/loltt89/netvault-react.git
cd netvault-react

# Запуск установщика (требует root)
sudo ./install.sh
```

### Установка из архива

```bash
# Распаковка архива
tar -xzf netvault-installer.tar.gz
cd netvault-react

# Запуск установщика (требует root)
sudo ./install.sh
```

### Что делает install.sh:

- ✅ Устанавливает все зависимости (Python, MariaDB, Redis, Nginx)
- ✅ Создаёт базу данных и пользователя
- ✅ Настраивает Python virtual environment
- ✅ Генерирует безопасные ключи шифрования
- ✅ Создаёт администратора системы
- ✅ Настраивает systemd сервисы (backend, celery worker, celery beat)
- ✅ Конфигурирует Nginx (HTTP или HTTPS)
- ✅ Поддержка Let's Encrypt, custom или self-signed сертификатов
- ✅ Настраивает firewall (UFW)

### Опции SSL/HTTPS:

1. **Let's Encrypt** - автоматический бесплатный сертификат
2. **Custom certificate** - свои сертификаты
3. **Self-signed** - для тестирования

---

## Ручная установка

### 1. Системные требования

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm mariadb-server libmariadb-dev redis-server
```

### 2. Настройка MariaDB

```bash
sudo mysql_secure_installation

# Создание базы данных
sudo mysql -u root -p
```

В MySQL консоли:

```sql
CREATE DATABASE netvault CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'netvault_user'@'localhost' IDENTIFIED BY 'netvault_password';
GRANT ALL PRIVILEGES ON netvault.* TO 'netvault_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Backend Setup

```bash
cd backend

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Копирование и настройка .env файла
cp .env.example .env
# Отредактируйте .env файл и установите правильные значения

# Создание миграций и применение
python manage.py makemigrations
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Создание директории для логов
mkdir -p logs

# Запуск сервера
python manage.py runserver 0.0.0.0:8000
```

### 4. Frontend Setup

```bash
cd ../frontend

# Установка зависимостей
npm install

# Запуск dev сервера
npm start
```

Frontend будет доступен по адресу: http://localhost:3000
Backend API: http://localhost:8000/api/v1/

## API Endpoints

### Authentication

- `POST /api/v1/token/` - Получение JWT токена (логин)
- `POST /api/v1/token/refresh/` - Обновление access токена
- `POST /api/v1/auth/register/` - Регистрация нового пользователя
- `POST /api/v1/auth/logout/` - Выход из системы

### Users

- `GET /api/v1/users/me/` - Получить профиль текущего пользователя
- `PATCH /api/v1/users/update_profile/` - Обновить профиль
- `POST /api/v1/users/change_password/` - Изменить пароль
- `POST /api/v1/users/enable_2fa/` - Включить 2FA
- `POST /api/v1/users/verify_2fa/` - Подтвердить 2FA
- `POST /api/v1/users/disable_2fa/` - Отключить 2FA

## Структура проекта

```
netvault-react/
├── backend/
│   ├── accounts/           # Пользователи, аутентификация, SAML/LDAP
│   ├── devices/            # Устройства, SSH/Telnet, SSRF/командные guard'ы
│   ├── backups/            # Резервное копирование, retention, Celery-задачи
│   ├── notifications/      # Email/Telegram уведомления
│   ├── core/                # Общая инфраструктура: SystemSettings, dashboard,
│   │                         # health checks, шифрование, distributed locks
│   ├── netvault/           # Django-проект: settings.py, urls.py, celery.py, asgi/wsgi
│   ├── manage.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/     # React компоненты
│   │   ├── services/       # API сервисы
│   │   ├── contexts/       # React Context
│   │   ├── hooks/          # Custom hooks
│   │   ├── pages/          # Страницы
│   │   ├── styles/         # Стили и темы
│   │   ├── types/          # TypeScript типы
│   │   └── utils/          # Утилиты
│   ├── package.json
│   └── tsconfig.json
└── README.md
```

## Безопасность

1. **Шифрование credentials:** Все пароли устройств хранятся зашифрованными с использованием Fernet (AES-256)
2. **Шифрование backup-ов:** Конфигурации шифруются перед сохранением в БД
3. **JWT токены:** Безопасная аутентификация с автоматическим обновлением токенов
4. **2FA:** Опциональная двухфакторная аутентификация через TOTP
5. **Audit logging:** Полное логирование всех действий пользователей
6. **CORS:** Правильная настройка CORS для безопасной работы API

## Разработка

### Backend

```bash
cd backend
source venv/bin/activate

# Запуск dev сервера
python manage.py runserver

# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск shell
python manage.py shell
```

### Frontend

```bash
cd frontend

# Запуск dev сервера
npm start

# Сборка для production
npm run build

# Запуск тестов
npm test
```

## Production Deployment

`install.sh` делает всё это автоматически и это рекомендуемый способ (см.
"Быстрая установка" выше) — раздел ниже описывает, что именно он настраивает,
на случай ручной установки или отладки конкретного сервиса.

### Backend (systemd services)

Приложение использует **ASGI (Daphne)**, а не WSGI/gunicorn — это обязательно,
поскольку real-time логи бэкапов идут через Django Channels по WebSocket
(`/ws/`), а WSGI-сервер их не обслужит. Помимо самого backend'а нужны ещё три
сервиса — без Celery worker/beat запланированные бэкапы просто никогда не
выполнятся.

`/etc/systemd/system/netvault-backend.service`:
```ini
[Unit]
Description=NetVault Django Backend (ASGI with Daphne)
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/netvault
Environment="PATH=/opt/netvault/venv/bin"
ExecStart=/opt/netvault/venv/bin/daphne -b 0.0.0.0 -p 8000 netvault.asgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/netvault-celery-worker.service`:
```ini
[Unit]
Description=NetVault Celery Worker
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/netvault
Environment="PATH=/opt/netvault/venv/bin"
ExecStart=/opt/netvault/venv/bin/celery -A netvault worker --loglevel=info --concurrency=10
ExecStop=/bin/kill -TERM $MAINPID
TimeoutStopSec=300
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/netvault-celery-beat.service` (runs scheduled backups,
retention policies, and stale-backup cleanup — see `netvault/celery.py`
for the full schedule):
```ini
[Unit]
Description=NetVault Celery Beat (Scheduler)
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/netvault
Environment="PATH=/opt/netvault/venv/bin"
ExecStart=/opt/netvault/venv/bin/celery -A netvault beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
ExecStop=/bin/kill -TERM $MAINPID
TimeoutStopSec=30
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/netvault-flower.service` (optional — Celery task
monitoring UI, proxied at `/flower/` behind the same admin IP whitelist as
`/admin/`):
```ini
[Unit]
Description=NetVault Flower (Celery Monitoring)
After=network.target redis.service netvault-celery-worker.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/netvault
Environment="PATH=/opt/netvault/venv/bin"
ExecStart=/opt/netvault/venv/bin/celery -A netvault flower --port=5555 --address=127.0.0.1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now netvault-backend netvault-celery-worker netvault-celery-beat netvault-flower
```

### Frontend + nginx

```bash
cd frontend
npm run build

# install.sh serves directly from frontend_build — no separate /var/www copy needed
sudo cp -r build/* /opt/netvault/frontend_build/
```

Nginx (trimmed to the essentials — `install.sh` also adds gzip, static asset
caching, security headers, and an IP whitelist on `/admin/` and `/flower/`):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /opt/netvault/frontend_build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Real-time backup logs — needs the WebSocket upgrade headers, a plain
    # proxy_pass like /api/ above is not enough for this location.
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location /media/ {
        alias /opt/netvault/media/;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## Third-Party Software

NetVault использует следующие сторонние компоненты:

### libssh
- **Назначение:** legacy SSH-фолбэк (`backend/tools/netvault-ssh/`) — собственный C-инструмент
  (`netvault-ssh.c`), связанный с libssh, используется когда Paramiko не может подключиться
  (в частности, устройства с SSH v1 или устаревшими алгоритмами KEX)
- **Лицензия:** GNU Lesser General Public License v2.1 (LGPL-2.1)
- **Сайт:** https://www.libssh.org/
- **Бандл:** в репозитории скомпилированы и подключаются динамически две версии —
  `lib/libssh.so.4.4.4` (libssh 0.7.7, для SSH v1 / устаревших алгоритмов) и
  `lib-modern/libssh.so.4.9.6` (libssh 0.10.6, современные алгоритмы). Исходный код
  libssh не модифицирован; полные исходники соответствующих версий доступны на
  сайте проекта.

libssh используется только как fallback (≈5% подключений) — основной путь подключения
по SSH/Telnet идёт через Paramiko (см. `backend/devices/connection.py`).

## Лицензия

MIT License

## Поддержка

Для вопросов и поддержки создайте issue в репозитории проекта.
