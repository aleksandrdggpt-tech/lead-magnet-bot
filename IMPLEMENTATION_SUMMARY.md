# Сводка изменений: воронка в BotSettings и цепочка follow-up

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `database/models.py` | Поле `BotSettings.value`: `String(500)` → `Text` (длинные тексты). |
| `modules/payments/settings.py` | Универсальные `get_setting`/`set_setting`; новые ключи (welcome_btn_text, followup_enabled, fup_lost_text, fup1/2/3_lead_text, diag_selection_text, diag1/2/3_price_btn, diag1/2/3_url). Геттеры: `get_welcome_settings(session?)`, `get_followup_enabled(session?)`, `get_followup_lost_text(session?)`, `get_followup_texts(session?)`, `get_diag_selection_settings(session?)`. Обратная совместимость: welcome_button_text, followup_lost_text. |
| `modules/payments/handlers.py` | Перед планированием follow-up проверяется `get_followup_enabled()`; планируется цепочка из 3 шагов (день+1, день+2, день+3). В job в начале проверка `followup_enabled`; подписанным отправляется fup1/fup2/fup3 текст + кнопка «Выбрать тип диагностики» (`followup:choose_diagnostic`). Добавлен обработчик `followup_choose_diagnostic_callback`: отправка текста и трёх кнопок из `get_diag_selection_settings()`. Успешная выдача чек-листа использует `welcome["button_text"]` для кнопки. |
| `modules/payments/keyboards.py` | `get_admin_panel_keyboard(followup_enabled=True)`: добавлена кнопка переключателя follow-up (ВКЛ/ВЫКЛ) и параметр состояния. |
| `modules/payments/admin_handlers.py` | Импорт `get_followup_enabled`, `set_followup_enabled`. При показе админ-панели и «Назад» передаётся `followup_enabled` в клавиатуру. Новый callback `admin_toggle_followup_callback` (pattern `admin:toggle_followup`): переключение и сохранение `followup_enabled`, обновление сообщения. |
| `scripts/init_bot_settings_from_db.py` | **Новый скрипт.** Одноразовая инициализация недостающих ключей BotSettings русскими текстами по умолчанию (приветствие, fup_lost, fup1/2/3_lead, diag_selection, кнопки и URL диагностик). Запуск: `PYTHONPATH=. python scripts/init_bot_settings_from_db.py`. |
| `scripts/smoke_test_settings.py` | Проверка наличия ключей из спецификации и вызовов `get_welcome_settings`, `get_followup_enabled`, `get_followup_texts`, `get_diag_selection_settings`, а также legacy `get_followup_lead_settings`. |

## Основные изменения поведения

1. **Единый источник текстов** — все тексты и ссылки воронки (приветствие, follow-up lost, fup1/fup2/fup3, выбор диагностики) хранятся и редактируются в таблице `BotSettings`.
2. **Follow-up включается/выключается** — флаг `followup_enabled` в БД; переключатель в админ-панели; при выключении уже запланированные job’ы при срабатывании не отправляют сообщения.
3. **Цепочка из трёх напоминаний** — при нажатии «Получить чек-лист» планируются три сообщения (день+1, день+2, день+3); каждое с текстом из fup1_lead_text / fup2_lead_text / fup3_lead_text и кнопкой «Выбрать тип диагностики».
4. **Экран выбора диагностики** — по нажатию «Выбрать тип диагностики» отправляется сообщение с текстом и тремя URL-кнопками из `get_diag_selection_settings()` (diag_selection_text, diag1/2/3 price_btn и url).
5. **Обратная совместимость** — сохранены ключи `welcome_button_text`, `followup_lost_text` и legacy followup_lead (для админ-диалогов); геттеры читают и новые, и старые ключи.

## Запуск после деплоя

1. Один раз выполнить миграцию настроек:  
   `PYTHONPATH=. python scripts/init_bot_settings_from_db.py`  
   (в окружении с PostgreSQL, например на Railway или локально с DATABASE_URL).
2. При необходимости проверить настройки:  
   `PYTHONPATH=. python scripts/smoke_test_settings.py`.
