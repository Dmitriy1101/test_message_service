
### Для работы необходим `.env` файл вкорне проекта:
```
SECRET_KEY='Твой ключь Django'
DEBUG='True'
DB_HOST='ip базы данных postgresql'
POSTGRES_DB='имя базы'
POSTGRES_USER='пользователь базы'
POSTGRES_PASSWORD='пароль базы'
TELEGRAM_BOT_TOKEN='Токен телеграм бота'
EMAIL_HOST='smtp.yandex.ru' # Далее данные для email рассылки, я использовал яндекс
EMAIL_PORT='465'
EMAIL_USE_TLS='False'
EMAIL_USE_SSL='True'
EMAIL_HOST_USER='яндекс почта для отправки'
EMAIL_HOST_PASSWORD='яндекс парольприложения'
DEFAULT_FROM_EMAIL='почта отправителя' 
```

### Я руководствовался: 
 - задачами ТЗ и не создавал эндпойнт для создания пользователя, так как не "боевой" проект для заполнения данных используй аминку сайта.
 - Для запуска запускай сборку Docker: `docker compose up -d`
 - Примени миграции `docker compose run --rm web-app sh -c "python manage.py migrate"`
 - После запуска не забудь создать суперпользователя для админки: `docker compose run --rm web-app sh -c "python manage.py createsuperuser"`

### Запуск тесов:
 - `python -m dotenv run -- pytest`
 
