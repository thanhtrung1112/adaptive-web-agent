// Form operations use business names/structure, independent of mutated IDs and labels.
const form = document.querySelector('form[action^="/orders/new"]');
const lines = form.querySelector('fieldset').parentElement;
const script = document.querySelector('script[src*="/static/orders.js"]');
const config = new URL(script.src).searchParams;
const mutation = config.get('mutation') || 'M0';
const seed = config.get('seed') || '0';

// Same FNV-1a 64-bit as app/mutations.py, including fields cloned in the browser.
function fieldId(name, number) {
    const original = `order-${name}-${number}`;
    if (!['M1', 'W5_ID', 'W5_COMBINED'].includes(mutation)) return original;
    let hash = 14695981039346656037n;
    for (const byte of new TextEncoder().encode(`${seed}:${original}`)) {
        hash = BigInt.asUintN(64, (hash ^ BigInt(byte)) * 1099511628211n);
    }
    return 'm' + hash.toString(16).padStart(16, '0');
}

// Keep label references and field IDs synchronized after adding/removing a row.
function renumberLines() {
    const rows = lines.querySelectorAll('fieldset');
    rows.forEach((row, index) => {
        row.querySelector('legend').textContent = `Sản phẩm ${index + 1}`;
        for (const name of ['sku', 'qty']) {
            const input = row.querySelector(`[name="${name}"]`);
            const label = Array.from(row.querySelectorAll('label')).find(el => el.htmlFor === input.id);
            input.id = fieldId(name, index + 1);
            label.htmlFor = input.id;
        }
        row.querySelector('button[type="button"]').disabled = rows.length === 1;
    });
}

// The add button is outside fieldsets; wrappers do not alter that relationship.
const add = Array.from(form.querySelectorAll('button[type="button"]')).find(el => !el.closest('fieldset'));
add.addEventListener('click', () => {
    const row = lines.querySelector('fieldset').cloneNode(true);
    row.querySelector('[name="sku"]').value = '';
    row.querySelector('[name="qty"]').value = '1';
    lines.appendChild(row);
    renumberLines();
});

// Delegation handles buttons in newly cloned rows as well.
lines.addEventListener('click', event => {
    const button = event.target.closest('button[type="button"]');
    if (button && lines.querySelectorAll('fieldset').length > 1) {
        button.closest('fieldset').remove();
        renumberLines();
    }
});
renumberLines();
