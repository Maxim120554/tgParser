Код для парсинга тг каналов (список каналов должен лежать в корне проекта в файле channels.txt)
каналы указывать ссылкой
t.me/ai_newz

установить зависимости 
pip install -r requirements.txt

запустить в режиме парсинга последних N сообщений с указанных каналов
python main.py fetch

в корень проекта положить файл .env с приватными данными

TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PROXY_SECRET=

QDRANT_API_KEY=
