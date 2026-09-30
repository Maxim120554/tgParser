import hashlib
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.errors import ChannelPrivateError, FloodWaitError
from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate as ConnectionTcpMTProxy
from qdrant_client.models import PointStruct
from loguru import logger
# from config import settings
from settings import settings
from database import QdrantRepository
from embedder import Embedder
from utils import clean_text


class TelegramParser:
    def __init__(self, db: QdrantRepository, embedder: Embedder):
        self.db = db
        self.embedder = embedder

        self.buffer = []
        self.batch_size = settings.embeddings.batch_size

        proxy_cfg = settings.telegram.proxy
        proxy_tuple = None
        connection_type = None

        if proxy_cfg and proxy_cfg.host:
            p_type = proxy_cfg.type.lower()
            if p_type == "mtproxy":
                connection_type = ConnectionTcpMTProxy
                proxy_tuple = (proxy_cfg.host, proxy_cfg.port, proxy_cfg.secret)
            elif p_type == "socks5":
                proxy_tuple = ('socks5', proxy_cfg.host, proxy_cfg.port, True)
            elif p_type == "http":
                proxy_tuple = ('http', proxy_cfg.host, proxy_cfg.port)

        # Формируем аргументы для клиента динамически
        client_kwargs = {
            'connection_retries': 3,
            'retry_delay': 5,
            'timeout': 60,
            'request_retries': 5,
            'auto_reconnect': True,
        }

        # Добавляем connection ТОЛЬКО если это mtproxy (иначе Telethon выдаст AssertionError)
        if connection_type is not None:
            client_kwargs['connection'] = connection_type

        # Добавляем proxy, если он настроен
        if proxy_tuple is not None:
            client_kwargs['proxy'] = proxy_tuple

        self.client = TelegramClient(
            'parser_session',
            settings.telegram.api_id,
            settings.telegram.api_hash,
            **client_kwargs
        )
        self.channels = self._load_channels()

    def _load_channels(self) -> list[str]:
        try:
            with open("channels.txt", "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            logger.warning("Файл channels.txt не найден.")
            return []

    def _build_payload(self, message, channel_title: str, channel_username: str) -> dict | None:
        """Возвращает payload или None, если текст отсутствует или слишком короткий"""
        raw_text = message.text or message.message or ""

        # 1. Если исходного текста нет
        if not raw_text.strip():
            return None

        cleaned_text = clean_text(raw_text)

        # 2. Если после очистки текст стал пустым (были только эмодзи/ссылки)
        if not cleaned_text.strip():
            return None

        # 3. Проверка минимальной длины (безопасное получение из конфига)
        min_length = settings.filter.min_text_length
        if len(cleaned_text) < min_length:
            return None

        unique_str = f"{message.chat_id}_{message.id}"
        news_id = hashlib.md5(unique_str.encode()).hexdigest()

        return {
            "news_id": news_id,
            "title": channel_title,
            "text": cleaned_text,
            "source": channel_username or channel_title,
            "url": "",
            "published_at": message.date.isoformat() if message.date else datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _queue_message(self, message, channel_title: str, channel_username: str):
        """Добавляет сообщение в буфер только если есть валидный текст"""
        payload = self._build_payload(message, channel_title, channel_username)

        # === КРИТИЧЕСКИ ВАЖНО: прерываем выполнение, если текста нет ===
        if payload is None:
            return

        try:
            payload["url"] = await message.get_link() or ""
        except Exception:
            pass

        self.buffer.append({
            "news_id": payload["news_id"],
            "text": payload["text"],
            "payload": payload
        })

        logger.info(f"[NEW] {channel_title} | {payload['text'][:50]}...")

        if len(self.buffer) >= self.batch_size:
            await self._flush_buffer()

    async def _flush_buffer(self):
        """Пакетная обработка и сохранение буфера в БД"""
        if not self.buffer:
            return

        logger.info(f"💾 Накоплено {len(self.buffer)} сообщений. Запуск эмбеддинга и сохранение...")

        texts = [item["text"] for item in self.buffer]
        vectors = await self.embedder.encode_async(texts, normalize=True)

        points = []
        for item, vector in zip(self.buffer, vectors):
            points.append(PointStruct(
                id=item["news_id"],
                vector=vector,
                payload=item["payload"]
            ))

        await self.db.client.upsert(
            collection_name=settings.collection.name,
            points=points
        )
        logger.success(f"✅ Успешно сохранено {len(points)} сообщений в Qdrant")
        self.buffer.clear()


    async def start_monitoring(self):
        @self.client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            try:
                channel = await event.get_chat()
                await self._queue_message(event.message, channel.title, getattr(channel, 'username', 'unknown'))
            except Exception as e:
                logger.error(f"Ошибка в обработчике: {e}")

        logger.info("👀 Мониторинг запущен. Сообщения накапливаются до достижения лимита...")
        await self.client.run_until_disconnected()

    async def fetch_history(self):
        limit = settings.telegram.fetch_limit
        logger.info(f"--- Загрузка последних {limit} постов из {len(self.channels)} каналов ---")

        for channel_name in self.channels:
            try:
                entity = await self.client.get_entity(channel_name)
                username = getattr(entity, 'username', 'unknown')
                logger.info(f"[*] Парсинг: {entity.title}")

                try:
                    async for message in self.client.iter_messages(entity, limit=limit):
                        await self._queue_message(message, entity.title, username)

                        # Пауза каждые 20 сообщений для защиты от FloodWait
                        if len(self.buffer) % 20 == 0:
                            await asyncio.sleep(1)

                except FloodWaitError as e:
                    logger.warning(f"FloodWait: ждем {e.seconds} секунд...")
                    await asyncio.sleep(e.seconds)

                # Сохраняем остаток буфера перед переходом к следующему каналу
                await self._flush_buffer()
                logger.success(f"[OK] Канал {entity.title} полностью обработан")
                await asyncio.sleep(3)

            except ChannelPrivateError:
                logger.error(f"[ERROR] {channel_name} - приватный канал или нет доступа")
            except Exception as e:
                logger.error(f"[ERROR] {channel_name}: {e}")

        logger.info("--- Загрузка истории завершена ---")

    async def start(self):
        await self.client.connect()
        logger.success("✅ Соединение с Telegram установлено")

        if await self.client.is_user_authorized():
            me = await self.client.get_me()
            logger.success(f"✅ Уже авторизованы как: {me.first_name} (@{me.username})")
            return

        phone = input("Введите номер телефона (например +79991234567): ")
        try:
            result = await self.client.send_code_request(phone)
            logger.info("📱 Код отправлен")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки кода: {e}")
            await self.client.disconnect()
            raise

        code = input("Введите код из Telegram: ")
        try:
            await self.client.sign_in(phone=phone, code=code, phone_code_hash=result.phone_code_hash)
        except Exception as e:
            if "SESSION_PASSWORD_NEEDED" in str(e):
                logger.warning("🔐 Требуется облачный пароль (2FA)")
                password = input("Введите облачный пароль: ")
                await self.client.sign_in(password=password)
            else:
                logger.error(f"❌ Ошибка входа: {e}")
                raise

        me = await self.client.get_me()
        logger.success(f"✅ Успешно авторизованы как: {me.first_name} (@{me.username})")