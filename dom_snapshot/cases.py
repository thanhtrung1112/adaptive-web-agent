"""Trạng thái đại diện cho các giao diện T001–T020, không phải replay toàn bộ task."""


# Mỗi trạng thái có task liên quan và các bước chuẩn bị độc lập trên seed mới.
def case(state, tasks, route, ready, steps=(), expected=None, absent=()):
    return dict(state=state, tasks=tasks.split(), route=route, ready=ready,
                steps=steps, expected=expected or {}, absent=absent)


CASES = [
    case('customers-list', 'T001 T002 T003 T010 T011 T012 T013', '/customers', '#customer-search'),
    case('customers-new', 'T001 T011', '/customers/new', '#save-customer'),
    case('customers-search', 'T002 T003 T010 T012 T013', '/customers?email=tran.hoa%40example.com', '#customer-search',
         expected={'customer-search': {'value':'tran.hoa@example.com'}}),
    case('customers-detail', 'T002 T003 T010 T012 T013', '/customers/1', '#edit-customer'),
    case('customers-edit', 'T003 T013', '/customers/1/edit', '#save-customer',
         expected={'customer-phone': {'label':'Số điện thoại', 'value':'0900000001'}}),
    case('orders-list', 'T004 T005 T006 T014 T015 T016 T017 T018', '/orders', '#orders-from'),
    case('orders-filtered', 'T006 T018', '/orders?from=2026-09-01&to=2026-09-15', '#export-orders',
         expected={'orders-from':{'value':'2026-09-01'}, 'orders-to':{'value':'2026-09-15'}}),
    case('orders-new', 'T004 T010 T014', '/orders/new', '#save-order'),
    case('orders-two-lines', 'T004', '/orders/new', '#save-order',
         [('click','#add-order-line',None)],
         {'order-sku-2':{'label':'Sản phẩm'}, 'order-qty-2':{'label':'Số lượng','value':'1'}}),
    case('orders-detail', 'T005 T010 T015 T016 T017', '/orders/ORD-1003', '#order-status',
         expected={'order-status':{'label':'Trạng thái đơn hàng','value':'shipped'}}),
    case('orders-updated', 'T005 T015 T016 T017', '/orders/ORD-1003', '#order-status',
         [('select','#order-status','delivered'),('click','#update-order-status',None)],
         {'order-status':{'value':'delivered'}}),
    case('tickets-list', 'T007 T008 T009 T019 T020', '/tickets', '#create-ticket'),
    case('tickets-new', 'T007 T010 T020', '/tickets/new', '#save-ticket'),
    case('tickets-prefilled', 'T010', '/tickets/new?order_id=ORD-1003', '#save-ticket',
         expected={'ticket-order':{'value':'ORD-1003'}}),
    case('tickets-detail', 'T008 T009 T019 T020', '/tickets/TCK-2002', '#ticket-assignee',
         expected={'ticket-assignee':{'label':'Người xử lý'},'ticket-note':{'label':'Ghi chú'}}),
    case('tickets-assigned', 'T008 T019 T020', '/tickets/TCK-2002', '#ticket-assignee',
         [('select','#ticket-assignee','1'),('click','#assign-ticket',None)],
         {'ticket-assignee':{'value':'1'}}),
    case('tickets-closed', 'T009', '/tickets/TCK-2002', '#ticket-note',
         [('fill','#ticket-note','Đã hoàn tiền cho khách'),('click','#close-ticket',None)],
         absent=('ticket-assignee','ticket-note','close-ticket')),
]


# Đối chiếu đặc trưng đã parse với kỳ vọng nghiệp vụ riêng, không chỉ đếm node.
def check_features(snapshot, spec):
    by_id = {e['attributes']['id']:e for e in snapshot['elements'] if 'id' in e['attributes']}
    for ident, fields in spec['expected'].items():
        if ident not in by_id:
            raise AssertionError(f'Missing {ident}')
        for key, value in {**fields, 'visible':True, 'enabled':True}.items():
            if by_id[ident][key] != value:
                raise AssertionError(f'{spec["state"]}: {ident}.{key}: expected {value!r}, got {by_id[ident][key]!r}')
    for ident in spec['absent']:
        if ident in by_id:
            raise AssertionError(f'Unexpected control after closing: {ident}')
    if spec['state'] == 'tickets-closed':
        text = snapshot['elements'][0]['text']
        if 'closed' not in text or 'Đã hoàn tiền cho khách' not in text:
            raise AssertionError('Closed ticket must retain status and note')

