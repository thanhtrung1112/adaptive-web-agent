"""Attach observed container text for the resolver, without changing ranker features."""
from healing.descriptor import controls_with_xpath
from healing.ordinal import add_ordinals


def runtime_candidates(snapshot):
    by_id = {e["element_id"]: e for e in snapshot["elements"]}
    result = []
    for candidate in add_ordinals(controls_with_xpath(snapshot)):
        node = by_id[candidate["element_id"]]
        context = ""
        while node.get("parent_id"):
            node = by_id[node["parent_id"]]
            if node["tag"] in ("section", "fieldset", "tr", "article", "form"):
                context = node.get("text", "")[:1000]
                break
        result.append({**candidate, "context_text": context})
    return result
