# NetVault Monitoring Stack

Prometheus + Grafana для мониторинга NetVault.

## Быстрый старт

```bash
cd monitoring
docker-compose up -d
```

## Доступ

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - Логин: `admin`
  - Пароль: `admin`

## Эндпоинты API

| Endpoint | Описание |
|----------|----------|
| `/metrics` | Prometheus метрики |
| `/api/v1/health/` | Базовый health check |
| `/api/v1/health/detailed/` | Детальный health check |
| `/api/v1/health/ready/` | Kubernetes readiness probe |
| `/api/v1/health/live/` | Kubernetes liveness probe |

## Метрики Django

- `django_http_requests_total_by_method_total` - Количество запросов по методу
- `django_http_responses_total_by_status_total` - Количество ответов по статусу
- `django_http_requests_latency_seconds` - Время ответа
- `django_db_execute_total` - Запросы к БД
- `django_db_execute_many_total` - Batch запросы к БД

## Алерты

Настроены следующие алерты:

1. **NetVaultAPIDown** - API недоступен более 1 минуты
2. **NetVaultHighErrorRate** - Более 10% ошибок 5xx
3. **NetVaultSlowResponses** - P95 латентность > 2 секунд
4. **HighMemoryUsage** - RAM > 90%
5. **HighCPUUsage** - CPU > 90%
6. **DiskSpaceLow** - Диск < 10%

## Настройка для продакшена

1. Измените `host.docker.internal` на IP вашего сервера в `prometheus/prometheus.yml`
2. Измените пароль Grafana в `docker-compose.yml`
3. Настройте Alertmanager для отправки уведомлений
