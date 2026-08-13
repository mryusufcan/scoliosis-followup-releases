from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Line, Circle, String

from modular_app.database.exam_repository import ExamRepository


def _font_name() -> str:
    """Use a Unicode-capable Windows font when available; retain a safe fallback."""
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if font_path.exists():
        pdfmetrics.registerFont(TTFont("FollowUpArial", str(font_path)))
        return "FollowUpArial"
    return "Helvetica"


def _table(data: list[list[str]], widths: list[float], font: str) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#bdc3c7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7f8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _cobb_chart(rows: list[dict], font: str) -> Drawing | None:
    if not rows:
        return None
    chronological = list(reversed(rows))
    values = [float(row["angle_degrees"]) for row in chronological]
    drawing = Drawing(480, 150)
    left, bottom, width, height = 40, 28, 420, 96
    lower, upper = min(values), max(values)
    pad = max(2.0, (upper - lower) * .2)
    lower, upper = max(0., lower - pad), upper + pad
    span = max(1., upper - lower)
    drawing.add(Line(left, bottom, left + width, bottom, strokeColor=colors.HexColor("#7f8c8d")))
    drawing.add(Line(left, bottom, left, bottom + height, strokeColor=colors.HexColor("#7f8c8d")))
    drawing.add(String(2, bottom + height - 2, f"{upper:.1f}", fontName=font, fontSize=7))
    drawing.add(String(2, bottom - 2, f"{lower:.1f}", fontName=font, fontSize=7))
    points = []
    for index, (row, value) in enumerate(zip(chronological, values)):
        x = left + width / 2 if len(values) == 1 else left + index * width / (len(values) - 1)
        y = bottom + (value - lower) / span * height
        points.append((x, y, row, value))
    for first, second in zip(points, points[1:]):
        drawing.add(Line(first[0], first[1], second[0], second[1], strokeColor=colors.HexColor("#3498db"), strokeWidth=1.5))
    for x, y, row, value in points:
        drawing.add(Circle(x, y, 2.5, fillColor=colors.HexColor("#2ecc71"), strokeColor=colors.HexColor("#2ecc71")))
        drawing.add(String(x - 10, y + 7, f"{value:.1f}", fontName=font, fontSize=7))
        drawing.add(String(x - 15, 10, str(row.get("exam_date", ""))[-6:], fontName=font, fontSize=6))
    return drawing


def generate_follow_up_report(
    repository: ExamRepository,
    patient_id: str,
    patient_name: str,
    destination: str | Path,
    clinical_note: str = "",
    overlay_snapshot: str | Path | None = None,
    prepared_by: str = "",
    prepared_role: str = "",
) -> Path:
    """Create a data-only patient follow-up PDF from local SQLite records."""
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    font = _font_name()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontName=font, fontSize=17, leading=21, textColor=colors.HexColor("#2c3e50"))
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontName=font, fontSize=11, leading=14, textColor=colors.HexColor("#2c3e50"), spaceBefore=10, spaceAfter=5)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName=font, fontSize=9, leading=12)
    story = [
        Paragraph("Scoliosis Follow-Up - Takip Raporu", title_style),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Hasta:</b> {patient_name or 'Hasta'} &nbsp;&nbsp; <b>ID:</b> {patient_id}", body_style),
        Paragraph("Bu belge kaydedilmis tetkik, olcum ve karsilastirma verilerinin otomatik ozetidir. Klinik karar yerine gecmez.", body_style),
        Spacer(1, 4 * mm),
    ]

    profile = repository.get_patient_profile(patient_id)
    story.append(Paragraph("Hasta Kartı", heading_style))
    profile_data = [
        ["Tanı / başlık", str(profile.get("diagnosis", "")) or "—"],
        ["Sorumlu hekim", str(profile.get("referring_physician", "")) or "—"],
        ["Planlanan kontrol", str(profile.get("next_follow_up_date", "")) or "—"],
        ["Tedavi / takip planı", str(profile.get("treatment_plan", "")) or "—"],
    ]
    story.append(_table([["Alan", "Yerel takip kaydı"], *profile_data], [44 * mm, 139 * mm], font))

    try:
        alert_threshold = float(repository.get_setting("follow_up/cobb_alert_threshold", "5") or 5)
    except ValueError:
        alert_threshold = 5.0
    alerts = repository.follow_up_alerts(patient_id, alert_threshold)
    story.append(Paragraph("Takip Uyarıları", heading_style))
    alert_data = [["Durum", "Kontrol", "Ayrıntı"]]
    for row in alerts:
        alert_data.append([str(row["severity"]), str(row["kind"]), str(row["details"])])
    if len(alert_data) == 1:
        alert_data.append(["Bilgi", "Takip uyarısı", "Tanımlı eşiği aşan yerel takip uyarısı bulunmadı."])
    story.append(_table(alert_data, [22 * mm, 40 * mm, 121 * mm], font))

    exams = repository.list_patient_follow_up(patient_id)
    story.append(Paragraph("Tetkik Ozeti", heading_style))
    exam_data = [["Tarih", "Bolge", "Modalite", "Tetkik", "Son Cobb", "Overlay"]]
    for row in exams:
        angle = row.get("latest_cobb")
        exam_data.append([
            str(row.get("exam_date", "")), str(row.get("body_part", "")), str(row.get("modality", "")),
            str(row.get("study_description", ""))[:38], f"{float(angle):.2f} deg" if angle is not None else "-",
            str(row.get("overlay_session_count", 0)),
        ])
    if len(exam_data) == 1:
        exam_data.append(["-", "-", "-", "Kayit yok", "-", "-"])
    story.append(_table(exam_data, [24*mm, 27*mm, 20*mm, 62*mm, 26*mm, 20*mm], font))

    measurements = list(reversed(repository.list_cobb_measurements(patient_id)))
    story.append(Paragraph("Cobb Olcum Gecmisi", heading_style))
    measurement_data = [["Tetkik tarihi", "Goruntu", "Taraf", "Cobb acisi", "Durum"]]
    for row in measurements:
        measurement_data.append([
            str(row.get("exam_date", "")), Path(str(row.get("dicom_path", ""))).name[:42],
            str(row.get("side", "")).upper(), f"{float(row.get('angle_degrees', 0.0)):.2f} deg",
            f"Kilitli / {row.get('verified_by', '')}" if bool(row.get("is_locked")) else "Taslak",
        ])
    if len(measurement_data) == 1:
        measurement_data.append(["-", "Kayit yok", "-", "-", "-"])
    story.append(_table(measurement_data, [29*mm, 78*mm, 18*mm, 27*mm, 31*mm], font))
    chart = _cobb_chart(repository.list_cobb_measurements(patient_id), font)
    if chart:
        story.append(Spacer(1, 3 * mm))
        story.append(chart)

    sessions = repository.list_comparison_sessions(patient_id)
    story.append(Paragraph("Kayitli Overlay Oturumlari", heading_style))
    session_data = [["Kayit", "Referans", "Karsilastirma", "Hizalama", "Not"]]
    for row in sessions:
        alignment = f"X {float(row.get('overlay_offset_x', 0)):+.0f}; Y {float(row.get('overlay_offset_y', 0)):+.0f}; Z {float(row.get('overlay_scale', 1)):.2f}"
        session_data.append([
            str(row.get("created_at", ""))[:16], Path(str(row.get("reference_path", ""))).name[:18],
            Path(str(row.get("comparison_path", ""))).name[:18], alignment, str(row.get("notes", ""))[:42],
        ])
    if len(session_data) == 1:
        session_data.append(["-", "Kayit yok", "-", "-", "-"])
    story.append(_table(session_data, [29*mm, 35*mm, 35*mm, 45*mm, 39*mm], font))

    labels = repository.list_vertebra_labels(patient_id)
    if labels:
        story.append(Paragraph("Omur Etiketleri", heading_style))
        label_data = [["Görüntü", "Seviye", "Not", "Ekleyen"]]
        for row in labels:
            label_data.append([
                Path(str(row.get("dicom_path", ""))).name[:35], str(row.get("vertebra", "")),
                str(row.get("note", ""))[:60], str(row.get("created_by", "")) or "—",
            ])
        story.append(_table(label_data, [58 * mm, 24 * mm, 70 * mm, 31 * mm], font))

    if overlay_snapshot and Path(overlay_snapshot).is_file():
        story.append(Paragraph("Aktif Overlay Onizlemesi", heading_style))
        preview = Image(str(overlay_snapshot))
        preview._restrictSize(170 * mm, 110 * mm)
        story.append(preview)
    if clinical_note.strip():
        story.append(Paragraph("Kullanici Notu", heading_style))
        story.append(Paragraph(clinical_note.strip().replace("\n", "<br/>"), body_style))

    story.extend([
        Spacer(1, 6 * mm),
        Paragraph(f"Hazırlayan: {prepared_by or 'Yerel kullanıcı'}" + (f" ({prepared_role})" if prepared_role else ""), body_style),
        Spacer(1, 7 * mm),
        Paragraph("Onaylayan hekim / imza: ______________________________________________", body_style),
        Paragraph("Not: Cobb olcumleri kullanicinin uygulamadaki dort nokta secimine dayanir. Sonuclar klinik olarak yetkili bir uzman tarafindan degerlendirilmelidir.", body_style),
    ])
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=14*mm, leftMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm, title="Scoliosis Follow-Up Takip Raporu")
    document.build(story)
    return output
