# Lead Magnet Bot — обзор архитектуры, функций и возможностей

Документ предназначен для загрузки в нейросеть или передачи разработчикам для анализа проекта.

---

## 1. Назначение проекта

**Lead Magnet Bot** — Telegram-бот для раздачи лид-магнитов (чек-листы, ссылки на материалы) с обязательной проверкой подписки на канал. Основные цели:

- Выдача контента только подписчикам канала.
- Создание постов с кнопками в канале (кнопка ведёт в бота с отслеживанием нажатий).
- Настраиваемое приветствие, текст и кнопка «получить чек-лист» + ссылка на лид-магнит.
- Follow-up на следующий день: подписанным — продающий текст и кнопки оплаты; неподписанным — напоминание с кнопкой получения лид-магнита.
- Статистика: пользователи, клики по кнопкам (в канале и в боте).

Технологии: **Python 3.11+**, **python-telegram-bot** (async), **SQLAlchemy** (async), **PostgreSQL** (production) или **SQLite** (DEV_MODE). Деплой: **Railway**.

---

## 2. Структура проекта

```
.
├── bot.py                 # Точка входа: создание Application, /start, регистрация обработчиков, polling
├── config.py              # Конфиг из .env: BOT_TOKEN, ADMIN_USER_IDS, CHANNEL_USERNAME, FOLLOWUP_HOUR, PAYMENT_URL_*
├── database/
│   ├── base_models.py     # Base, User
│   ├── models.py          # ChannelButton, ChannelButtonClick, BotSettings
│   ├── database.py        # Async engine, get_session(), init_db(), PostgreSQL/SQLite
│   └── __init__.py
├── modules/payments/
│   ├── handlers.py        # Обработчики подписки: payment:check_subscription, welcome:get_checklist, follow-up job
│   ├── admin_handlers.py  # Админ-панель, команды, ConversationHandler'ы (add_button, set_channel, set_welcome, set_followup_*)
│   ├── keyboards.py       # get_free_access_keyboard(), get_admin_panel_keyboard()
│   ├── messages.py       # get_free_access_message()
│   ├── settings.py        # get/set welcome, followup_lost, followup_lead из BotSettings
│   ├── subscription.py    # get_or_create_user(), get_subscription_channel(), check_channel_subscription()
│   └── __init__.py
├── services/
│   └── channel_button_service.py  # ChannelButtonService: generate_bot_link(), publish_post_with_button()
└── scripts/
    └── smoke_test_settings.py     # Тест init_db, welcome, followup_lost, followup_lead
```

---

## 3. Архитектура и потоки данных

### 3.1 Запуск

- `bot.py` → `main()`: загрузка конфига, `Application.builder().token().post_init(post_init).build()`.
- `post_init` вызывает `init_db()` — создание таблиц БД.
- Регистрируются: `CommandHandler("start", start_command)`, `register_subscription_handlers()`, `register_admin_handlers()`, глобальный `error_handler`.
- Запуск: `application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)`.

### 3.2 База данных

- **Подключение**: `database/database.py` — `DATABASE_URL` из env; для PostgreSQL подмена `postgres://` → `postgresql+asyncpg://`; при `DEV_MODE=1` и отсутствии URL — SQLite.
- **Сессии**: асинхронный контекст `get_session()` (commit при успехе, rollback при исключении).
- **Модели**:
  - **User** (base_models): id, telegram_id, username, first_name, last_name, registration_date, last_activity.
  - **ChannelButton**: id, channel_id, message_id, post_title, button_text, lead_magnet_type ("bot"|"external"), link, created_at, created_by.
  - **ChannelButtonClick**: id, user_id, telegram_id, button_id, clicked_at, post_id, source (например "channel_button_123", "welcome:get_checklist", "payment:check_subscription").
  - **BotSettings**: id, key, value, updated_at, updated_by — ключ-значение для всех текстов и ссылок бота.

### 3.3 Конфигурация

- **config.py**: `BOT_TOKEN`, `ADMIN_USER_IDS` (список int), `CHANNEL_USERNAME` (fallback канала подписки), `PAYMENT_URL_1/2/3`, `FOLLOWUP_HOUR` (0–23). Валидация: `Config.validate()` — проверка BOT_TOKEN.

---

## 4. Пользовательские сценарии (не админ)

### 4.1 Команда /start без параметров

1. Создание/обновление пользователя в БД.
2. Загрузка приветствия из `get_welcome_settings()` (BotSettings: welcome_text, welcome_button_text, welcome_link).
3. Отправка пользователю текста приветствия и одной inline-кнопки с `callback_data="welcome:get_checklist"`.

### 4.2 Команда /start с параметром (deep link)

- Параметр вида `channel_button_<message_id>` — переход по кнопке из поста канала.
- В БД: поиск/создание User, поиск ChannelButton по message_id, сохранение ChannelButtonClick (source=start_param, button_id, post_id), запись в context: channel_button_id, channel_button_link, channel_button_type.
- Если у кнопки есть link:
  - Проверка подписки `check_channel_subscription(bot, telegram_id, channel)`.
  - Подписан: выдача сообщения «Подписка подтверждена» + кнопка «Получить доступ» (url=link) для external или просто текст для типа bot; очистка user_data от данных кнопки.
  - Не подписан: сообщение «Доступ по подписке» + клавиатура с кнопкой канала и «✅ Я подписался» (callback_data="payment:check_subscription").

### 4.3 Кнопка «Получить чек-лист» (welcome:get_checklist)

- Обработчик: `welcome_get_checklist_callback` в handlers.py.
- Получение канала и welcome-настроек; проверка наличия welcome["link"].
- Создание/обновление User, запись клика ChannelButtonClick (source="welcome_get_checklist").
- Планирование follow-up: `schedule_lead_followup(context, telegram_id)` — JobQueue.run_once на следующий день в FOLLOWUP_HOUR (UTC).
- Проверка подписки. Если не подписан — сообщение «Подписка не найдена» + клавиатура подписки. Если подписан — сообщение «Подписка подтверждена» + кнопка «Получить чек-лист» (url=welcome["link"]).

### 4.4 Кнопка «Я подписался» (payment:check_subscription)

- Обработчик: `check_subscription_callback` в handlers.py.
- Создание/обновление User, запись клика (source="payment_check_subscription").
- Получение канала, вызов `check_channel_subscription()`.
- Не подписан: редактирование сообщения «Подписка не найдена» + клавиатура подписки.
- Подписан: если в context есть channel_button_link (пришли из кнопки канала) — выдача ссылки и очистка user_data; иначе — просто «Подписка подтверждена».

### 4.5 Проверка подписки (subscription.py)

- `get_subscription_channel()`: из BotSettings key="subscription_channel", иначе Config.CHANNEL_USERNAME.
- `check_channel_subscription(bot, telegram_id, channel_username)`: `bot.get_chat_member(chat_id=channel_username, user_id=telegram_id)`. Статус считаем «подписан», если status в (MEMBER, ADMINISTRATOR, CREATOR/OWNER — с учётом совместимости версий библиотеки). При BadRequest (например, бот не админ) — False.

### 4.6 Follow-up на следующий день

- Job: `send_lead_followup_job(context)`; chat_id = telegram_id из job.
- Снова проверка подписки.
- Подписан: `get_followup_lead_settings()` — текст + до 3 кнопок (текст, url); отправка сообщения с кнопками.
- Не подписан: `get_followup_lost_text()` — текст напоминания; клавиатура с одной кнопкой (welcome["button_text"], callback_data="welcome:get_checklist").

---

## 5. Админ-функции

Доступ: `is_admin(telegram_id)` — id входит в Config.ADMIN_USER_IDS.

### 5.1 Команды и входные точки

- `/admin` — показ панели с inline-кнопками (get_admin_panel_keyboard).
- `/add_button` — начало диалога «Создать пост с кнопкой».
- `/set_channel` — настройка канала для проверки подписки (сохраняется в BotSettings subscription_channel).
- `/set_welcome` — пошагово: текст приветствия → текст кнопки → ссылка на лид-магнит.
- `/set_followup_lost` — один шаг: текст follow-up для неподписавшихся.
- `/set_followup_lead` — текст сообщения + по очереди текст/url для кнопок 1–3 (можно пропустить кнопку через «-»).
- `/cancel` — отмена текущего ConversationHandler (add_button, set_channel, set_welcome, set_followup_*).

### 5.2 Админ-панель (inline-кнопки)

- **➕ Создать пост с кнопкой** (admin:add_button) — то же, что /add_button (возврат в меню).
- **📊 Статистика по кнопкам** (admin:button_stats) — список кнопок и количество кликов по каждой.
- **⚙️ Настройки канала** (admin:channel_settings) — экран с текущим каналом и кнопкой «Изменить» → запуск диалога set_channel (admin:start_set_channel через ConversationHandler).
- **💬 Настройки приветствия** (admin:welcome_settings) — краткая сводка (текст кнопки, ссылка задана/нет), кнопка «Изменить приветствие» (admin:start_set_welcome) → тот же поток, что /set_welcome.
- **📩 Follow-up (неподписавшиеся)** (admin:followup_lost_settings) — сводка, кнопка «Изменить текст» (admin:start_set_followup_lost) → поток /set_followup_lost.
- **📩 Follow-up (подписавшиеся)** (admin:followup_lead_settings) — сводка, кнопка «Изменить настройки» (admin:start_set_followup_lead) → поток /set_followup_lead.
- **📝 Список команд** (admin:commands) — вывод списка админ-команд.
- **◀️ Назад** (admin:back) — возврат к панели /admin.

### 5.3 Диалог «Создать пост с кнопкой» (add_button)

Состояния: WAITING_BUTTON_TEXT → WAITING_LEAD_MAGNET_TYPE (inline: button:type:bot / button:type:external) → WAITING_EXTERNAL_LINK (если external) → WAITING_CHANNEL → WAITING_POST_CONTENT (текст или фото+подпись). Используется ChannelButtonService: для типа bot ссылка генерируется как t.me/bot?start=channel_button_<message_id> (message_id получим после публикации — в текущей реализации передаётся заглушка или уже известный id в зависимости от кода). Публикация: `publish_post_with_button()`; сохранение в БД ChannelButton (channel_id, message_id, post_title, button_text, lead_magnet_type, link, created_by).

### 5.4 Настройка канала подписки

Один шаг: ввод @username канала → сохранение в BotSettings key="subscription_channel".

### 5.5 Настройки приветствия (set_welcome)

Три шага подряд: текст приветствия → текст кнопки → ссылка. Сохранение в BotSettings: welcome_text, welcome_button_text, welcome_link.

### 5.6 Настройки follow-up

- **Lost**: один шаг — текст. Ключ BotSettings: followup_lost_text.
- **Lead**: текст сообщения → для каждой из 3 кнопок: текст кнопки, затем url (можно пропустить кнопку, отправив «-»). Ключи: followup_lead_text, followup_lead_btn1_text, followup_lead_btn1_url, … btn3.

---

## 6. Настройки в БД (BotSettings keys)

| Ключ | Описание |
|------|----------|
| subscription_channel | @username канала для проверки подписки |
| welcome_text | Текст приветственного сообщения |
| welcome_button_text | Текст кнопки «получить чек-лист» |
| welcome_link | URL лид-магнита (показывается после проверки подписки) |
| followup_lost_text | Текст follow-up для неподписавшихся |
| followup_lead_text | Текст follow-up для подписавшихся |
| followup_lead_btn1_text, followup_lead_btn1_url | Первая кнопка follow-up (подписан) |
| followup_lead_btn2_text, followup_lead_btn2_url | Вторая кнопка |
| followup_lead_btn3_text, followup_lead_btn3_url | Третья кнопка |

Дефолты и загрузка/сохранение реализованы в modules/payments/settings.py (в т.ч. PAYMENT_URL_1/2/3 из Config как fallback для кнопок lead).

---

## 7. Клавиатуры и сообщения

- **get_free_access_keyboard(channel_username)** — кнопка «Подписаться на канал» (url), «✅ Я подписался» (payment:check_subscription).
- **get_admin_panel_keyboard()** — перечисленные выше inline-кнопки админ-меню.
- **get_free_access_message(channel_username)** — текст про подписку и нажатие «Я подписался».

---

## 8. Сервис кнопок канала

- **ChannelButtonService.generate_bot_link(bot_username, post_id)** — ссылка вида https://t.me/BotUsername?start=channel_button_<post_id>.
- **ChannelButtonService.create_button_keyboard(link, button_text)** — одна inline-кнопка с url.
- **ChannelButtonService.publish_post_with_button(bot, channel_id, post_content, button_text, link, photo_file_id, lead_magnet_type)** — отправка в канал сообщения (текст или фото+подпись) с кнопкой; возврат message_id.

---

## 9. Важные замечания для анализа

- Один экземпляр бота на один токен (иначе конфликт «only one bot instance»).
- При ошибке проверки подписки (например, бот не админ канала) пользователь видит экран «подпишитесь» и может снова нажать «Я подписался».
- Follow-up планируется один раз при нажатии «Получить чек-лист» (welcome:get_checklist); час отправки задаётся FOLLOWUP_HOUR (UTC).
- Все клики (канал, приветствие, проверка подписки) пишутся в channel_button_clicks с разными source для аналитики.
- Редактирование сообщений при проверке подписки может вернуть 400 Bad Request (например, если текст не изменился или произошла ошибка до редактирования); в коде есть обработка и fallback-сообщения.

---

Конец документа.
