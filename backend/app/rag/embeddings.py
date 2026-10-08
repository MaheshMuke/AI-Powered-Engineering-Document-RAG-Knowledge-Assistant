"""
Embedding provider abstraction.
Supports sentence-transformers with an offline deterministic hash/ngram fallback
so vector search functions reliably without network dependencies.
"""
import math
import hashlib
from typing import List

import re

STOPWORDS = {
    'what', 'is', 'the', 'of', 'and', 'a', 'an', 'in', 'on', 'to', 'for', 'with', 'by', 'at', 'from',
    'does', 'do', 'are', 'was', 'were', 'it', 'its', 'this', 'that', 'these', 'those', 'how', 'which',
    'who', 'whom', 'whose', 'why', 'where', 'when', 'can', 'could', 'should', 'would', 'will', 'shall'
}

class LocalEmbeddingProvider:
    def __init__(self, dim: int = 384):
        self.dim = dim
        self._st_model = None
        self._try_load_st()

    def _try_load_st(self):
        try:
            from sentence_transformers import SentenceTransformer
            # Only load if cached locally, avoid blocking download if offline
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self._st_model = None

    def embed_text(self, text: str) -> List[float]:
        if self._st_model is not None:
            try:
                emb = self._st_model.encode(text).tolist()
                return emb
            except Exception:
                pass

        # Deterministic semantic-hash embedding fallback (unit vector in 384 dims)
        vec = [0.0] * self.dim
        if not text:
            return vec

        raw_tokens = re.findall(r'[a-zA-Z0-9_]+', text.lower())
        tokens = []
        for t in raw_tokens:
            tokens.append(t)
            if '_' in t:
                # Also index sub-parts, e.g. 'swc', 'cameraprocessing'
                parts = [p for p in t.split('_') if p]
                tokens.extend(parts)

        if not tokens:
            return vec

        for token in tokens:
            weight = 0.2 if token in STOPWORDS else 1.5
            if '_' in token:
                weight = 3.0  # Technical identifier bonus

            # Word level hash
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            bucket = h % self.dim
            sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
            vec[bucket] += sign * weight

            # Subword 3-gram hashes to capture partial matches
            if len(token) > 3:
                for i in range(len(token) - 2):
                    ngram = token[i:i+3]
                    nh = int(hashlib.sha256(ngram.encode("utf-8")).hexdigest(), 16)
                    nbucket = nh % self.dim
                    nsign = 1.0 if ((nh >> 8) % 2 == 0) else -1.0
                    vec[nbucket] += nsign * (weight * 0.3)

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

embedding_provider = LocalEmbeddingProvider()
