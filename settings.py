"""Централизованная конфигурация проекта через JSON и переменные окружения."""
import json
import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (если он существует)
load_dotenv()

# Абсолютный путь к корневой директории проекта и файлу конфигурации
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


class ProjectConfig(BaseModel):
    name: str = "news_analytics"
    log_level: str = "INFO"
    log_dir: Path = BASE_DIR / "logs"



class TelegramProxyConfig(BaseModel):
    """Вложенная модель для прокси Telegram."""
    type: str = "http"
    host: str = "127.0.0.1"
    port: int = 2080
    secret: str = ""


class TelegramConfig(BaseModel):
    # Чувствительные данные берем из .env. Если их нет, будут None (или 0 для int)
    api_id: int | None = int(os.getenv("TELEGRAM_API_ID", 0)) or None
    api_hash: str | None = os.getenv("TELEGRAM_API_HASH")

    # Данные из config.json
    fetch_limit: int = 150
    proxy: TelegramProxyConfig = TelegramProxyConfig()


class QdrantConfig(BaseModel):
    host: str = "192.168.0.100"
    http_port: int = 6333
    grpc_port: int = 6334
    # Критически важно: берем из .env, иначе пустая строка
    api_key: str = os.getenv("QDRANT_API_KEY", "")
    prefer_grpc: bool = False
    timeout: int = 30


class CollectionConfig(BaseModel):
    name: str = ""
    vector_size: int = 2048
    vector_distance: str = "Cosine"
    shard_number: int = 1
    replication_factor: int = 1
    on_disk_payload: bool = True
    quantization_enabled: bool = True


class EmbeddingsConfig(BaseModel):
    model_name: str = ""
    model_path: str = ""
    device: str = "cuda"
    batch_size: int = 40


class FilterConfig(BaseModel):
    min_text_length: int = 100


class Settings(BaseModel):
    project: ProjectConfig
    telegram: TelegramConfig
    qdrant: QdrantConfig
    collection: CollectionConfig
    embeddings: EmbeddingsConfig
    filter: FilterConfig

    @classmethod
    def load(cls) -> "Settings":
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"❌ Файл конфигурации не найден: {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Pydantic автоматически сопоставит JSON с моделями и подставит значения из .env, где указано os.getenv
        return cls(**data)


# Глобальный экземпляр настроек, готовый к импорту в любом месте проекта
settings = Settings.load()