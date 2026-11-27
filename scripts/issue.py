import csv, json, hashlib, datetime, io, qrcode, fitz
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

BASE_URL = "https://profswatraj-stack.github.io/teamacademy-certificates/"
DATE_FORMAT = "%d %B %Y"        # "23 November 2026". Use "%B %Y" for "November 2026"

# ---------- LAYOUT (fractions of the page: x from left, y from top) ----------
# For text, y is the baseline of the text.
FIELDS = {
    "name":    dict(x=0.106, y=0.339, size=28, font="Times-Bold"),
    "date":    dict(x=0.108, y=0.654, size=16, font="Times-Roman"),
    "cert_no": dict(x=0.889, y=0.665, size=16, font="Times-Roman"),   # right-aligned
}
NAME_MAX_WIDTH = 0.55           # name shrinks if wider than this share of the page

# Course title: starts at x,y; wraps to max_width; shrinks from size to min_size to fit max_lines
COURSE = dict(x=0.106, y=0.521, size=28, min_size=16, font="Times-Bold",
              max_width=0.60, leading=1.10, max_lines=2)

# White boxes hiding the printed placeholders: (x, top, width, height)
COVERS = [
    (0.100,  0.300, 0.555, 0.052),   # printed name placeholder
    (0.100,  0.482, 0.600, 0.110),   # printed course title (2 lines)
    # The source artwork has the old date and certificate number printed in it.
    # Extend these masks above and below the original text to remove every trace.
    (0.1045, 0.600, 0.285, 0.085),   # printed award date
    (0.625,  0.600, 0.285, 0.115),   # printed certificate number
]

# QR code: top-left corner (fractions) and size in points
QR_X, QR_Y, QR_SIZE = 0.78, 0.45, 85
LABEL = dict(x=0.83, y=0.60, size=8, text="Scan to verify")
# -----------------------------------------------------------------------------

REG = Path("docs/data/certificates.json")
PDF_DIR = Path("docs/pdf"); PDF_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = Path("docs/img"); IMG_DIR.mkdir(parents=True, exist_ok=True)

def find_template(code):
    # templates/<COURSE_CODE>.jpg first, then certificate.jpg in the main folder
    for folder, stem in (("templates", code), (".", "certificate")):
        for ext in (".jpg", ".jpeg", ".png"):
            p = Path(folder) / (stem + ext)
            if p.exists():
                return p
    return None

def wrap(text, font, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if stringWidth(t, font, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)
    return lines

def build(row, cid, today, tpl):
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

    # student name (shrinks if long)
    f = FIELDS["name"]; size = f["size"]
    while stringWidth(row["student"], f["font"], size) > W * NAME_MAX_WIDTH and size > 12:
        size -= 1
    c.setFont(f["font"], size)
    c.drawString(W * f["x"], H * (1 - f["y"]), row["student"])

    # course title (wrapped, shrinks to fit)
    cf = COURSE
    size = cf["size"]
    while True:
        lines = wrap(row["course_name"], cf["font"], size, W * cf["max_width"])
        if len(lines) <= cf["max_lines"] or size <= cf["min_size"]:
            break
        size -= 1
    c.setFont(cf["font"], size)
    for i, line in enumerate(lines):
        c.drawString(W * cf["x"], H * (1 - cf["y"]) - i * size * cf["leading"], line)

    # date
    f = FIELDS["date"]
    c.setFont(f["font"], f["size"])
    c.drawString(W * f["x"], H * (1 - f["y"]), "Awarded on " + today.strftime(DATE_FORMAT))

    # certificate number (right-aligned)
    f = FIELDS["cert_no"]
    c.setFont(f["font"], f["size"])
    c.drawRightString(W * f["x"], H * (1 - f["y"]), "Certificate No: " + cid)

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

# Rebuild certificates already present in the registry as well as issuing new ones.
# This makes template/layout corrections apply to existing certificate IDs too.
for row in csv.DictReader(open("input/completions.csv", encoding="utf-8")):
    if not row.get("student"):
        continue

    existing = next((r for r in registry
                     if r["student"] == row["student"]
                     and r["course"] == row["course_name"]), None)

    tpl = find_template(row["course_code"])
    if tpl is None:
        print("SKIPPED (no template):", row["student"], row["course_code"])
        continue

    if existing:
        cid = existing["id"]
        # Preserve the original issue date recorded in the registry.
        try:
            issued = datetime.date.fromisoformat(existing["issued"])
        except (KeyError, TypeError, ValueError):
            issued = today
    else:
        n = sum(1 for r in registry if f"-{row['course_code']}-" in r["id"]) + 1
        cid = f"TA-{today.year}-{row['course_code']}-{n:04d}"
        issued = today

    data = build(row, cid, issued, tpl)
    (PDF_DIR / f"{cid}.pdf").write_bytes(data)
    with fitz.open(stream=data, filetype="pdf") as doc:
        doc[0].get_pixmap(dpi=110).save(str(IMG_DIR / f"{cid}.jpg"))

    record = {
        "id": cid, "student": row["student"], "course": row["course_name"],
        "issued": str(issued), "sha256": hashlib.sha256(data).hexdigest()
    }
    if existing:
        existing.update(record)
        print("Regenerated", cid)
    else:
        registry.append(record)
        print("Issued", cid)

REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
