# Деплой и эксплуатация

Целевая платформа: любой Linux VPS с Docker (бот) + Vercel (лендинг).

## Первый запуск (VPS)

```bash
git clone <repo> && cd <repo>
cp .env.example .env        # заполнить TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ADMIN_IDS
docker compose up -d --build
docker compose logs -f bot  # убедиться, что "СИСТЕМА активирована"
```

`restart: always` в compose обеспечивает автоперезапуск после падений и ребута сервера
(при условии, что docker daemon включён: `systemctl enable docker`).

## Обновление

```bash
git pull
docker compose up -d --build
```

БД живёт в named volume `bot_data` и переживает пересборку контейнера.

## Бэкапы

- Бот сам делает бэкап каждые `BACKUP_INTERVAL_HOURS` (по умолчанию 6 ч) через
  `VACUUM INTO` — это корректный способ для SQLite в WAL-режиме
  (простое копирование файла даёт битую копию).
- Копии лежат в volume: `/app/data/backups/hunter_YYYYMMDD_HHMMSS.db`,
  хранится последних `BACKUP_KEEP` (по умолчанию 28 ≈ 7 суток).
- **Обязательно** настройте выгрузку каталога бэкапов во внешнее хранилище, например cron на хосте:

```bash
# /etc/cron.daily/bot-backup-offsite
docker cp $(docker compose ps -q bot):/app/data/backups /srv/offsite/bot-backups
# затем rclone/rsync в S3/B2/другой сервер
```

## Восстановление

```bash
docker compose down
docker run --rm -v <project>_bot_data:/data -v /srv/offsite:/backup alpine \
  cp /backup/bot-backups/hunter_<STAMP>.db /data/hunter.db
docker compose up -d
```

После восстановления проверьте `/admin` — числа пользователей должны совпадать с ожидаемыми.

## Ротация секретов

Если токен бота или ключ Gemini мог утечь (репозиторий был публичным с ними в истории):
1. `@BotFather` → `/revoke` → обновить `TELEGRAM_BOT_TOKEN` в `.env`.
2. Google AI Studio → удалить ключ, создать новый → обновить `GEMINI_API_KEY`.
3. `docker compose up -d` для перечитывания `.env`.

## Важно про git-историю

`hunter.db*` удалены из рабочего дерева и добавлены в `.gitignore`, но если они
уже попадали в коммиты — вычистите историю перед публикацией репозитория:

```bash
pip install git-filter-repo
git filter-repo --invert-paths --path hunter.db --path hunter.db-shm --path hunter.db-wal
git push --force
```
