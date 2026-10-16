"""Ground truth: phần tử đích của từng selector trong baseline, tìm trong các trạng thái đã thu."""
import re

from baseline.scripts import SCRIPTS
from candidates.features import controls, list_states, load_state


def parse_selector(css):
    if m := re.fullmatch(r"#([\w-]+)", css):
        return lambda c: c["id"] == m.group(1)
    if m := re.fullmatch(r"(?:table )?a\[href='([^']+)'\]", css):
        return lambda c: c["tag"] == "a" and c["href"] == m.group(1)
    if m := re.fullmatch(r"(?:table )?a\[href\^='([^']+)'\]", css):
        return lambda c: c["tag"] == "a" and c["href"].startswith(m.group(1))
    return None


def build_targets():
    """Danh sách (state, element_id, selector) duy nhất."""
    selectors = {s["css"] for steps in SCRIPTS.values() for s in steps if s["do"] != "goto"}
    found, skipped = set(), set()
    for st in list_states():
        cs = controls(load_state(st))
        for css in selectors:
            match = parse_selector(css)
            if match is None:
                skipped.add(css)
                continue
            for c in cs:
                if match(c):
                    found.add((st, c["element_id"], css))
    return sorted(found), sorted(skipped)
