from typing import List
import hashlib

class EmbeddingService:
    def __init__(self):
        self.available = False
        try:
            import numpy as np  # noqa
            self.available = True
        except Exception:
            self.available = False

    def embed_text(self, text: str) -> List[float]:
        # 简化占位：用hash生成伪向量，避免环境不满足时报错
        h = hashlib.sha256(text.encode('utf-8')).digest()
        return [int(b) / 255.0 for b in h[:64]]

embedding_service = EmbeddingService()