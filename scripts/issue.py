import csv, json, hashlib, datetime, io, qrcode
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

BASE_URL = "https://profswatraj-stack.github.io/teamacademy-certificates/"

# ---------- LAYOUT (fractions of the page: x from left, y from top) ----------
# For text, y is the baseline of the text.
FIELDS = {
    "name":    dict(x=0.106, y=0.339, size=26, font="Times-Bold",  align="left"),
    "date":    dict(x=0.108, y=0.654, size=16, font="Times-Roman", align="left"),
    "cert_no": dict(x=0.889, y=0.665, size=16, font="Times-Roman", align="right"),
}
NAME_MAX_WIDTH = 0.55          # name shrinks automatically if longer than this share of the page

# White boxes that hide the printed placeholders: (x, top, width, height)
COVERS = [
    (0.100, 0.300, 0.555, 0.052),   # "Name"
    (0.1045, 0.630, 0.240, 0.040),  # "Awarded on September 2025"
    (0.645, 0.636, 0.253, 0.040),   # "Certificate No: 33696"
]

# QR code: top-left corner (fractions) and size in points
QR_X, QR_Y, QR_SIZE = 0.78, 0.45, 85
LABEL = dict(x=0.83, y=0.60, size=8, text="Scan to verify")
# -----------------------------------------------------------------------------

REG = Path("docs/data/certificates.json")
PDF_DIR = Path("docs/pdf"); PDF_DIR.mkdir(parents=True, exist_ok=True)

def find_template(code):
    # first look for templates/<COURSE_CODE>.jpg, then certificate.jpg in the main folder
    for folder, stem in (("templates", code), (".", "certificate")):
        for ext in (".jpg", ".jpeg", ".png"):
            p = Path(folder) / (stem + ext)
            if p.exists():
                return p
    return None

def build(row, cid, issued_date, tpl):
    iw, ih = Image.open(tpl).size
    W = 842.0
    H = W * ih / iw
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.drawImage(str(tpl), 0, 0, W, H)

    # hide the printed placeholders
    c.setFillColorRGB(1, 1, 1)
    for fx, ft, fw, fh in COVERS:
        c.rect(W * fx, H * (1 - ft - fh), W * fw, H * fh, stroke=0, fill=1)

    c.setFillColorRGB(0, 0, 0)

    def put(key, text):
        f = FIELDS[key]
        size = f["size"]
        if key == "name":
            while stringWidth(text, f["font"], size) > W * NAME_MAX_WIDTH and size > 12:
                size -= 1
        c.setFont(f["font"], size)
        x, y = W * f["x"], H * (1 - f["y"])
        if f["align"] == "right":
            c.drawRightString(x, y, text)
        else:
            c.drawString(x, y, text)

    put("name", row["student"])
    put("date", "Awarded on " + issued_date.strftime("%B %Y"))
    put("cert_no", "Certificate No: " + cid)

    # QR code
    qbuf = io.BytesIO()
    qrcode.make(f"{BASE_URL}?id={cid}").save(qbuf); qbuf.seek(0)
    c.drawImage(ImageReader(qbuf), W * QR_X, H * (1 - QR_Y) - QR_SIZE, QR_SIZE, QR_SIZE)
    c.setFont("Helvetica", LABEL["size"])
    c.drawCentredString(W * LABEL["x"], H * (1 - LABEL["y"]), LABEL["text"])

    c.showPage(); c.save()
    return buf.getvalue()

registry = json.loads(REG.read_text()) if REG.exists() else []
today = datetime.date.today()
year = today.year

for row in csv.DictReader(open("input/completions.csv", encoding="utf-8")):
    if not row.get("student"):
        continue
    if any(r["student"] == row["student"] and r["course"] == row["course_name"] for r in registry):
        continue
    tpl = find_template(row["course_code"])
    if tpl is None:
        print("SKIPPED (no template):", row["student"], row["course_code"])
        continue
    n = sum(1 for r in registry if f"-{row['course_code']}-" in r["id"]) + 1
    cid = f"TA-{year}-{row['course_code']}-{n:04d}"
    data = build(row, cid, today, tpl)
    (PDF_DIR / f"{cid}.pdf").write_bytes(data)
    registry.append({
        "id": cid, "student": row["student"], "course": row["course_name"],
        "issued": str(today), "sha256": hashlib.sha256(data).hexdigest()
    })
    print("Issued", cid)

REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
