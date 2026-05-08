import hashlib
import math


class EmbeddingClient:
    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            weight = (digest[1] / 255.0) + 0.5
            vector[index] += weight
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0:
            return vector
        return [component / norm for component in vector]
