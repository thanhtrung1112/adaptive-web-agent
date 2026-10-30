"""Benchmark 0.5.0: independent, deterministic mutation axes for owned MiniBiz HTML."""
import re
from pathlib import Path

from .mutations import Node, Tree, mutate_html, opaque_id, render

VERSION = '0.5.0'
MODES = ('W5_ID', 'W5_CLASS', 'W5_TEXT', 'W5_ORDER', 'W5_STRUCTURE', 'W5_COMBINED')


def nodes(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from nodes(child)


def mutate(source, mode, seed):
    if mode not in MODES:
        raise ValueError('Unsupported W5 mutation')
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError('Seed out of range')
    combined = mode == 'W5_COMBINED'
    # Reuse frozen W4 primitives; W4 routes and evidence keep their original behavior.
    for enabled, axis in ((mode == 'W5_ID' or combined, 'M1'),
                          (mode == 'W5_TEXT' or combined, 'M2'),
                          (mode == 'W5_STRUCTURE' or combined, 'M3')):
        if enabled:
            source = mutate_html(source, axis, seed)
    root = Tree(source).root
    all_nodes = list(nodes(root))
    if mode == 'W5_CLASS' or combined:
        for node in all_nodes:
            if node.attrs.get('class'):
                node.attrs['class'] = ' '.join(opaque_id(c, seed) for c in node.attrs['class'].split())
            for key in list(node.attrs):
                if key.startswith('data-'):
                    node.attrs['data-' + opaque_id(key[5:], seed)] = node.attrs.pop(key)
        # Ship equivalent stylesheet with the renamed classes, preserving presentation.
        css = (Path(__file__).parent / 'static/style.css').read_text(encoding='utf-8')
        css = re.sub(r'\.([A-Za-z_][\w-]*)', lambda m: '.' + opaque_id(m[1], seed), css)
        head = next(n for n in all_nodes if n.tag == 'head') if any(n.tag == 'head' for n in all_nodes) else root
        head.children.append(Node('style', {}, [css]))
    if mode == 'W5_ORDER' or combined:
        # Rotate columns consistently in header and every complete data row. Empty rows
        # with colspan stay intact; business IDs/values and record order stay unchanged.
        for table in [n for n in all_nodes if n.tag == 'table']:
            rows = [n for n in nodes(table) if n.tag == 'tr']
            width = max((sum(isinstance(c, Node) and c.tag in ('th', 'td') for c in r.children) for r in rows), default=0)
            for row in rows:
                positions = [i for i,c in enumerate(row.children) if isinstance(c,Node) and c.tag in ('th','td')]
                if width > 1 and len(positions) == width and all('colspan' not in row.children[i].attrs for i in positions):
                    cells = [row.children[i] for i in positions]
                    shift = 1 + seed % (width - 1)
                    cells = cells[shift:] + cells[:shift]
                    for i, cell in zip(positions, cells):
                        row.children[i] = cell
        for nav in [n for n in all_nodes if n.tag == 'nav']:
            positions = [i for i,c in enumerate(nav.children) if isinstance(c,Node) and c.tag == 'a']
            links = [nav.children[i] for i in positions]
            if len(links) > 1:
                shift = 1 + seed % (len(links)-1)
                for i, link in zip(positions, links[shift:]+links[:shift]):
                    nav.children[i] = link
    # Set dynamic-row script context after composing primitives (one query, no aliases).
    for node in all_nodes:
        if node.tag == 'script' and '/static/orders.js' in node.attrs.get('src',''):
            node.attrs['src'] = node.attrs['src'].split('?')[0] + f'?mutation={mode}&seed={seed}'
        if node.tag == 'input' and node.attrs.get('name') == 'mutation':
            node.attrs['value'] = mode
    return render(root)
