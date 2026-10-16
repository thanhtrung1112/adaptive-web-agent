"""Thu DOM của MiniBiz trong browser context do bên gọi quản lý."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .parser import parse_snapshot

EXTRACT = Path(__file__).with_name('extract.js').read_text(encoding='utf-8')


# Chụp đúng trạng thái hiện tại; bên gọi phải chờ điều kiện sẵn sàng trước khi gọi.
def capture(page, snapshot_id, task_id, state, provenance):
    raw = page.evaluate(EXTRACT)
    html = raw.pop('html')
    metadata = {
        'snapshot_id': snapshot_id, 'task_id': task_id, 'state': state,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'viewport': page.viewport_size,
        'html_sha256': hashlib.sha256(html.encode('utf-8')).hexdigest(),
        'provenance': provenance,
    }
    return html, parse_snapshot(raw, metadata)


# Lưu HTML UTF-8 và JSON chỉnh sửa/đọc độc lập; không lưu ảnh hay video.
def save_snapshot(directory, html, snapshot):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'dom.html').write_bytes(html.encode('utf-8'))
    (directory/'features.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
