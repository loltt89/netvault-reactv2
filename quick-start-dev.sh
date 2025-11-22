#!/bin/bash

# Quick Start Script for Development (Current Machine)
# This script starts the application without full installation

set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "========================================="
echo "  NetVault - Quick Start (Dev Mode)"
echo "========================================="
echo ""

# Check if backend is set up
if [ ! -d "$PROJECT_DIR/backend/venv" ]; then
    echo "Backend not set up. Setting up now..."
    cd "$PROJECT_DIR/backend"

    # Create venv
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install --upgrade pip > /dev/null
    pip install -r requirements.txt > /dev/null

    # Create .env if not exists
    if [ ! -f ".env" ]; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
        ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

        cat > .env <<EOF
SECRET_KEY=$SECRET_KEY
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=sqlite3
DB_NAME=db.sqlite3
ENCRYPTION_KEY=$ENCRYPTION_KEY
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
EOF
    fi

    # Run migrations
    python manage.py migrate

    # Create superuser if not exists
    python manage.py shell <<PYEOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@netvault.local').exists():
    User.objects.create_superuser(
        email='admin@netvault.local',
        password='admin123',
        first_name='Admin',
        last_name='User'
    )
    print('✓ Superuser created')
else:
    print('✓ Superuser already exists')
PYEOF

    echo "✓ Backend setup complete"
fi

# Check if frontend dependencies are installed
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$PROJECT_DIR/frontend"
    npm install > /dev/null 2>&1
    echo "✓ Frontend dependencies installed"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Check if Redis is running (required for Celery and Channels)
if ! pgrep -x redis-server > /dev/null; then
    echo "⚠ Warning: Redis is not running!"
    echo "  Celery and WebSocket features will not work."
    echo "  Start Redis with: sudo systemctl start redis-server"
    echo ""
    read -p "Continue anyway? [y/N]: " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 0
    fi
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID $CELERY_PID $BEAT_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Backend (with Daphne for WebSocket support)
echo ""
echo "Starting Backend server (Daphne ASGI)..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
daphne -b 0.0.0.0 -p 8000 netvault.asgi:application > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"

# Start Celery Worker (for async tasks)
echo "Starting Celery worker..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
celery -A netvault worker -l info > ../logs/celery.log 2>&1 &
CELERY_PID=$!
echo "✓ Celery worker started (PID: $CELERY_PID)"

# Start Celery Beat (for scheduled tasks)
echo "Starting Celery beat scheduler..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
celery -A netvault beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler > ../logs/celery-beat.log 2>&1 &
BEAT_PID=$!
echo "✓ Celery beat started (PID: $BEAT_PID)"

# Wait for backend to start
sleep 3

# Start Frontend
echo "Starting Frontend server..."
cd "$PROJECT_DIR/frontend"
BROWSER=none npm start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "========================================="
echo "  NetVault is running!"
echo "========================================="
echo ""
echo "Frontend:     http://localhost:3000"
echo "Backend API:  http://localhost:8000/api/v1/"
echo "Django Admin: http://localhost:8000/admin/"
echo ""
echo "Default credentials:"
echo "  Email:    admin@netvault.local"
echo "  Password: admin123"
echo ""
echo "Logs:"
echo "  Backend:     tail -f logs/backend.log"
echo "  Celery:      tail -f logs/celery.log"
echo "  Celery Beat: tail -f logs/celery-beat.log"
echo "  Frontend:    tail -f logs/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for processes
wait $BACKEND_PID $CELERY_PID $BEAT_PID $FRONTEND_PID
