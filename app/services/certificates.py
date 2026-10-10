from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas


def generate_certificate(name: str, event_name: str, issuer: str, issue_date: date, certificate_id: str) -> bytes:
    """Render the project's single predefined certificate design as a PDF."""
    buffer = BytesIO()
    width, height = landscape(letter)
    pdf = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=1)
    pdf.setTitle(f"Certificate - {name}")
    pdf.setAuthor(issuer)
    pdf.setSubject(f"{event_name} | {certificate_id}")

    navy = colors.HexColor("#10243A")
    blue = colors.HexColor("#176B87")
    gold = colors.HexColor("#C99B45")
    muted = colors.HexColor("#647789")
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(navy)
    pdf.setLineWidth(2.2)
    pdf.roundRect(25, 25, width - 50, height - 50, 8, fill=0, stroke=1)
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(0.8)
    pdf.roundRect(33, 33, width - 66, height - 66, 6, fill=0, stroke=1)

    def centered(text: str, y: int, font: str, size: int, color) -> None:
        pdf.setFillColor(color)
        pdf.setFont(font, size)
        pdf.drawCentredString(width / 2, y, text)

    centered("CERTIFICATE OF COMPLETION", 505, "Helvetica-Bold", 12, blue)
    pdf.setStrokeColor(gold)
    pdf.line(width / 2 - 34, 489, width / 2 + 34, 489)
    centered("This certificate is proudly presented to", 450, "Helvetica", 15, muted)
    centered(name, 395, "Helvetica-Bold", 31, navy)
    pdf.setStrokeColor(colors.HexColor("#D8E0E6"))
    pdf.line(width * 0.23, 378, width * 0.77, 378)
    centered("for successfully participating in", 345, "Helvetica", 14, muted)
    centered(event_name, 310, "Helvetica-Bold", 19, navy)

    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(82, 105, f"ISSUED {issue_date.strftime('%B %d, %Y').upper()}")
    pdf.setStrokeColor(colors.HexColor("#9AAAB6"))
    pdf.line(82, 145, 250, 145)
    pdf.setFillColor(navy)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(82, 127, issuer)
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(width - 82, 105, f"CERTIFICATE ID  {certificate_id}")
    pdf.setStrokeColor(colors.HexColor("#9AAAB6"))
    pdf.line(width - 250, 145, width - 82, 145)
    pdf.setFillColor(navy)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(width - 82, 127, "AUTHORIZED ISSUER")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
