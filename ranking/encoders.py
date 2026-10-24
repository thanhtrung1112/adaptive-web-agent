"""Bộ mã hóa văn bản thành vector. Hai lựa chọn cùng giao diện `encode(list[str]) -> ndarray (n, d)`, đã chuẩn hóa L2."""
import hashlib

import numpy as np

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # hỗ trợ tiếng Việt


def _normalize(v):
    return v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-9, None)


class _Cached:
    """Mỗi chuỗi chỉ mã hóa một lần (rất hữu ích khi mô hình thật chạy chậm)."""

    def encode(self, texts):
        texts = list(texts)
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            for t, vec in zip(missing, self._encode(missing)):
                self._cache[t] = vec
        return np.vstack([self._cache[t] for t in texts])


class HashingEncoder(_Cached):
    """Offline, xác định: băm n-gram ký tự vào vector cố định. Chỉ bắt được giống nhau về MẶT CHỮ, không bắt nghĩa."""

    def __init__(self, dim=512, ngram=(2, 4)):
        self.dim, self.ngram, self._cache = dim, ngram, {}

    def _encode(self, texts):
        out = np.zeros((len(texts), self.dim))
        for i, text in enumerate(texts):
            s = f" {text.lower()} "
            for n in range(self.ngram[0], self.ngram[1] + 1):
                for j in range(len(s) - n + 1):
                    h = int.from_bytes(hashlib.blake2b(s[j:j + n].encode("utf-8"), digest_size=4).digest(), "big")
                    out[i, h % self.dim] += 1.0
        return _normalize(out)


class SentenceTransformerEncoder(_Cached):
    """Embedding ngữ nghĩa bằng SentenceTransformers (cần `pip install sentence-transformers`, tải mô hình lần đầu)."""

    def __init__(self, model_name=DEFAULT_MODEL, model=None):
        if model is None:
            from sentence_transformers import SentenceTransformer  # import muộn: repo vẫn chạy khi chưa cài
            model = SentenceTransformer(model_name)
        self.model, self._cache = model, {}

    def _encode(self, texts):
        return _normalize(np.asarray(self.model.encode(list(texts), normalize_embeddings=True), dtype=float))


def make_encoder(name, model_name=DEFAULT_MODEL):
    if name == "hash":
        return HashingEncoder()
    if name == "sbert":
        return SentenceTransformerEncoder(model_name)
    raise ValueError(f"encoder không hợp lệ: {name}")
