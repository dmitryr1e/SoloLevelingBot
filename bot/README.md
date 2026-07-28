# SoloLevelingBot

Telegram-бот-геймификация в духе Solo Leveling: реальная жизнь как RPG.
Стек: aiogram 3, SQLite (aiosqlite, WAL), APScheduler, Gemini API, Telegram Stars.

## Запуск

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="..."   # у @BotFather
export GEMINI_API_KEY="..."       # aistudio.google.com
export ADMIN_IDS="123456789"      # опционально: твой Telegram ID
python -m bot.main
```

## Механики

- Ежедневные квесты из пула 60 шт. (спорт / учёба / дисциплина) + личные квесты
- XP, уровни, ранги E→S, HP; провал дня бьёт по HP, ноль HP — «смерть» (минус уровень)
- Серии (стрики), заморозки серий, вехи серии на 3/7/14/30/60/100 дней с бонусами
- Врата: случайный бонус-квест дня повышенной сложности (шанс 25%)
- Босс недели: общий рейд всего сервера, урон = заработанный XP
- ИИ-отчёты (Gemini): оценка дня, начисление XP и характеристик
- Ачивки, рейтинг, карточка охотника (генерация PNG), рефералы
- Премиум «Монарх» через Telegram Stars (`/premium`, `/paysupport`)

## Тесты

```bash
python tests/test_smoke.py
```

## Деплой

Любой VPS / Railway / Fly.io. Бот работает через long polling, вебхуки не нужны.
База — файл SQLite (`solo.db` рядом с процессом); для бэкапа достаточно копировать файл.
