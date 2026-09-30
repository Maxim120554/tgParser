import sys
import json
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
BASE_DIR = Path(__file__).parent.resolve()

class Settings:
    def __init__(self, config_path: str = "config.json"):
        with open(BASE_DIR / config_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def project(self): return self._data["project"]
    @property
    def telegram(self): return self._data["telegram"]
    @property
    def qdrant(self): return self._data["qdrant"]
    @property
    def collection(self): return self._data["collection"]
    @property
    def embeddings(self): return self._data["embeddings"]
    @property
    def filter(self):
        f = self._data.get("filter")
        return f if isinstance(f, dict) else {"min_text_length": 0}

settings = Settings()

def setup_logger() -> None:
    logger.remove()

    logger.add(
        sys.stderr,
        format=(
            "<green>{time:DD-MM-YYYY HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.project["log_level"],
        colorize=True,
    )

    log_dir = BASE_DIR / settings.project["log_dir"]
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "app_{time:DD-MM-YYYY}.log",
        format=(
            "{time:DD-MM-YYYY HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message} | "
            "{exception}"
        ),
        level=settings.project["log_level"],
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )
    logger.info(f"Логгер инициализирован. Уровень: {settings.project['log_level']}")

setup_logger()