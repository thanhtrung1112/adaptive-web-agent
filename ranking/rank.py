"""Semantic locator ranking: kết hợp điểm đặc trưng (candidates.generator) với độ giống embedding."""
import numpy as np

from candidates.generator import score as feature_score
from ranking.text import element_text

MODES = ("features", "embedding", "hybrid")


def rank(desc, cands, encoder=None, mode="hybrid", alpha=0.5, top_k=5):
    """Xếp hạng các control `cands` theo độ giống với phần tử gốc `desc`.

    mode: features (chỉ đặc trưng, = generator v0.1), embedding (chỉ cosine), hybrid (alpha*đặc trưng + (1-alpha)*cosine).
    Hòa điểm thì giữ thứ tự trong DOM.
    """
    feats = np.array([feature_score(desc, c)[0] for c in cands])
    sims = np.zeros(len(cands))
    if mode != "features":
        vecs = encoder.encode([element_text(desc)] + [element_text(c) for c in cands])
        sims = np.clip(vecs[1:] @ vecs[0], 0.0, 1.0)
    final = {"features": feats, "embedding": sims, "hybrid": alpha * feats + (1 - alpha) * sims}[mode]
    order = np.argsort(-final, kind="stable")[:top_k]
    return [{"element_id": cands[i]["element_id"], "score": round(float(final[i]), 3),
             "feature": round(float(feats[i]), 3), "embedding": round(float(sims[i]), 3)} for i in order]
