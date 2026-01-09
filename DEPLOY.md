# Инструкция по деплою на Railway

## Подготовка

1. **Создайте .env файл** (скопируйте из `env.example`):
   ```bash
   cp env.example .env
   ```
   
2. **Заполните переменные окружения в .env**:
   - `BOT_TOKEN` - получите у @BotFather в Telegram
   - `ADMIN_USER_IDS` - ваш Telegram ID (узнайте у @userinfobot), можно несколько через запятую
   - `CHANNEL_USERNAME` - username канала для проверки подписки (например: @TaktikaKutuzova)
   - `DATABASE_URL` - для локальной разработки можно не указывать (используйте `DEV_MODE=1`)
   - `DEV_MODE=0` - для Railway установите в 0 (будет использоваться PostgreSQL)

## Деплой на Railway

### Шаг 1: Создайте аккаунт и проект на Railway

1. Перейдите на [railway.app](https://railway.app)
2. Войдите через GitHub
3. Нажмите "New Project"
4. Выберите "Deploy from GitHub repo"

### Шаг 2: Подключите репозиторий

1. Если репозиторий еще не на GitHub:
   ```bash
   # Создайте репозиторий на GitHub
   # Затем выполните:
   git remote add origin https://github.com/ваш-username/ваш-репозиторий.git
   git branch -M main
   git push -u origin main
   ```

2. В Railway выберите ваш репозиторий

### Шаг 3: Добавьте PostgreSQL базу данных

1. В проекте Railway нажмите "+ New"
2. Выберите "Database" → "Add PostgreSQL"
3. Railway автоматически создаст переменную `DATABASE_URL`

### Шаг 4: Настройте переменные окружения

В настройках проекта Railway (Settings → Variables) добавьте:

- `BOT_TOKEN` - токен вашего бота от @BotFather
- `ADMIN_USER_IDS` - ваш Telegram ID (например: `123456789`)
- `CHANNEL_USERNAME` - username канала (например: `@TaktikaKutuzova`)
- `DEV_MODE` - установите в `0` (для production)

**Важно:** `DATABASE_URL` будет установлен автоматически Railway после добавления PostgreSQL.

### Шаг 5: Настройте деплой

1. В настройках сервиса (Settings → Deploy):
   - **Root Directory:** `.` (корень проекта)
   - **Build Command:** (оставьте пустым, Railway определит автоматически)
   - **Start Command:** `python bot.py`

2. Railway автоматически определит Python из `requirements.txt` и `runtime.txt`

### Шаг 6: Деплой

1. Railway автоматически начнет деплой после пуша в GitHub
2. Или нажмите "Deploy" вручную
3. Следите за логами в разделе "Deployments"

## Проверка работы

1. После успешного деплоя бот должен запуститься
2. Проверьте логи в Railway (Deployments → View Logs)
3. Отправьте `/start` боту в Telegram
4. Попробуйте команду `/admin` (если вы в списке админов)

## Важные замечания

1. **Бот должен быть администратором канала** для работы с кнопками
2. Для проверки подписки бот должен иметь права администратора в канале
3. После первого деплоя база данных будет создана автоматически
4. Railway предоставляет бесплатный план с ограничениями (500 часов в месяц)

## Обновление бота

После изменений в коде:

```bash
git add .
git commit -m "Описание изменений"
git push origin main
```

Railway автоматически задеплоит новую версию.

## Локальная разработка

Для локальной разработки:

1. Создайте `.env` файл из `env.example`
2. Установите `DEV_MODE=1` для использования SQLite
3. Установите зависимости: `pip install -r requirements.txt`
4. Запустите: `python bot.py`
