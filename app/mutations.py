"""HTML render mutations: M1 opaque IDs, M2 labels, M3 wrappers. No database changes."""
import html
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MODES = ('M0', 'M1', 'M2', 'M3')
COOKIE = 'minibiz_mutation'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
LABELS = {
    'Tìm': ('Tra cứu', 'Tìm thông tin'), 'Lưu': ('Lưu thông tin', 'Xác nhận lưu'),
    'Sửa': ('Chỉnh sửa', 'Cập nhật thông tin'), 'Thêm khách hàng': ('Tạo khách hàng', 'Khách hàng mới'),
    'Tên khách hàng': ('Họ tên khách hàng', 'Tên liên hệ'), 'Email': ('Địa chỉ email', 'Email liên hệ'),
    'Số điện thoại': ('Điện thoại liên hệ', 'Số liên lạc'),
    'Tìm khách hàng theo email': ('Tra cứu email khách hàng', 'Tìm theo địa chỉ email'),
    'Tạo đơn': ('Thêm đơn hàng', 'Tạo đơn hàng mới'), 'Khách hàng': ('Người đặt hàng', 'Khách mua hàng'),
    'Sản phẩm': ('Mặt hàng', 'Sản phẩm đặt mua'), 'Số lượng': ('Số lượng đặt mua', 'Lượng đặt'),
    'Thêm dòng': ('Thêm sản phẩm', 'Bổ sung mặt hàng'), 'Xóa dòng': ('Bỏ sản phẩm', 'Xóa mặt hàng'),
    'Xác nhận tạo đơn': ('Lưu đơn hàng', 'Hoàn tất tạo đơn'),
    'Trạng thái đơn hàng': ('Tình trạng đơn', 'Trạng thái xử lý đơn'),
    'Cập nhật': ('Lưu trạng thái', 'Xác nhận cập nhật'), 'Lọc': ('Áp dụng bộ lọc', 'Tìm đơn theo ngày'),
    'Từ ngày (UTC)': ('Ngày bắt đầu (UTC)', 'Từ thời điểm (UTC)'),
    'Đến ngày (UTC)': ('Ngày kết thúc (UTC)', 'Đến thời điểm (UTC)'),
    'Xuất CSV': ('Tải danh sách CSV', 'Tải tệp CSV'), 'Tạo ticket': ('Yêu cầu hỗ trợ mới', 'Thêm ticket'),
    'Đơn hàng': ('Đơn cần hỗ trợ', 'Đơn liên quan'), 'Tiêu đề': ('Chủ đề hỗ trợ', 'Nội dung tiêu đề'),
    'Gửi': ('Gửi yêu cầu', 'Tạo yêu cầu hỗ trợ'), 'Người xử lý': ('Nhân viên phụ trách', 'Người phụ trách'),
    'Gán': ('Phân công', 'Lưu người phụ trách'), 'Ghi chú': ('Ghi nhận xử lý', 'Ghi chú kết quả'),
    'Đóng ticket': ('Hoàn tất hỗ trợ', 'Kết thúc ticket'),
}


# FNV-1a 64-bit shared with orders.js; never use process-randomized hash().
def opaque_id(value, seed):
    number = 14695981039346656037
    for byte in f'{seed}:{value}'.encode('utf-8'):
        number = ((number ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return f'm{number:016x}'


def context_url(url, mode, seed):
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path.startswith('/') or parts.path.startswith(('/api/', '/static/')):
        return url
    pairs = [(k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True) if k not in ('mutation','seed')]
    return urlunsplit(parts._replace(query=urlencode(pairs + [('mutation',mode),('seed',str(seed))])))


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


# Parser limited to valid HTML rendered by MiniBiz; preserve script/style/comment text.
class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID: self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data): self.stack[-1].children.append(data)
    def handle_entityref(self, name): self.handle_data(f'&{name};')
    def handle_charref(self, name): self.handle_data(f'&#{name};')
    def handle_comment(self, text): self.handle_data(f'<!--{text}-->')
    def handle_decl(self, text): self.handle_data(f'<!{text}>')


def render(node):
    if isinstance(node, str): return node
    content = ''.join(render(c) for c in node.children)
    if node.tag == 'root': return content
    attrs = ''.join(' '+k+('' if v is None else '="'+html.escape(v,quote=True)+'"') for k,v in node.attrs.items())
    return f'<{node.tag}{attrs}>' + ('' if node.tag in VOID else content+f'</{node.tag}>')


# Pure transformation; keep transport names, CSS classes and option values unchanged.
def mutate_html(source, mode, seed):
    if mode not in MODES: raise ValueError('Unsupported mutation')
    if type(seed) is not int or not 0 <= seed <= 2147483647: raise ValueError('Seed out of range')
    if mode == 'M0': return source
    root = Tree(source).root
    def visit(node):
        if isinstance(node, str): return
        attrs = node.attrs
        if mode == 'M1':
            if attrs.get('id'): attrs['id'] = opaque_id(attrs['id'], seed)
            for ref in ('for','aria-labelledby','aria-describedby','aria-controls','headers'):
                if attrs.get(ref): attrs[ref] = ' '.join(opaque_id(v,seed) for v in attrs[ref].split())
            if attrs.get('href','').startswith('#'): attrs['href'] = '#'+opaque_id(attrs['href'][1:],seed)
        if mode == 'M2':
            if node.tag in ('label','button','a') and all(isinstance(c,str) for c in node.children):
                text = html.unescape(''.join(node.children)).strip()
                if text in LABELS: node.children = [html.escape(LABELS[text][int(opaque_id(text,seed)[-1],16)%2])]
            for key in ('placeholder','aria-label'):
                if attrs.get(key) in LABELS:
                    text = attrs[key]
                    attrs[key] = LABELS[text][int(opaque_id(text,seed)[-1],16)%2]
        # Keep href AND form action stable: context parameters must not bias locator/form features.
        # Cookies carry POST/link context; GET forms carry hidden query fields below.
        if node.tag == 'script' and '/static/orders.js' in attrs.get('src',''):
            attrs['src'] += ('&' if '?' in attrs['src'] else '?')+urlencode({'mutation':mode,'seed':seed})
        if node.tag == 'form' and attrs.get('method','get').lower() == 'get':
            for key,value in [('mutation',mode),('seed',str(seed))]:
                node.children.append(Node('input',{'type':'hidden','name':key,'value':value}))
        for child in list(node.children): visit(child)
        if mode == 'M3':
            # Do not wrap table rows/cells/options: preserve valid HTML and table semantics.
            children = []
            for child in node.children:
                if isinstance(child,Node) and child.tag in ('label','input','select','textarea','button','a') and node.tag not in ('label','select','option') and not (child.tag == 'input' and child.attrs.get('type') == 'hidden'):
                    # Phrasing wrappers are valid inside p/label; display:contents isolates structure.
                    for _ in range(1+seed%2): child = Node('span',{'style':'display:contents'},[child])
                children.append(child)
            node.children = children
    visit(root)
    return render(root)


# ASGI render boundary: mutate HTML before delivery and carry context through redirects.
class MutationMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or (scope['path'] != '/' and not any(scope['path']==p or scope['path'].startswith(p+'/') for p in ('/customers','/orders','/tickets'))):
            return await self.app(scope,receive,send)
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse
        request = Request(scope)
        try:
            saved = request.cookies.get(COOKIE,'M0:0').split(':')
            if len(saved)!=2: saved=['M0','0']
            mode = request.query_params.get('mutation',saved[0])
            seed = int(request.query_params.get('seed',saved[1]))
            if mode not in MODES or not 0 <= seed <= 2147483647: raise ValueError()
        except (ValueError,IndexError):
            return await PlainTextResponse('mutation must be M0/M1/M2/M3; seed must be 0..2147483647',status_code=400)(scope,receive,send)
        start, chunks = None, []
        async def wrapped(message):
            nonlocal start
            if message['type'] == 'http.response.start':
                start = {**message,'headers':list(message['headers'])}
                return
            if message['type'] != 'http.response.body': return await send(message)
            chunks.append(message.get('body',b''))
            if message.get('more_body',False): return
            payload = b''.join(chunks)
            headers = [(k,v) for k,v in start['headers'] if k.lower() != b'content-length']
            if any(k.lower() == b'content-type' and b'text/html' in v for k,v in headers):
                payload = mutate_html(payload.decode('utf-8'),mode,seed).encode('utf-8')
            if mode != 'M0':
                headers = [(k,context_url(v.decode('latin-1'),mode,seed).encode('latin-1') if k.lower() == b'location' else v) for k,v in headers]
            headers += [(b'content-length',str(len(payload)).encode()),
                        (b'set-cookie',f'{COOKIE}={mode}:{seed}; Path=/; SameSite=Lax'.encode())]
            await send({**start,'headers':headers})
            await send({'type':'http.response.body','body':payload})
        await self.app(scope,receive,wrapped)
