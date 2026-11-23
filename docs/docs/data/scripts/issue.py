import csv, json, hashlib, datetime, io, qrcode
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

BASE_URL = "https://profswatraj-stack.github.io/teamacademy-certificates/"

# ---------- LAYOUT SETTINGS (edit these to fit your template) ----------
# x and y are fractions of the page: x from the left (0 to 1), y from the top (0 to 1)
FIELDS = {
    "name":   dict(x=0.50, y=0.48, size=36, font="Helvetica-Bold", align="center", color=(0, 0, 0)),
    "course": dict(x=0.50, y=0.64, size=24, font="Helvetica-Bold", align="center", color=(0, 0, 0)),
    "date":   dict(x=0.15, y=0.88, size=14, font="Helvetica",      align="left",   color=(0, 0, 0)),
    "id":     dict(x=0.15, y=0.93, size=11, font="Helvetica",      align="left",   color=(0.3, 0.3, 0.3)),
}
QR_X, QR_Y, QR_SIZE = 0.80, 0.74, 90   # top-left corner of QR (fractions), size in points
# -----------------------------------------------------------------------

REG = Path("docs/data/certificates.json")
PDF_DIR = Path("docs/pdf"); PDF_DIR.mkdir(parents=True, exist_ok=True)

template = next(Path(".").glob("certificate.*"), None)
if template is None:
    raise SystemExit("No template found. Upload certificate.png, .jpg or .pdf to the main folder.")
is_pdf = template.suffix.lower() == ".pdf"

if is_pdf:
    from pypdf import PdfReader, PdfWriter
    box = PdfReader(str(template)).pages[0].mediabox
    W, H = float(box.width), float(box.height)
else:
    iw, ih = Image.open(template).size
    W = 842.0
    H = W * ih / iw

def build(row, cid, issued):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    if not is_pdf:
        c.drawImage(str(template), 0, 0, W, H)

    def put(key, s):
        f = FIELDS[key]
        c.setFont(f["font"], f["size"]); c.setFillColorRGB(*f["color"])
        x, y = W * f["x"], H * (1 - f["y"])
        (c.drawCentredString if f["align"] == "center" else c.drawString)(x, y, s)

    put("name", row["student"])
    put("course", row["course_name"])
    put("date", f"Date: {issued}")
    put("id", f"ID: {cid}")

    qbuf = io.BytesIO()
    qrcode.make(f"{BASE_URL}?id={cid}").save(qbuf); qbuf.seek(0)
    c.drawImage(ImageReader(qbuf), W * QR_X, H * (1 - QR_Y) - QR_SIZE, QR_SIZE, QR_SIZE)
    c.showPage(); c.save()
    buf.seek(0)

    if not is_pdf:
        return buf.getvalue()
    page = PdfReader(str(template)).pages[0]
    page.merge_page(PdfReader(buf).pages[0])
    out = io.BytesIO(); w = PdfWriter(); w.add_page(page); w.write(out)
    return out.getvalue()

registry = json.loads(REG.read_text()) if REG.exists() else []
year = datetime.date.today().year
issued = str(datetime.date.today())

for row in csv.DictReader(open("input/completions.csv", encoding="utf-8")):
    if not row.get("student"):
        continue
    if any(r["student"] == row["student"] and r["course"] == row["course_name"] for r in registry):
        continue
    n = sum(1 for r in registry if f"-{row['course_code']}-" in r["id"]) + 1
    cid = f"TA-{year}-{row['course_code']}-{n:04d}"
    data = build(row, cid, issued)
    (PDF_DIR / f"{cid}.pdf").write_bytes(data)
    registry.append({
        "id": cid, "student": row["student"], "course": row["course_name"],
        "issued": issued, "sha256": hashlib.sha256(data).hexdigest()
    })
    print("Issued", cid)

REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
