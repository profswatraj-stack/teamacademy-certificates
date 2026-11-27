"""Generate Team Academy completion certificates from the approved CSV.

A CSV row is considered approved when an authorized Team Academy member commits
it to input/completions.csv. New rows must include completion_date (YYYY-MM-DD)
and approved_by (use a staff code/initials, not private contact information).
"""
import csv
import datetime
import hashlib
import io
import json
import re
from pathlib import Path

import fitz
import qrcode
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

BASE_URL = "https://profswatraj-stack.github.io/teamacademy-certificates/"
DATE_FORMAT = "%d %B %Y"

# Canonical codes used in certificate IDs. Keep these stable after issuing.
COURSE_CODES = {
    "AI": "AI", "MSO": "MSO", "PYTHON": "PYTHON",
    "DA": "DA", "DATA ANALYTICS": "DA",
    "GENAI": "GENAI", "GENERATIVE AI": "GENAI",
}

FIELDS = {
    "name": dict(x=0.106, y=0.339, size=28, font="Times-Bold"),
    "date": dict(x=0.108, y=0.654, size=16, font="Times-Roman"),
    "cert_no": dict(x=0.889, y=0.665, size=16, font="Times-Roman"),
}
NAME_MAX_WIDTH = 0.55
COURSE = dict(x=0.106, y=0.521, size=28, min_size=16, font="Times-Bold",
              max_width=0.60, leading=1.10, max_lines=2)
COVERS = [
    (0.100, 0.300, 0.555, 0.052),
    (0.100, 0.482, 0.600, 0.110),
    (0.1045, 0.600, 0.285, 0.085),
    (0.625, 0.600, 0.285, 0.115),
    # Cover the fixed Python/PMP badge embedded in certificate.jpg. The QR is
    # drawn afterward in its original location.
    (0.725, 0.315, 0.190, 0.285),
]
# Keep the QR code in its existing right-side position. The old static badge is
# masked from the background template and replaced by a course-specific badge
# near the top-right of the certificate.
QR_X, QR_Y, QR_SIZE = 0.78, 0.45, 85
LABEL = dict(x=0.83, y=0.60, size=8, text="Scan to verify")
BADGE = dict(x=0.755, top=0.105, width=0.17, height=0.105)
COURSE_BADGE_LABELS = {
    "AI": "badges/AI Business Practitioner @2x.png",
    "MSO": "MICROSOFT OFFICE",
    "PYTHON": "PYTHON",
    "DA": "DATA ANALYTICS",
    "GENAI": "GENERATIVE AI",
}

REG = Path("docs/data/certificates.json")
PDF_DIR = Path("docs/pdf")
IMG_DIR = Path("docs/img")
PDF_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)


def find_template(code):
    for folder, stem in (("templates", code), (".", "certificate")):
        for ext in (".jpg", ".jpeg", ".png"):
            path = Path(folder) / (stem + ext)
            if path.exists():
                return path
    return None


def wrap(text, font, size, max_w):
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if stringWidth(candidate, font, size) <= max_w or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def parse_completion_date(value, existing=None):
    value = (value or "").strip()
    if value:
        try:
            return datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Invalid completion_date {value!r}; use YYYY-MM-DD") from exc
    # Backward compatibility for the repository's already-issued legacy row.
    if existing:
        for key in ("completed", "issued"):
            try:
                return datetime.date.fromisoformat(existing.get(key, ""))
            except (TypeError, ValueError):
                pass
    raise ValueError("New certificate rows must include completion_date (YYYY-MM-DD).")


def normalize_code(value):
    key = (value or "").strip().upper()
    if key not in COURSE_CODES:
        allowed = "AI, MSO, PYTHON, DA (Data Analytics), GENAI (Generative AI)"
        raise ValueError(f"Unsupported course_code {value!r}. Use one of: {allowed}.")
    return COURSE_CODES[key]


def build(row, cid, completed, template):
    iw, ih = Image.open(template).size
    page_w = 842.0
    page_h = page_w * ih / iw
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.drawImage(str(template), 0, 0, page_w, page_h)

    pdf.setFillColorRGB(1, 1, 1)
    for fx, ft, fw, fh in COVERS:
        pdf.rect(page_w * fx, page_h * (1 - ft - fh), page_w * fw,
                 page_h * fh, stroke=0, fill=1)
    pdf.setFillColorRGB(0, 0, 0)

    # Draw a dynamic course badge at the top-right. This is independent of the
    # QR code, which remains in its original position below.
    badge_x = page_w * BADGE["x"]
    badge_w = page_w * BADGE["width"]
    badge_h = page_h * BADGE["height"]
    badge_y = page_h * (1 - BADGE["top"]) - badge_h
    pdf.setFillColor(colors.HexColor("#142B55"))
    pdf.setStrokeColor(colors.HexColor("#35C5D8"))
    pdf.setLineWidth(2.2)
    pdf.roundRect(badge_x, badge_y, badge_w, badge_h, 10, stroke=1, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(badge_x + badge_w / 2, badge_y + badge_h * 0.67, "TEAM ACADEMY")
    pdf.setStrokeColor(colors.HexColor("#35C5D8"))
    pdf.setLineWidth(0.8)
    pdf.line(badge_x + 12, badge_y + badge_h * 0.52, badge_x + badge_w - 12, badge_y + badge_h * 0.52)
    course_badge_text = COURSE_BADGE_LABELS.get(row["course_code"], row["course_code"])
    badge_font = 7.5
    while stringWidth(course_badge_text, "Helvetica-Bold", badge_font) > badge_w - 12 and badge_font > 5:
        badge_font -= 0.5
    pdf.setFont("Helvetica-Bold", badge_font)
    pdf.drawCentredString(badge_x + badge_w / 2, badge_y + badge_h * 0.27, course_badge_text)
    pdf.setFillColor(colors.black)

    name_field = FIELDS["name"]
    name_size = name_field["size"]
    while stringWidth(row["student"], name_field["font"], name_size) > page_w * NAME_MAX_WIDTH and name_size > 12:
        name_size -= 1
    pdf.setFont(name_field["font"], name_size)
    pdf.drawString(page_w * name_field["x"], page_h * (1 - name_field["y"]), row["student"])

    course_field = COURSE
    course_size = course_field["size"]
    while True:
        lines = wrap(row["course_name"], course_field["font"], course_size,
                     page_w * course_field["max_width"])
        if len(lines) <= course_field["max_lines"] or course_size <= course_field["min_size"]:
            break
        course_size -= 1
    pdf.setFont(course_field["font"], course_size)
    for index, line in enumerate(lines[:course_field["max_lines"]]):
        pdf.drawString(page_w * course_field["x"],
                       page_h * (1 - course_field["y"]) - index * course_size * course_field["leading"],
                       line)

    date_field = FIELDS["date"]
    pdf.setFont(date_field["font"], date_field["size"])
    pdf.drawString(page_w * date_field["x"], page_h * (1 - date_field["y"]),
                   "Completed on " + completed.strftime(DATE_FORMAT))

    number_field = FIELDS["cert_no"]
    pdf.setFont(number_field["font"], number_field["size"])
    pdf.drawRightString(page_w * number_field["x"], page_h * (1 - number_field["y"]),
                        "Certificate No: " + cid)

    qr_buffer = io.BytesIO()
    qrcode.make(f"{BASE_URL}?id={cid}").save(qr_buffer)
    qr_buffer.seek(0)
    pdf.drawImage(ImageReader(qr_buffer), page_w * QR_X,
                  page_h * (1 - QR_Y) - QR_SIZE, QR_SIZE, QR_SIZE)
    pdf.setFont("Helvetica", LABEL["size"])
    pdf.drawCentredString(page_w * LABEL["x"], page_h * (1 - LABEL["y"]), LABEL["text"])
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def load_registry():
    if not REG.exists():
        return []
    records = json.loads(REG.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("certificates.json must contain a JSON array.")
    return records


def next_certificate_id(registry, issue_year, course_code):
    pattern = re.compile(rf"^TA-{issue_year}-{re.escape(course_code)}-(\d{{4,}})$")
    used = [int(match.group(1)) for record in registry
            if (match := pattern.match(str(record.get("id", ""))))]
    return f"TA-{issue_year}-{course_code}-{max(used, default=0) + 1:04d}"


def main():
    registry = load_registry()
    today = datetime.date.today()
    seen_rows = set()

    with open("input/completions.csv", newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))

    for line_number, raw in enumerate(rows, start=2):
        row = {key: (value or "").strip() for key, value in raw.items()}
        if not row.get("student"):
            continue
        if not row.get("course_name"):
            raise ValueError(f"CSV line {line_number}: course_name is required.")

        course_code = normalize_code(row.get("course_code"))
        row["course_code"] = course_code
        row["student"] = row["student"].strip()
        row["course_name"] = row["course_name"].strip()

        # Match by student + course + completion date, allowing the original
        # three-column legacy row to retain its existing certificate ID.
        possible_existing = next((record for record in registry
                                  if record.get("student") == row["student"]
                                  and record.get("course") == row["course_name"]), None)
        completed = parse_completion_date(row.get("completion_date"), possible_existing)
        row_key = (row["student"].casefold(), row["course_name"].casefold(), str(completed))
        if row_key in seen_rows:
            raise ValueError(f"Duplicate CSV entry on line {line_number}: same student, course and completion date.")
        seen_rows.add(row_key)

        existing = next((record for record in registry
                         if record.get("student", "").casefold() == row["student"].casefold()
                         and record.get("course", "").casefold() == row["course_name"].casefold()
                         and (record.get("completed") or record.get("issued")) == str(completed)), None)
        # A legacy row has no completed field; preserve its old record/ID.
        if existing is None and possible_existing and not row.get("completion_date"):
            existing = possible_existing

        approver = row.get("approved_by", "")
        if not existing and not approver:
            raise ValueError(f"CSV line {line_number}: approved_by is required for a new certificate. Use a staff code or initials.")

        template = find_template(course_code)
        if template is None:
            raise ValueError(f"No certificate template found for {course_code}; add templates/{course_code}.jpg or use certificate.jpg.")

        if existing:
            certificate_id = existing["id"]
            try:
                issued = datetime.date.fromisoformat(existing["issued"])
            except (KeyError, TypeError, ValueError):
                issued = today
        else:
            certificate_id = next_certificate_id(registry, today.year, course_code)
            issued = today

        pdf_bytes = build(row, certificate_id, completed, template)
        (PDF_DIR / f"{certificate_id}.pdf").write_bytes(pdf_bytes)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            document[0].get_pixmap(dpi=110).save(str(IMG_DIR / f"{certificate_id}.jpg"))

        credential_url = f"{BASE_URL}?id={certificate_id}"
        record = {
            "id": certificate_id,
            "student": row["student"],
            "course": row["course_name"],
            "course_code": course_code,
            "completed": str(completed),
            "issued": str(issued),
            "credential_url": credential_url,
            "status": "active",
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        }
        if existing:
            existing.update(record)
            print("Regenerated", certificate_id)
        else:
            registry.append(record)
            print("Issued", certificate_id)

    REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
