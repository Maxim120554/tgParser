import asyncio
import torch
from pathlib import Path
from loguru import logger
from sentence_transformers import SentenceTransformer
# from config import settings
from settings import settings

class Embedder:
    def __init__(self) -> None:
        cfg = settings.embeddings
        self.model_name = cfg.model_name
        self.model_path = cfg.model_path
        self.device = cfg.device
        self.batch_size = cfg.batch_size
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            model_kwargs = {}
            if self.device == "cuda":
                if torch.cuda.is_bf16_supported():
                    model_kwargs["torch_dtype"] = torch.bfloat16
                else:
                    model_kwargs["torch_dtype"] = torch.float16
                logger.info(f"🚀 Используется GPU: {torch.cuda.get_device_name(0)}")

            if not Path(self.model_path).exists():
                logger.warning(f"Модель не найдена: {self.model_path}. Загрузка из HuggingFace...")
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                    model_kwargs=model_kwargs,
                    trust_remote_code=True,
                )
                self._model.save(self.model_path)
                logger.success(f"✅ Модель сохранена в {self.model_path}")
            else:
                logger.info(f"Загрузка модели из {self.model_path} на {self.device}...")
                self._model = SentenceTransformer(
                    self.model_path,
                    device=self.device,
                    model_kwargs=model_kwargs,
                    trust_remote_code=True,
                )

            dim = self._model.get_embedding_dimension()
            settings.collection.vector_size = dim
            logger.success(f"✅ Модель загружена. Размерность: {dim}, Batch size для инференса: {self.batch_size}")

        return self._model

    async def encode_async(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode_sync, texts, normalize)

    def _encode_sync(self, texts: list[str], normalize: bool = True):
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()
        return embeddings