"""Evaluation-only locator translation. Never import from ranking/embedding code."""
from app.mutations import opaque_id


# Uses knowledge of the app's mutation rule, ONLY to establish functionality and ground truth.
def oracle_css(css, mutation, seed):
    if mutation == 'M1' and css.startswith('#'):
        return '#' + opaque_id(css[1:], seed)
    return css


# Ground-truth IDs reference schema v0.1 DOM preorder; no extra attribute is injected in HTML.
def element_id(locator):
    if locator.count() != 1:
        raise ValueError(f'Expected exactly one oracle target: {locator}')
    return locator.evaluate("el => 'e' + (Array.from(document.querySelectorAll('*')).indexOf(el) + 1)")
