import sys
import asyncio
from loguru import logger
from config import settings
from database import QdrantRepository
from embedder import Embedder
from parser import TelegramParser

# Глобальная ссылка на парсер для graceful shutdown
parser_instance = None


async def main():
    global parser_instance

    # 1. Инициализация БД
    db = QdrantRepository()
    await db.connect()
    await db.ensure_collection()

    # 2. Инициализация модели эмбеддингов
    embedder = Embedder()
    _ = embedder.model  # Триггерим ленивую загрузку

    # 3. Инициализация парсера
    parser_instance = TelegramParser(db, embedder)
    await parser_instance.start()

    # 4. Выбор режима
    if len(sys.argv) > 1 and sys.argv[1] == 'fetch':
        await parser_instance.fetch_history()
        # Гарантированно сохраняем остаток буфера после завершения fetch
        await parser_instance._flush_buffer()
        await parser_instance.client.disconnect()
    else:
        logger.info("🚀 Запускаем режим мониторинга...")
        await parser_instance.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n🛑 Получен сигнал остановки. Сохраняем остаток буфера...")
        if parser_instance is not None:
            # Синхронно запускаем асинхронную функцию очистки перед выходом
            loop = asyncio.get_event_loop()
            loop.run_until_complete(parser_instance._flush_buffer())
        logger.success("✅ Буфер сохранен. Работа парсера остановлена.")
    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")