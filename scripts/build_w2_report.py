"""Sinh báo cáo PDF 2 trang từ kết quả W2; cần reportlab và font Arial trên Windows."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/weekly/W2-report.pdf'


# Báo cáo lấy trực tiếp số đo đã lưu, không nhập lại bằng tay.
def main():
    summary = json.loads((ROOT/'results/w2/baseline_M0_summary.json').read_text(encoding='utf-8'))
    metadata = json.loads((ROOT/'results/w2/baseline_M0_metadata.json').read_text(encoding='utf-8'))
    pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('ArialBold', 'C:/Windows/Fonts/arialbd.ttf'))
    pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='ArialBold')
    body = ParagraphStyle('Body', fontName='Arial', fontSize=10, leading=14, spaceAfter=7)
    title = ParagraphStyle('Title', parent=body, fontName='ArialBold', fontSize=18, leading=23, spaceAfter=12)
    heading = ParagraphStyle('Heading', parent=body, fontName='ArialBold', fontSize=12, leading=16, spaceBefore=10)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=11, spaceAfter=0)
    story=[]
    def p(text, style=body): story.append(Paragraph(text,style))
    def table(rows, widths):
        cells=[[Paragraph(str(cell),small) for cell in row] for row in rows]
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8edf3')),
            ('GRID',(0,0),(-1,-1),.5,colors.HexColor('#cbd2da')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.append(t);story.append(Spacer(1,8))
    p('Báo cáo tiến độ tuần 2',title)
    p('Đề tài AI Agent thích nghi tự động hóa tác vụ nghiệp vụ trên Web')
    p('Nhóm: Vũ Văn Bình và Nguyễn Thành Trung<br/>Thời gian kế hoạch: 04/10–10/10/2026')
    p('Kết quả thực hiện',heading)
    p('Đã xây dựng MiniBiz v1 gồm CRM, Order, Support và luồng khách hàng → đơn hàng → ticket. '
      'Ứng dụng có dữ liệu tổng hợp, reset seed, API chỉ đọc để chấm và hướng dẫn chạy. '
      'Bộ W2 gồm 20 task khác nhau; 10 pilot task W1 được giữ nguyên.')
    p('Phân bố: 6 CRM, 8 Order, 5 Support, 1 chain. Hai cấu hình CSS/XPath thực thi qua '
      'giao diện bằng Playwright. Mỗi cấu hình đạt 20/20 trên DOM gốc M0; 23 kiểm thử tự động đạt.')
    p('Bảng tiến độ',heading)
    table([
        ['Planned','Done','Evidence','Problems','Next week'],
        ['App v1','Ba module và luồng liên thông','app/; tests/; PR #3','Validation ngoài tập task còn giới hạn','Ổn định DOM'],
        ['20 task','T001–T020','tasks/tasks_w2.json','Có biến thể cùng workflow','Chuẩn bị snapshot'],
        ['CSS/XPath','40 lượt; 40 đạt','results/w2/; baseline/','Một lần/task, chỉ M0','Parser và candidate generator'],
        ['Bằng chứng','Báo cáo, trace, metadata','docs/weekly/; results/w2/','Cần PR bổ sung và nộp LMS','Bàn giao dữ liệu W3'],
    ],[66,91,107,116,115])
    p('Phương pháp đo',heading)
    p('Runner tự mở server local và SQLite tạm riêng, reset trước từng task và tạo browser context mới. '
      'Timeout 5 giây/hành động; không retry; giới hạn bước theo task. Chấm trạng thái cuối bằng API '
      'hoặc nội dung CSV. T002 giữ cookie; T010 đối chiếu ID đơn mới với ticket.')
    p('Mỗi goto/fill/select/click/download tính một bước. Latency tính hành động và tải file, '
      'không gồm reset, khởi tạo context hoặc chấm API. Lọc ngày UTC gồm cả hai biên. '
      'Bộ chấm từ chối CSV lặp dòng và ticket gắn sai đơn.')
    story.append(PageBreak())
    p('Kết quả và bằng chứng tuần 2',title)
    rows=[['Cấu hình','Task đạt','Success rate','Median (s)','p95 (s)','Mean steps']]
    for mode in ('css','xpath'):
        s=summary[mode]
        rows.append([mode.upper(),f"{s['success']}/{s['tasks']}",f"{s['success_rate']:.0%}",s['median_seconds'],s['p95_seconds'],s['mean_steps']])
    table(rows,[80,70,90,85,85,85])
    p('Số liệu có 40 bản ghi cho 20 task × 2 cấu hình, một lần/task. p95 theo nearest-rank. '
      'Retry và chi phí token bằng 0; recovery rate chưa áp dụng vì chưa có self-healing. '
      '100% trên M0 không chứng minh khả năng thích nghi khi DOM thay đổi hoặc khác biệt tốc độ có ý nghĩa thống kê.')
    p('Truy vết và tái lập',heading)
    p(f"Lần đo bắt đầu (UTC): {metadata['started_at_utc']}. Chromium {metadata['browser_version']}. "
      'Môi trường khóa trong requirements-lock.txt; runner lưu metadata và trace từng bước.')
    p(f"Commit nền: {metadata['git_commit'][:12]}. Lúc đo có chỉnh sửa chưa commit; "
      'metadata ghi trạng thái Git và SHA-256 từng tệp nguồn sau chuẩn hóa LF. Không dùng commit nền '
      'một mình để đại diện phiên bản đã đo. Seed và tập task có checksum riêng.')
    p('Kết quả chính: results/w2/baseline_M0_results.csv; baseline_M0_summary.json; '
      'baseline_M0_metadata.json; baseline_M0_traces.json. CSV tải về được giữ trong downloads/. '
      'Kết quả pilot 10 task cũ được lưu riêng, không trộn với lần đo mới.')
    p('Liên kết và hoàn tất bàn giao',heading)
    p('<link href="https://github.com/thanhtrung1112/adaptive-web-agent/pull/3" color="blue">PR #3 app v1</link> · '
      '<link href="https://github.com/thanhtrung1112/adaptive-web-agent/pull/6" color="blue">PR #6 baseline pilot</link>. '
      'Hai PR này chưa chứa phần mở rộng 20 task và kết quả mới trên nhánh w2-completion.')
    p('Repo không lưu demo/video. Link demo hoặc video sẽ bổ sung riêng khi nộp LMS; '
      'phần này đang hoãn theo kế hoạch bàn giao của nhóm.')
    p('Trước khi nộp LMS: gắn Issue/Milestone cho bản bổ sung, commit có mã Issue và review chéo PR; '
      'cập nhật link PR và link demo/video, nộp PDF cùng CSV/JSON. Hai thành viên cần xác nhận ADR-0001.')
    p('Ghi nhận đóng góp chờ nhóm xác nhận: Vũ Văn Bình - Web App và kiểm tra T001–T010 (PR #3); '
      'Nguyễn Thành Trung - baseline ban đầu và review app (PR #6, review PR #3). '
      'Phân chia thí nghiệm, mục báo cáo và bản bổ sung cần ghi rõ trong docs/weekly/W2.md và Issue/PR.')
    p('Kế hoạch W3',heading)
    p('Thu DOM snapshot, xây parser và candidate generator; dùng bộ task W2 làm đầu vào. '
      'Giữ phạm vi MiniBiz, chưa đưa kết quả M0 thành kết luận về semantic ranking hoặc LLM.')
    def footer(canvas,doc):
        canvas.setFont('Arial',8);canvas.drawRightString(A4[0]-50,28,f'Trang {doc.page}')
    SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=40,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUT)


if __name__=='__main__':
    main()
