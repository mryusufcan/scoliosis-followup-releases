from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Line, Circle, String

from modular_app.database.exam_repository import ExamRepository
from modular_app.services.measurement_labels import display_measurement_source


_FONT_NAME_CACHE: str | None = None


def _font_name() -> str:
    """Türkçe karakterler için Windows'ta Unicode font kullan; bir kez kaydet."""
    global _FONT_NAME_CACHE
    if _FONT_NAME_CACHE is not None:
        return _FONT_NAME_CACHE
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont("FollowUpUnicode", str(font_path)))
                _FONT_NAME_CACHE = "FollowUpUnicode"
                return _FONT_NAME_CACHE
            except Exception:
                continue
    _FONT_NAME_CACHE = "Helvetica"
    return _FONT_NAME_CACHE


def _date_text(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw or "—"


def _datetime_text(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
    return raw[:19]


def _p(value: object, style: ParagraphStyle, limit: int | None = None) -> Paragraph:
    text = str(value if value not in (None, "") else "—")
    if limit is not None and len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _table(
    data: list[list[object]],
    widths: list[float],
    font: str,
    body_style: ParagraphStyle,
    header_style: ParagraphStyle,
    font_size: float = 7.5,
) -> Table:
    converted = []
    for row_index, row in enumerate(data):
        style = header_style if row_index == 0 else body_style
        converted.append([
            value if isinstance(value, Paragraph) else _p(value, style)
            for value in row
        ])

    table = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cdd1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8f9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _section_title(text: str, style: ParagraphStyle) -> list:
    return [Spacer(1, 2.5 * mm), Paragraph(text, style), Spacer(1, 1 * mm)]


def _measurement_summary(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "first": None,
            "latest": None,
            "delta": None,
            "minimum": None,
            "maximum": None,
            "locked": 0,
        }

    chronological = list(reversed(rows))
    values = [float(row.get("angle_degrees", 0.0)) for row in chronological]
    return {
        "count": len(rows),
        "first": chronological[0],
        "latest": chronological[-1],
        "delta": values[-1] - values[0],
        "minimum": min(values),
        "maximum": max(values),
        "locked": sum(1 for row in rows if bool(row.get("is_locked"))),
    }


def _summary_cards(
    summary: dict,
    font: str,
    body_style: ParagraphStyle,
    header_style: ParagraphStyle,
) -> Table:
    if not summary["count"]:
        data = [["Ölçüm", "İlk Cobb", "Son Cobb", "Toplam değişim", "Min / Maks"],
                ["0", "—", "—", "—", "—"]]
    else:
        first = summary["first"]
        latest = summary["latest"]
        delta = float(summary["delta"])
        data = [
            ["Ölçüm", "İlk Cobb", "Son Cobb", "Toplam değişim", "Min / Maks"],
            [
                f"{summary['count']} ({summary['locked']} kilitli)",
                f"{float(first.get('angle_degrees', 0.0)):.2f}°\n{_date_text(first.get('exam_date'))}",
                f"{float(latest.get('angle_degrees', 0.0)):.2f}°\n{_date_text(latest.get('exam_date'))}",
                f"{delta:+.2f}°",
                f"{float(summary['minimum']):.2f}° / {float(summary['maximum']):.2f}°",
            ],
        ]

    table = _table(
        data,
        [34 * mm, 39 * mm, 39 * mm, 36 * mm, 35 * mm],
        font,
        body_style,
        header_style,
        font_size=8,
    )
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef3f6")),
    ]))
    return table


def _trend_sentence(summary: dict) -> str:
    if not summary["count"]:
        return "Kayıtlı Cobb ölçümü bulunmuyor."
    if summary["count"] == 1:
        return "Tek Cobb ölçümü mevcut; sayısal trend için en az iki ölçüm gerekir."

    delta = float(summary["delta"])
    if abs(delta) < 0.05:
        direction = "başlangıca göre belirgin sayısal değişim yoktur"
    elif delta < 0:
        direction = f"başlangıca göre {abs(delta):.2f}° azalma vardır"
    else:
        direction = f"başlangıca göre {delta:.2f}° artış vardır"

    return (
        f"İlk ve son kayıt karşılaştırıldığında {direction}. "
        "Bu ifade yalnızca ölçülen açı farkını özetler; klinik iyileşme veya kötüleşme yorumu değildir."
    )


def _cobb_chart(rows: list[dict], font: str) -> Drawing | None:
    if not rows:
        return None

    chronological = list(reversed(rows))
    values = [float(row.get("angle_degrees", 0.0)) for row in chronological]
    drawing = Drawing(500, 170)

    left, bottom, width, height = 48, 38, 430, 100
    lower, upper = min(values), max(values)
    pad = 5.0 if abs(upper - lower) < 0.1 else max(3.0, (upper - lower) * 0.20)
    lower = max(0.0, lower - pad)
    upper = upper + pad
    span = max(1.0, upper - lower)

    # grid
    for step in range(5):
        ratio = step / 4.0
        y = bottom + ratio * height
        value = lower + ratio * span
        drawing.add(Line(
            left, y, left + width, y,
            strokeColor=colors.HexColor("#e1e5e8"),
            strokeWidth=0.5,
        ))
        drawing.add(String(
            4, y - 2, f"{value:.1f}°",
            fontName=font, fontSize=7, fillColor=colors.HexColor("#7f8c8d"),
        ))

    drawing.add(Line(left, bottom, left + width, bottom, strokeColor=colors.HexColor("#7f8c8d")))
    drawing.add(Line(left, bottom, left, bottom + height, strokeColor=colors.HexColor("#7f8c8d")))

    points = []
    count = len(values)
    for index, (row, value) in enumerate(zip(chronological, values)):
        x = left + width / 2 if count == 1 else left + index * width / (count - 1)
        y = bottom + (value - lower) / span * height
        points.append((x, y, row, value))

    for first, second in zip(points, points[1:]):
        drawing.add(Line(
            first[0], first[1], second[0], second[1],
            strokeColor=colors.HexColor("#3498db"),
            strokeWidth=2,
        ))

    label_every = 1 if count <= 7 else max(1, count // 6)
    for index, (x, y, row, value) in enumerate(points):
        locked = bool(row.get("is_locked"))
        point_color = colors.HexColor("#2ecc71") if locked else colors.HexColor("#f39c12")
        drawing.add(Circle(x, y, 3, fillColor=point_color, strokeColor=point_color))
        drawing.add(String(
            x - 12, y + 7, f"{value:.1f}°",
            fontName=font, fontSize=7, fillColor=colors.HexColor("#2c3e50"),
        ))
        if index % label_every == 0 or index == count - 1:
            drawing.add(String(
                x - 18, 14, _date_text(row.get("exam_date", "")),
                fontName=font, fontSize=6, fillColor=colors.HexColor("#7f8c8d"),
            ))

    drawing.add(String(
        left, 154, "Cobb Açısı Zaman İçindeki Değişim",
        fontName=font, fontSize=9, fillColor=colors.HexColor("#2c3e50"),
    ))
    return drawing


def _page_decorator(font: str, patient_id: str):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#d5d9dc"))
        canvas.setLineWidth(0.4)
        canvas.line(14 * mm, 10 * mm, width - 14 * mm, 10 * mm)

        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#7f8c8d"))
        canvas.drawString(
            14 * mm,
            6 * mm,
            f"Scoliosis Follow-Up | Hasta ID: {patient_id}",
        )
        canvas.drawRightString(
            width - 14 * mm,
            6 * mm,
            f"Sayfa {doc.page}",
        )
        canvas.restoreState()
    return draw


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
    """Yerel hasta takip verilerinden Profesyonel Takip Raporu v2 oluştur."""

    output = Path(destination)
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")
    output.parent.mkdir(parents=True, exist_ok=True)

    font = _font_name()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#20384a"),
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#7f8c8d"),
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#20384a"),
        spaceBefore=4,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#2d3436"),
    )
    table_body_style = ParagraphStyle(
        "TableBody",
        parent=body_style,
        fontName=font,
        fontSize=7.3,
        leading=9,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=body_style,
        fontName=font,
        fontSize=7.3,
        leading=9,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=body_style,
        fontName=font,
        fontSize=8.5,
        leading=12,
        backColor=colors.HexColor("#f6f8f9"),
        borderColor=colors.HexColor("#dfe4e7"),
        borderWidth=0.5,
        borderPadding=7,
        spaceBefore=3,
        spaceAfter=3,
    )

    now = datetime.now()
    story = [
        Paragraph("Scoliosis Follow-Up", title_style),
        Paragraph("Profesyonel Hasta Takip Raporu v2", heading_style),
        Paragraph(
            f"Oluşturulma: {now.strftime('%d.%m.%Y %H:%M')} &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Hazırlayan: {escape(prepared_by or 'Yerel kullanıcı')}"
            + (f" ({escape(prepared_role)})" if prepared_role else ""),
            subtitle_style,
        ),
        Spacer(1, 4 * mm),
    ]

    # Hasta kimlik kartı
    identity = [
        ["Hasta adı", patient_name or "Hasta", "Hasta ID", patient_id],
    ]
    identity_table = _table(
        identity,
        [28 * mm, 63 * mm, 27 * mm, 65 * mm],
        font,
        table_body_style,
        table_header_style,
        font_size=8.5,
    )
    identity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf0f4")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eaf0f4")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2c3e50")),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTNAME", (0, 0), (0, -1), font),
        ("FONTNAME", (2, 0), (2, -1), font),
    ]))
    story.append(identity_table)

    story.append(Spacer(1, 2.5 * mm))
    story.append(Paragraph(
        "Bu rapor uygulamada kayıtlı tetkik, ölçüm, karşılaştırma ve takip notlarını özetler. "
        "Tek başına tanı veya tedavi kararı oluşturmaz.",
        note_style,
    ))

    # Tek bağlantıda salt-okunur rapor verisi
    bundle = repository.get_follow_up_report_bundle(patient_id)
    profile = bundle["profile"]
    raw_measurements = bundle["measurements"]
    exams = bundle["exams"]
    sessions = bundle["sessions"]
    labels = bundle["labels"]
    image_notes = bundle["image_notes"]
    alerts = bundle["alerts"]

    # Hasta kartı
    story.extend(_section_title("Hasta Kartı ve Takip Planı", heading_style))
    profile_data = [
        ["Alan", "Kayıt"],
        ["Tanı / başlık", str(profile.get("diagnosis", "")) or "—"],
        ["Sorumlu hekim", str(profile.get("referring_physician", "")) or "—"],
        ["Planlanan kontrol", _date_text(profile.get("next_follow_up_date", ""))],
        ["Tedavi / takip planı", str(profile.get("treatment_plan", "")) or "—"],
    ]
    story.append(_table(
        profile_data, [43 * mm, 140 * mm],
        font, table_body_style, table_header_style,
    ))

    # Cobb özet
    summary = _measurement_summary(raw_measurements)
    story.extend(_section_title("Cobb Takip Özeti", heading_style))
    story.append(_summary_cards(summary, font, table_body_style, table_header_style))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(_trend_sentence(summary), note_style))

    chart = _cobb_chart(raw_measurements, font)
    if chart is not None:
        story.append(Spacer(1, 2 * mm))
        story.append(chart)

    # Tetkikler
    story.extend(_section_title("Tetkik Geçmişi", heading_style))
    exam_data = [["Tarih", "Bölge", "Modalite", "Tetkik", "Son Cobb", "Overlay"]]
    for row in exams:
        angle = row.get("latest_cobb")
        angle_text = "—"
        if angle is not None:
            angle_text = f"{float(angle):.2f}°"
            angle_text += "\nKilitli" if bool(row.get("latest_cobb_locked")) else "\nTaslak"
        exam_data.append([
            _date_text(row.get("exam_date", "")),
            str(row.get("body_part", "")) or "—",
            str(row.get("modality", "")) or "—",
            str(row.get("study_description", "")) or "—",
            angle_text,
            str(row.get("overlay_session_count", 0)),
        ])
    if len(exam_data) == 1:
        exam_data.append(["—", "—", "—", "Kayıt yok", "—", "—"])
    story.append(_table(
        exam_data,
        [22 * mm, 25 * mm, 18 * mm, 67 * mm, 29 * mm, 22 * mm],
        font, table_body_style, table_header_style,
    ))

    # Ölçüm geçmişi
    measurements = list(reversed(raw_measurements))
    story.extend(_section_title("Cobb Ölçüm Geçmişi", heading_style))
    measurement_data = [["Tarih", "Görüntü", "Kaynak", "Cobb", "Kanıt", "Durum"]]
    for row in measurements:
        has_evidence = bool(str(row.get("point_data", "")).strip())
        source_uid = bool(str(row.get("source_sop_instance_uid", "")).strip())
        evidence = "4 nokta" if has_evidence else "Eski kayıt"
        if source_uid:
            evidence += " / UID"
        measurement_data.append([
            _date_text(row.get("exam_date", "")),
            Path(str(row.get("dicom_path", ""))).name,
            display_measurement_source(row.get("side", "")),
            f"{float(row.get('angle_degrees', 0.0)):.2f}°",
            evidence,
            f"Kilitli\n{row.get('verified_by', '')}" if bool(row.get("is_locked")) else "Taslak",
        ])
    if len(measurement_data) == 1:
        measurement_data.append(["—", "Kayıt yok", "—", "—", "—", "—"])
    story.append(_table(
        measurement_data,
        [22 * mm, 52 * mm, 24 * mm, 20 * mm, 29 * mm, 36 * mm],
        font, table_body_style, table_header_style,
    ))

    # Overlay kayıtları
    story.extend(_section_title("Karşılaştırma / Overlay Oturumları", heading_style))
    session_data = [["Kayıt", "Referans", "Karşılaştırma", "Hizalama", "Not"]]
    for row in sessions:
        alignment = (
            f"X {float(row.get('overlay_offset_x', 0)):+.0f}; "
            f"Y {float(row.get('overlay_offset_y', 0)):+.0f}; "
            f"Z {float(row.get('overlay_scale', 1)):.2f}"
        )
        session_data.append([
            _datetime_text(row.get("created_at", "")),
            Path(str(row.get("reference_path", ""))).name,
            Path(str(row.get("comparison_path", ""))).name,
            alignment,
            str(row.get("notes", "")) or "—",
        ])
    if len(session_data) == 1:
        session_data.append(["—", "Kayıt yok", "—", "—", "—"])
    story.append(_table(
        session_data,
        [28 * mm, 35 * mm, 35 * mm, 41 * mm, 44 * mm],
        font, table_body_style, table_header_style,
    ))

    # Omur etiketleri
    if labels:
        story.extend(_section_title("Omur Etiketleri", heading_style))
        label_data = [["Görüntü", "Seviye", "Not", "Ekleyen"]]
        for row in labels:
            label_data.append([
                Path(str(row.get("dicom_path", ""))).name,
                str(row.get("vertebra", "")),
                str(row.get("note", "")) or "—",
                str(row.get("created_by", "")) or "—",
            ])
        story.append(_table(
            label_data,
            [54 * mm, 23 * mm, 72 * mm, 34 * mm],
            font, table_body_style, table_header_style,
        ))

    # Görüntü notları v2
    story.extend(_section_title("Hasta / Görüntü Notları", heading_style))
    note_data = [["Tarih", "Tetkik / Görüntü", "Not", "Ekleyen"]]
    for row in image_notes:
        note_data.append([
            _datetime_text(row.get("created_at", "")),
            Path(str(row.get("dicom_path", ""))).name,
            str(row.get("note", "")) or "—",
            str(row.get("created_by", "")) or "—",
        ])
    if len(note_data) == 1:
        note_data.append(["—", "Kayıt yok", "—", "—"])
    story.append(_table(
        note_data,
        [28 * mm, 48 * mm, 78 * mm, 29 * mm],
        font, table_body_style, table_header_style,
    ))

    # Takip uyarıları
    story.extend(_section_title("Takip Uyarıları", heading_style))
    alert_data = [["Seviye", "Kontrol", "Ayrıntı"]]
    for row in alerts:
        alert_data.append([
            str(row.get("severity", "")),
            str(row.get("kind", "")),
            str(row.get("details", "")),
        ])
    if len(alert_data) == 1:
        alert_data.append([
            "Bilgi",
            "Takip",
            "Tanımlı yerel eşiklere göre aktif takip uyarısı bulunmadı.",
        ])
    story.append(_table(
        alert_data,
        [25 * mm, 43 * mm, 115 * mm],
        font, table_body_style, table_header_style,
    ))

    # Aktif overlay görseli
    if overlay_snapshot and Path(overlay_snapshot).is_file():
        story.extend(_section_title("Aktif Overlay Önizlemesi", heading_style))
        story.append(Paragraph(
            "Aşağıdaki görüntü, rapor oluşturulduğu anda uygulamada açık olan overlay görünümünün ekran çıktısıdır.",
            body_style,
        ))
        story.append(Spacer(1, 2 * mm))
        preview = Image(str(overlay_snapshot))
        preview._restrictSize(175 * mm, 120 * mm)
        story.append(preview)

    # Kullanıcı rapor notu
    if clinical_note.strip():
        story.extend(_section_title("Rapor Notu", heading_style))
        story.append(Paragraph(
            escape(clinical_note.strip()).replace("\n", "<br/>"),
            note_style,
        ))

    # İmza ve sınırlar
    story.append(Spacer(1, 7 * mm))
    signature_data = [
        ["Hazırlayan", prepared_by or "Yerel kullanıcı"],
        ["Rol", prepared_role or "—"],
        ["Onaylayan hekim / imza", "\n\n____________________________________________"],
    ]
    story.append(_table(
        [["Alan", "Bilgi"], *signature_data],
        [50 * mm, 133 * mm],
        font, table_body_style, table_header_style,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Önemli not: Cobb ölçümleri uygulamadaki kullanıcı işaretlemelerine dayanır. "
        "Otomatik özetler ve grafikler kayıtlı verileri sunar; klinik karar, tanı veya tedavi önerisi yerine geçmez. "
        "Sonuçlar yetkili uzman tarafından değerlendirilmelidir.",
        note_style,
    ))

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Scoliosis Follow-Up Profesyonel Hasta Takip Raporu v2",
        author=prepared_by or "Scoliosis Follow-Up",
        subject=f"Hasta takip raporu - {patient_id}",
    )
    decorator = _page_decorator(font, patient_id)
    document.build(story, onFirstPage=decorator, onLaterPages=decorator)
    return output
