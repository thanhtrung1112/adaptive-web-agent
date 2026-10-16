"""Chuẩn hóa snapshot runtime, giữ mọi phần tử cho candidate generator lọc sau."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).with_name('schema_v0.1.json')


# Ngoài schema kiểu dữ liệu, kiểm tra định danh và quan hệ cây DOM.
def validate_snapshot(snapshot):
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding='utf-8'))).validate(snapshot)
    seen = set()
    for element in snapshot['elements']:
        ident = element['element_id']
        if ident in seen:
            raise ValueError(f'Duplicate element_id: {ident}')
        parent = element['parent_id']
        if parent is not None and parent not in seen:
            raise ValueError(f'Parent must precede child: {ident}')
        if parent is None and seen:
            raise ValueError('Only one DOM root is allowed')
        seen.add(ident)
    return snapshot


# Tách payload runtime khỏi metadata; không suy đoán trạng thái visible từ HTML tĩnh.
def parse_snapshot(raw, metadata):
    snapshot = {**metadata, 'schema_version': '0.1', 'url': raw['url'],
                'title': raw['title'], 'elements': raw['elements']}
    return validate_snapshot(snapshot)
