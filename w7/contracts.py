"""Runtime-only handoff to Trung; no oracle IDs or locators in model-facing data."""
import importlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jsonschema import Draft202012Validator

DECISION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["decision", "candidate_id", "reason"],
    "properties": {"decision": {"type": "string", "enum": ["select", "abstain"]},
                   "candidate_id": {"type": ["string", "null"]},
                   "reason": {"type": "string"}}}
FEATURES = ("tag", "id", "name", "type", "text", "label", "placeholder", "href", "form", "path", "options", "ord", "ord_n", "context_text")


def safe_features(control):
    result = {}
    for key in FEATURES:
        if key not in control:
            continue
        value = control[key]
        if key in ("form", "href"):
            url = urlsplit(value)
            value = urlunsplit(url._replace(query=urlencode([(k, v) for k, v in parse_qsl(url.query)
                                                             if k not in ("mutation", "seed")])))
        if isinstance(value, str):
            value = value[:1000]
        elif isinstance(value, list):
            value = [str(v)[:200] for v in value[:40]]
        result[key] = value
    return result


def compatible(action, candidate):
    tag, kind = candidate.get("tag"), candidate.get("type", "").lower()
    if action == "fill":
        return tag == "textarea" or (tag == "input" and kind not in ("hidden", "checkbox", "radio", "file", "submit", "button", "reset", "image", "range", "color"))
    if action == "select":
        return tag == "select"
    return action in ("click", "download") and tag in ("a", "button", "input")


def make_request(descriptor, candidates, action, semantic_result, objective=""):
    """Return model-facing packet plus private candidate->XPath mapping.

    All compatible live candidates are offered; Trung selects top-k inside the
    resolver. Ranker top-k is included as hints, using only the opaque aliases.
    """
    offered, bindings, aliases = [], {}, {}
    for c in candidates:
        if not c.get("xpath") or not compatible(action, c):
            continue
        cid = f"c{len(offered) + 1}"
        aliases[c["element_id"]] = cid
        bindings[cid] = c["xpath"]
        offered.append({"candidate_id": cid, **safe_features(c)})
    ranked = [{"candidate_id": aliases[r["eid"]], "score": r["score"]}
              for r in semantic_result.get("topk", []) if r["eid"] in aliases]
    packet = {"version": "w7-fallback-v1", "action": action, "objective": objective[:2000],
              "descriptor": safe_features(descriptor), "trigger": semantic_result.get("reason", "uncertain"),
              "candidates": offered, "semantic_topk": ranked}
    return packet, bindings


def validate_decision(decision, bindings):
    Draft202012Validator(DECISION_SCHEMA).validate(decision)
    if decision["decision"] == "abstain":
        if decision["candidate_id"] is not None:
            raise ValueError("abstain requires candidate_id=null")
        return None
    if decision["candidate_id"] not in bindings:
        raise ValueError("selected candidate is outside the offered snapshot")
    return bindings[decision["candidate_id"]]


def load_resolver(spec):
    """module:function; signature resolve(packet, client) -> decision dict."""
    module, sep, name = spec.partition(":")
    if not sep or not name or name.startswith("_"):
        raise ValueError("resolver must be module:function")
    resolver = getattr(importlib.import_module(module), name)
    if not callable(resolver):
        raise ValueError("resolver is not callable")
    return resolver
