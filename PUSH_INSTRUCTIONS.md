# Инструкция по пушу на GitHub

## Вариант 1: Если репозиторий уже создан на GitHub

Замените `ваш-username` и `название-репозитория` на реальные значения:

```bash
cd "/Users/aleksandrdg/Projects/МОИ БОТЫ/Лид-магнит за подписку"
git remote add origin https://github.com/ваш-username/название-репозитория.git
git branch -M main
git push -u origin main
```

## Вариант 2: Если ваш GitHub username - aleksandrdggpt-tech

И репозиторий называется `lead-magnet-bot`:

```bash
cd "/Users/aleksandrdg/Projects/МОИ БОТЫ/Лид-магнит за подписку"
git remote add origin https://github.com/aleksandrdggpt-tech/lead-magnet-bot.git
git branch -M main
git push -u origin main
```

## Если репозиторий еще не создан

1. Перейдите на https://github.com/new
2. Создайте новый репозиторий (например, `lead-magnet-bot`)
3. НЕ добавляйте README, .gitignore или лицензию
4. Скопируйте URL репозитория
5. Выполните команды выше с вашим URL
