// Thu HTML và đặc trưng trong cùng một lần evaluate; không sửa DOM ứng dụng.
() => {
  const nodes = Array.from(document.querySelectorAll('*'));
  const ids = new Map(nodes.map((el, i) => [el, `e${i + 1}`]));
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  // XPath chỉ tham chiếu trong đúng trạng thái snapshot, không bền qua mutation.
  const path = el => {
    const parts = [];
    for (let n = el; n; n = n.parentElement) {
      const siblings = n.parentElement ? Array.from(n.parentElement.children) : [n];
      const index = siblings.filter(s => s.localName === n.localName).indexOf(n) + 1;
      parts.unshift(`*[local-name()='${n.localName}'][${index}]`);
    }
    return '/' + parts.join('/');
  };
  return {
    html: '<!DOCTYPE html>\n' + document.documentElement.outerHTML,
    url: location.href,
    title: document.title,
    elements: nodes.map(el => {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const labels = Array.from(el.labels || []).map(l => clean(l.textContent)).filter(Boolean);
      const labelledBy = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
        .map(id => document.getElementById(id)).filter(Boolean).map(n => clean(n.textContent)).join(' ');
      const attrs = Object.fromEntries(Array.from(el.attributes).map(a => [a.name, a.value]));
      return {
        element_id: ids.get(el), parent_id: ids.get(el.parentElement) || null,
        tag: el.localName, text: clean(el.textContent), attributes: attrs,
        label: labels.join(' ') || null,
        name_hint: clean(labelledBy || el.getAttribute('aria-label') || labels.join(' ') || el.getAttribute('alt') || el.getAttribute('title')) || null,
        visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.visibility !== 'collapse',
        enabled: !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true' && !el.closest('[inert]'),
        readonly: el.hasAttribute('readonly') || el.getAttribute('aria-readonly') === 'true',
        value: 'value' in el ? String(el.value) : null,
        checked: 'checked' in el ? Boolean(el.checked) : null,
        selected: 'selected' in el ? Boolean(el.selected) : null,
        bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
        locator: {strategy: 'xpath', value: path(el)}
      };
    })
  };
}
