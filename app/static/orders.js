// Đánh lại ID và label sau khi thêm/xóa để mỗi ô có nhãn riêng.
const lines = document.getElementById("order-lines");
function renumberLines() {
    lines.querySelectorAll(".order-line").forEach((row, index) => {
        const number = index + 1;
        row.querySelector("legend").textContent = `Sản phẩm ${number}`;
        for (const name of ["sku", "qty"]) {
            const input = row.querySelector(`[name="${name}"]`);
            row.querySelector(`label[for="${input.id}"]`).htmlFor = `order-${name}-${number}`;
            input.id = `order-${name}-${number}`;
        }
        row.querySelector(".remove-line").disabled = lines.children.length === 1;
    });
}

// Nhân bản cấu trúc dòng nhưng đặt lại sản phẩm và số lượng.
document.getElementById("add-order-line").addEventListener("click", () => {
    const row = lines.firstElementChild.cloneNode(true);
    row.querySelector('[name="sku"]').value = "";
    row.querySelector('[name="qty"]').value = "1";
    lines.appendChild(row);
    renumberLines();
});

// Luôn giữ ít nhất một dòng sản phẩm trên form.
lines.addEventListener("click", (event) => {
    if (event.target.matches(".remove-line") && lines.children.length > 1) {
        event.target.closest(".order-line").remove();
        renumberLines();
    }
});
renumberLines();
