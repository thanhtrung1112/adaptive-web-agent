"""heal(): chọn phần tử thay thế cho locator hỏng, hoặc bỏ cuộc khi không đủ chắc."""
from healing.ordinal import add_ordinals
from ranking.rank import rank


def heal(descriptor, cands, mode="features", encoder=None, alpha=0.5,
         min_score=0.0, min_margin=0.0, top_k=3, use_order=False):
    """Trả về dict:
      status   'healed' | 'abstain'
      eid      element_id được chọn (None nếu abstain)
      xpath    xpath của phần tử được chọn nếu `cands` có khóa xpath, ngược lại ''
      score    điểm hạng 1; margin = điểm hạng 1 - điểm hạng 2 (1.0 nếu chỉ có 1 ứng viên)
      reason   '' khi healed; 'no_candidates' | 'low_score' | 'low_margin' | 'ambiguous_order' khi abstain
      via      'score' | 'ordinal' (chọn nhờ thứ tự trong nhóm) khi healed
      top1_eid luôn có (để ghi log/đánh giá), kể cả khi abstain
      topk     [{eid, score}, ...]
    Điểm lấy từ ranking.rank (làm tròn 3 chữ số), nên margin có độ phân giải 0.001.
    Hòa hoặc gần hòa (margin < min_margin; hoặc margin 0 khi min_margin = 0): use_order=False thì bỏ cuộc nếu
    min_margin > 0 (nếu min_margin = 0 thì giữ hành vi cũ, hạng đầu theo thứ tự DOM); use_order=True thì chỉ nhận khi
    đúng MỘT ứng viên trong nhóm gần hòa có cùng `ord` và `ord_n` với descriptor, ngược lại bỏ cuộc
    ('ambiguous_order': số dòng lặp đã đổi hoặc vẫn mơ hồ).
    """
    if not cands:
        return {"status": "abstain", "eid": None, "xpath": "", "score": 0.0, "margin": 0.0, "via": "",
                "reason": "no_candidates", "top1_eid": None, "topk": []}
    ranked = rank(descriptor, cands, encoder=encoder, mode=mode, alpha=alpha, top_k=len(cands))
    top = ranked[0]
    margin = round(top["score"] - ranked[1]["score"], 3) if len(ranked) > 1 else 1.0
    chosen, via, reason = top["element_id"], "score", ""
    if top["score"] < min_score:
        reason = "low_score"
    elif use_order and (margin == 0 or margin < min_margin):
        band = max(min_margin, 0.001)  # nhóm "gần hòa": điểm cách hạng 1 chưa tới min_margin
        tied = {r["element_id"] for r in ranked if top["score"] - r["score"] < band}
        fit = [c["element_id"] for c in add_ordinals(cands) if c["element_id"] in tied
               and c["ord"] == descriptor.get("ord") and c["ord_n"] == descriptor.get("ord_n")]
        if len(fit) == 1:
            chosen, via = fit[0], "ordinal"
        else:
            reason = "ambiguous_order"
    elif margin < min_margin or (min_margin > 0 and margin == 0):
        reason = "low_margin"
    by_id = {c["element_id"]: c for c in cands}
    healed = reason == ""
    return {
        "status": "healed" if healed else "abstain",
        "eid": chosen if healed else None,
        "xpath": by_id[chosen].get("xpath", "") if healed else "",
        "score": top["score"], "margin": margin, "reason": reason, "via": via if healed else "",
        "top1_eid": top["element_id"],
        "topk": [{"eid": r["element_id"], "score": r["score"]} for r in ranked[:top_k]],
    }
