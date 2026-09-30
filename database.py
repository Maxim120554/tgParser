import os
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams, Distance, ScalarQuantization, ScalarQuantizationConfig
)
from loguru import logger
from settings import settings


class QdrantRepository:
    def __init__(self):
        self._client: AsyncQdrantClient | None = None
        self._url = f"http://{settings.qdrant.host}:{settings.qdrant.http_port}"

    async def connect(self) -> "QdrantRepository":
        async def _try_connect():
            self._client = AsyncQdrantClient(
                url=self._url,
                grpc_port=settings.qdrant.grpc_port,
                prefer_grpc=settings.qdrant.prefer_grpc,
                api_key=settings.qdrant.api_key or None,
                timeout=settings.qdrant.timeout,
            )
            await self._client.get_collections()

        try:
            await _try_connect()
            logger.info(f"✅ Подключение к Qdrant установлено: {self._url}")
            return self
        except Exception as e:
            error_msg = str(e).lower()
            if "proxy" in error_msg or "502" in error_msg or "bad gateway" in error_msg:
                logger.warning("⚠️ Проблема с прокси. Попытка переподключения с NO_PROXY...")
                os.environ["NO_PROXY"] = "127.0.0.1,localhost"
                os.environ["no_proxy"] = "127.0.0.1,localhost"
                try:
                    self._client = None
                    await _try_connect()
                    logger.success(f"✅ Подключение к Qdrant успешно (через NO_PROXY): {self._url}")
                    return self
                except Exception as retry_e:
                    logger.error(f"❌ Ошибка подключения после отключения прокси: {retry_e}")
                    self._client = None
                    raise ConnectionError(f"Не удалось подключиться к БД: {retry_e}") from retry_e
            else:
                logger.error(f"❌ Ошибка подключения к Qdrant: {e}")
                self._client = None
                raise ConnectionError(f"Не удалось подключиться к БД: {e}") from e

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise ConnectionError("Клиент не инициализирован. Вызовите connect().")
        return self._client

    async def ensure_collection(self):
        collections = await self.client.get_collections()
        names = [c.name for c in collections.collections]
        coll_cfg = settings.collection

        if coll_cfg.name not in names:
            distance = Distance.COSINE if coll_cfg.vector_distance.lower() == "cosine" else Distance.DOT

            quantization_config = None
            if coll_cfg.quantization_enabled:
                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(type="int8", always_ram=True)
                )

            logger.info("Создание коллекции с расширенными параметрами...")
            await self.client.create_collection(
                collection_name=coll_cfg.name,
                vectors_config=VectorParams(size=coll_cfg.vector_size, distance=distance),
                shard_number=coll_cfg.shard_number,
                replication_factor=coll_cfg.replication_factor,
                on_disk_payload=coll_cfg.on_disk_payload,
                quantization_config=quantization_config
            )
            logger.success(
                f"✅ Коллекция '{coll_cfg.name}' создана (dim={coll_cfg.vector_size}, quantization={coll_cfg.quantization_enabled})")
        else:
            logger.info(f"✅ Коллекция '{coll_cfg.name}' уже существует")