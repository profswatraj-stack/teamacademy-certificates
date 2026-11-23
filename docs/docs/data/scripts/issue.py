import csv, json, hashlib, datetime, qrcode
from pathlib import Path
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

BASE_URL = "https://profswatraj-stack.github.io/teamacademy-certificates/"
REG = Path("docs/data/certificates.json")
PDF_DIR = Path("docs/pdf"); PDF_DIR.mkdir(parents=True, exist_ok=True)

registry = json.loads(REG.read_text()) if REG.exists() else []
year = datetime.date.today().year

for row in csv.DictReader(open("input/completions.csv", encoding="utf-8")):
    # skip if student already has this course
    if any(r["student"] == row["student"] and r["course"] == row["course_name"] for r in registry):
        continue
    n = sum(1 for r in registry if f"-{row['course_code']}-" in r["id"]) + 1
    cid = f"TA-{year}-{row['course_code']}-{n:04d}"

    # QR code
    qr_path = f"/tmp/{cid}.png"
    qrcode.make(f"{BASE_URL}?id={cid}").save(qr_path)

    # PDF
    pdf_path = PDF_DIR / f"{cid}.pdf"
    w, h = landscape(A4)
    c = canvas.Canvas(str(pdf_path), pagesize=(w, h))
    c.setFont("Helvetica-Bold", 36); c.drawCentredString(w/2, h-120, "Certificate of Completion")
    c.setFont("Helvetica", 18);      c.drawCentredString(w/2, h-180, "This is to certify that")
    c.setFont("Helvetica-Bold", 30); c.drawCentredString(w/2, h-230, row["student"])
    c.setFont("Helvetica", 18);      c.drawCentredString(w/2, h-280, "has successfully completed")
    c.setFont("Helvetica-Bold", 24); c.drawCentredString(w/2, h-320, row["course_name"])
    c.setFont("Helvetica", 12)
    c.drawString(60, 60, f"ID: {cid}   Issued: {datetime.date.today()}")
    c.drawString(60, 44, f"Verify: {BASE_URL}?id={cid}")
    c.drawImage(qr_path, w-170, 40, 110, 110)
    c.drawString(60, 90, "TeamAcademy")
    c.save()

    registry.append({
        "id": cid, "student": row["student"], "course": row["course_name"],
        "issued": str(datetime.date.today()),
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    })
    print("Issued", cid)

REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
