from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


INK = colors.HexColor("#16232b")
MUTED = colors.HexColor("#52636c")
PANEL = colors.HexColor("#f6f8f7")
LINE = colors.HexColor("#d8e0dd")
SEA = colors.HexColor("#1976b9")
NAVY = colors.HexColor("#173247")
GREEN = colors.HexColor("#1f8a5b")
TEAL = colors.HexColor("#0786a8")
ORANGE = colors.HexColor("#d8891c")
RED = colors.HexColor("#c7372f")
NEUTRAL = colors.HexColor("#62727c")
PALE_SEA = colors.HexColor("#e4f3f6")
PALE_GREEN = colors.HexColor("#e4f5ec")
PALE_ORANGE = colors.HexColor("#fff2d9")
PALE_RED = colors.HexColor("#fde8e6")
PALE_NEUTRAL = colors.HexColor("#eef2f1")


@dataclass(frozen=True)
class ExportSpecies:
    species_id: str
    name: str
    summary: dict


def build_forecast_pdf(
    forecast: dict,
    selected_day: str,
    species_scope: str,
    species_id: str,
    interval_hours: int,
) -> bytes:
    interval_hours = max(1, min(12, int(interval_hours)))
    rows = filter_rows(forecast.get("hourly") or [], selected_day, interval_hours)
    species_exports = resolve_species_exports(forecast, species_scope, species_id)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=pdf_filename_base(forecast, selected_day, species_scope, species_id),
        author="ARCAFISH",
    )

    styles = build_styles()
    story = build_story(forecast, rows, selected_day, species_scope, interval_hours, species_exports, styles)
    document.build(story, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)
    return buffer.getvalue()


def pdf_filename(forecast: dict, selected_day: str, species_scope: str, species_id: str) -> str:
    return pdf_filename_base(forecast, selected_day, species_scope, species_id) + ".pdf"


def filter_rows(rows: list[dict], selected_day: str, interval_hours: int) -> list[dict]:
    filtered = list(rows)
    if selected_day != "all":
        filtered = [row for row in filtered if row_day_key(row.get("datetime")) == selected_day]
    filtered = [row for row in filtered if row_matches_interval(row.get("datetime"), interval_hours)]
    return filtered


def resolve_species_exports(forecast: dict, species_scope: str, species_id: str) -> list[ExportSpecies]:
    summary = forecast.get("summary") or {}
    species_summary = summary.get("species") or {}
    if species_scope == "all":
        exports = [ExportSpecies("general", "General costa", summary)]
        for profile in forecast.get("meta", {}).get("species_profiles", []):
            item = species_summary.get(profile["id"])
            if item:
                exports.append(ExportSpecies(profile["id"], profile["name"], item))
        return exports

    if species_id == "general":
        return [ExportSpecies("general", "General costa", summary)]

    selected = species_summary.get(species_id)
    if not selected:
        return [ExportSpecies("general", "General costa", summary)]
    return [ExportSpecies(species_id, selected.get("name", species_id), selected)]


def build_story(
    forecast: dict,
    rows: list[dict],
    selected_day: str,
    species_scope: str,
    interval_hours: int,
    species_exports: list[ExportSpecies],
    styles: dict[str, ParagraphStyle],
) -> list:
    spot = forecast.get("spot") or {}
    summary = forecast.get("summary") or {}
    generated_at = forecast.get("meta", {}).get("generated_at")

    story: list = [
        build_header_panel(spot, selected_day, interval_hours, generated_at, species_scope, species_exports, styles),
        Spacer(1, 8),
        build_summary_table(summary, species_exports, styles),
        Spacer(1, 8),
    ]
    fishing_context = forecast.get("fishing_context") or forecast.get("meta", {}).get("fishing_context")
    if fishing_context:
        story.extend([build_context_callout(fishing_context, styles), Spacer(1, 8)])
    story.extend(
        [
            section_title("Condiciones del tramo exportado", styles),
            build_conditions_table(rows, styles),
        ]
    )

    if species_scope == "all":
        story.extend(
            [
                Spacer(1, 8),
                section_title("Resumen por perfiles", styles),
                build_species_summary_table(species_exports, styles),
            ]
        )
        for index, export in enumerate(species_exports):
            story.extend(
                [
                    PageBreak() if index > 0 else Spacer(1, 8),
                    section_title(f"Perfil: {export.name}", styles),
                    build_profile_badge(export, styles),
                    build_species_rows_table(rows, export, styles),
                ]
            )
    else:
        story.extend(
            [
                Spacer(1, 8),
                section_title(f"Score exportado: {species_exports[0].name}", styles),
                build_profile_badge(species_exports[0], styles),
                build_species_rows_table(rows, species_exports[0], styles),
            ]
        )

    return story


def build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ExportTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            textColor=colors.white,
            spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "ExportHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=colors.white,
            spaceAfter=2,
        ),
        "brand": ParagraphStyle(
            "ExportBrand",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#bfe5ee"),
            spaceAfter=3,
        ),
        "header_meta": ParagraphStyle(
            "ExportHeaderMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.2,
            textColor=colors.HexColor("#d8eef2"),
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "ExportSection",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "meta": ParagraphStyle(
            "ExportMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=MUTED,
            spaceAfter=2,
        ),
        "metric_label": ParagraphStyle(
            "ExportMetricLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
        ),
        "metric_value": ParagraphStyle(
            "ExportMetricValue",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "ExportTableHeader",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=8.6,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "cell": ParagraphStyle(
            "ExportCell",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=9,
            textColor=INK,
        ),
        "cell_bold": ParagraphStyle(
            "ExportCellBold",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=INK,
        ),
        "cell_inverse": ParagraphStyle(
            "ExportCellInverse",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def draw_page_frame(canvas, document) -> None:  # noqa: ANN001
    width, height = landscape(A4)
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 5 * mm, width, 5 * mm, stroke=0, fill=1)
    canvas.setFillColor(SEA)
    canvas.rect(0, height - 5 * mm, 58 * mm, 5 * mm, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(document.leftMargin, 9 * mm, width - document.rightMargin, 9 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(document.leftMargin, 5.5 * mm, "ARCAFISH")
    canvas.drawRightString(width - document.rightMargin, 5.5 * mm, f"Pagina {canvas.getPageNumber()}")
    canvas.restoreState()


def build_header_panel(
    spot: dict,
    selected_day: str,
    interval_hours: int,
    generated_at: str | None,
    species_scope: str,
    species_exports: list[ExportSpecies],
    styles: dict[str, ParagraphStyle],
) -> Table:
    location = f"{spot.get('latitude', 0):.4f}, {spot.get('longitude', 0):.4f}"
    left = [
        Paragraph("ARCAFISH", styles["brand"]),
        Paragraph("Exportacion de pronostico", styles["title"]),
        Paragraph(escape_text(spot.get("name", "Punto sin nombre")), styles["heading"]),
    ]
    right = [
        Paragraph(
            "<b>Periodo</b><br/>"
            f"{escape_text(describe_period(selected_day))}<br/><br/>"
            "<b>Intervalo</b><br/>"
            f"Cada {interval_hours} h<br/><br/>"
            "<b>Coordenadas</b><br/>"
            f"{escape_text(location)}",
            styles["header_meta"],
        ),
        Paragraph(
            "<br/><b>Emitido</b><br/>"
            f"{escape_text(format_generated_at(generated_at))}<br/>"
            "<b>Perfiles</b><br/>"
            f"{escape_text(describe_species_scope(species_scope, species_exports))}",
            styles["header_meta"],
        ),
    ]
    table = Table([[left, right]], colWidths=[168 * mm, 90 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LINEBEFORE", (1, 0), (1, 0), 1.2, SEA),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def build_context_callout(fishing_context: dict, styles: dict[str, ParagraphStyle]) -> Table:
    text = fishing_context.get("interpretation", "")
    distance = fishing_context.get("casting_distance_m", "s/d")
    zone = fishing_context.get("target_zone_label", "s/d")
    data = [
        [
            Paragraph("Contexto de pesca", styles["cell_bold"]),
            Paragraph(escape_text(text), styles["cell"]),
        ],
        [
            Paragraph("Lance / zona", styles["cell_bold"]),
            Paragraph(f"{escape_text(distance)} m - {escape_text(zone)}", styles["cell"]),
        ],
    ]
    table = Table(data, colWidths=[34 * mm, 224 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_SEA),
                ("BOX", (0, 0), (-1, -1), 0.5, SEA),
                ("LINEBEFORE", (0, 0), (0, -1), 3, SEA),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def section_title(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(escape_text(text), styles["section"])]], colWidths=[258 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LINEBEFORE", (0, 0), (0, 0), 4, SEA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_profile_badge(export: ExportSpecies, styles: dict[str, ParagraphStyle]) -> Table:
    score = export.summary.get("score", "s/d")
    category = export.summary.get("category", "s/d")
    accent, pale = quality_palette(category, score)
    data = [[
        Paragraph(f"Score 24 h: {escape_text(score)}", styles["cell_inverse"]),
        Paragraph(escape_text(category), styles["cell_inverse"]),
        Paragraph(f"Mejor ventana: {escape_text(format_hour(export.summary.get('best_datetime')))}", styles["cell_bold"]),
    ]]
    table = Table(data, colWidths=[32 * mm, 34 * mm, 192 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), accent),
                ("BACKGROUND", (2, 0), (2, 0), pale),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def metric_card(
    label: str,
    value: str,
    styles: dict[str, ParagraphStyle],
    width: float,
    accent: colors.Color = SEA,
    background: colors.Color = PANEL,
) -> Table:
    data = [
        [Paragraph(escape_text(label), styles["metric_label"])],
        [Paragraph(escape_text(value), styles["metric_value"])],
    ]
    table = Table(data, colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("LINEABOVE", (0, 0), (-1, 0), 3, accent),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_summary_table(summary: dict, species_exports: list[ExportSpecies], styles: dict[str, ParagraphStyle]) -> Table:
    target = species_exports[0].summary if len(species_exports) == 1 else summary
    score = target.get("score", "s/d")
    category = target.get("category", "s/d")
    accent, pale = quality_palette(category, score)
    current_score = target.get("current_score", summary.get("current_score", "s/d"))
    data = [
        [
            metric_card("Score 24 h", str(score), styles, 42 * mm, accent, pale),
            metric_card("Categoria", str(category), styles, 52 * mm, accent, pale),
            metric_card("Mejor ventana", format_hour(target.get("best_datetime")), styles, 76 * mm, TEAL, PALE_SEA),
            metric_card("Ahora", str(current_score), styles, 88 * mm, *quality_palette(None, current_score)),
        ],
        [
            Paragraph("Alerta", styles["cell_bold"]),
            Paragraph(escape_text(first_alert(target.get("safety_alerts") or summary.get("safety_alerts") or [])), styles["cell"]),
            Paragraph("Recomendacion", styles["cell_bold"]),
            Paragraph(escape_text(target.get("recommendation", summary.get("recommendation", "s/d"))), styles["cell"]),
        ],
    ]
    table = Table(data, colWidths=[42 * mm, 52 * mm, 76 * mm, 88 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BOX", (0, 1), (-1, 1), 0.4, LINE),
                ("LINEBEFORE", (0, 1), (0, 1), 3, ORANGE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, 0), 0),
                ("RIGHTPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("LEFTPADDING", (0, 1), (-1, 1), 7),
                ("RIGHTPADDING", (0, 1), (-1, 1), 7),
                ("TOPPADDING", (0, 1), (-1, 1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ]
        )
    )
    return table


def build_conditions_table(rows: list[dict], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        header_cell("Hora", styles),
        header_cell("Cielo", styles),
        header_cell("Viento", styles),
        header_cell("Lluvia", styles),
        header_cell("Mar", styles),
        header_cell("Marea", styles),
        header_cell("Lectura", styles),
    ]]
    for row in rows:
        data.append(
            [
                cell(format_hour(row.get("datetime")), styles["cell"]),
                cell(row.get("weather_description", "s/d"), styles["cell"]),
                cell(f"{fmt(row.get('wind_speed_ms'), 'm/s')} / racha {fmt(row.get('wind_gust_ms'), 'm/s')}", styles["cell"]),
                cell(f"{fmt(row.get('precipitation_mm'), 'mm')} / {fmt(row.get('precipitation_probability'), '%')}", styles["cell"]),
                cell(f"{fmt(row.get('wave_height_m'), 'm')} / {fmt(row.get('wave_period_s'), 's')}", styles["cell"]),
                cell(f"{row.get('tide_state', 's/d')} / {fmt(row.get('tide_height_m'), 'm')}", styles["cell"]),
                cell(human_row_reading(row), styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[24 * mm, 34 * mm, 32 * mm, 25 * mm, 25 * mm, 28 * mm, 90 * mm], repeatRows=1)
    table.setStyle(base_table_style(row_count=len(data)))
    return table


def build_species_summary_table(species_exports: list[ExportSpecies], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        header_cell("Perfil", styles),
        header_cell("Score", styles),
        header_cell("Categoria", styles),
        header_cell("Mejor ventana", styles),
        header_cell("Mes", styles),
    ]]
    for export in species_exports:
        factor = export.summary.get("seasonality_factor")
        month_text = "100%" if export.species_id == "general" else f"{int(round((factor or 0) * 100))}%"
        data.append(
            [
                cell(export.name, styles["cell"]),
                cell(str(export.summary.get("score", "s/d")), styles["cell_inverse"]),
                cell(export.summary.get("category", "s/d"), styles["cell_inverse"]),
                cell(format_hour(export.summary.get("best_datetime")), styles["cell"]),
                cell(month_text, styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[65 * mm, 18 * mm, 28 * mm, 34 * mm, 18 * mm], repeatRows=1)
    style = base_table_style(row_count=len(data))
    for row_index, export in enumerate(species_exports, start=1):
        accent, _ = quality_palette(export.summary.get("category"), export.summary.get("score"))
        style.add("BACKGROUND", (1, row_index), (2, row_index), accent)
    table.setStyle(style)
    return table


def build_species_rows_table(rows: list[dict], export: ExportSpecies, styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        header_cell("Hora", styles),
        header_cell("Score", styles),
        header_cell("Categoria", styles),
        header_cell("Lectura", styles),
    ]]
    for row in rows:
        score_data = row_score(row, export.species_id)
        data.append(
            [
                cell(format_hour(row.get("datetime")), styles["cell"]),
                cell(str(score_data.get("score", "s/d")), styles["cell_inverse"]),
                cell(score_data.get("category", "s/d"), styles["cell_inverse"]),
                cell(score_data.get("explanation") or human_row_reading(row), styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[28 * mm, 18 * mm, 24 * mm, 180 * mm], repeatRows=1)
    style = base_table_style(row_count=len(data))
    for row_index, row in enumerate(rows, start=1):
        score_data = row_score(row, export.species_id)
        accent, _ = quality_palette(score_data.get("category"), score_data.get("score"))
        style.add("BACKGROUND", (1, row_index), (2, row_index), accent)
    table.setStyle(style)
    return table


def base_table_style(header: bool = True, row_count: int | None = None) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    first_data_row = 1 if header else 0
    if row_count is None or row_count > first_data_row:
        commands.append(("ROWBACKGROUNDS", (0, first_data_row), (-1, -1), [colors.white, PANEL]))
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, SEA),
            ]
        )
    return TableStyle(commands)


def quality_palette(category: str | None, score: object = None) -> tuple[colors.Color, colors.Color]:
    key = quality_key(category, score)
    return {
        "great": (TEAL, PALE_SEA),
        "good": (GREEN, PALE_GREEN),
        "regular": (ORANGE, PALE_ORANGE),
        "bad": (RED, PALE_RED),
    }.get(key, (NEUTRAL, PALE_NEUTRAL))


def quality_key(category: str | None, score: object = None) -> str:
    normalized = str(category or "").lower()
    if "muy" in normalized:
        return "great"
    if "buena" in normalized:
        return "good"
    if "regular" in normalized:
        return "regular"
    if "mala" in normalized:
        return "bad"

    numeric = numeric_score(score)
    if numeric is None:
        return "neutral"
    if numeric <= 39:
        return "bad"
    if numeric <= 59:
        return "regular"
    if numeric <= 79:
        return "good"
    return "great"


def numeric_score(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_matches_interval(value: str | None, interval_hours: int) -> bool:
    if interval_hours <= 1 or not value:
        return True
    return datetime.fromisoformat(value).hour % interval_hours == 0


def row_day_key(value: str | None) -> str:
    return str(value or "")[:10]


def row_score(row: dict, species_id: str) -> dict:
    if species_id == "general":
        return {
            "score": row.get("fishing_score"),
            "category": row.get("fishing_category"),
            "explanation": row.get("explanation"),
        }
    return (row.get("species_scores") or {}).get(species_id, {})


def human_row_reading(row: dict) -> str:
    parts = [
        row.get("weather_description") or "Tiempo variable",
        f"Viento {fmt(row.get('wind_speed_ms'), 'm/s')}",
        f"Mar {fmt(row.get('wave_height_m'), 'm')}",
        f"Marea {row.get('tide_state', 'sin datos')}",
    ]
    if row.get("precipitation_mm") not in (None, 0):
        parts.append(f"Lluvia {fmt(row.get('precipitation_mm'), 'mm')}")
    return ". ".join(parts)


def describe_period(selected_day: str) -> str:
    if selected_day == "all":
        return "Toda la semana seleccionada"
    return f"Dia {format_day_label(selected_day)}"


def describe_species_scope(species_scope: str, species_exports: list[ExportSpecies]) -> str:
    if species_scope == "all":
        return "general y todas las especies"
    return species_exports[0].name if species_exports else "general"


def format_day_label(value: str) -> str:
    date = datetime.fromisoformat(f"{value}T00:00:00")
    return date.strftime("%d/%m/%Y")


def format_hour(value: str | None) -> str:
    if not value:
        return "s/d"
    return datetime.fromisoformat(value).strftime("%d/%m %H:%M")


def format_generated_at(value: str | None) -> str:
    if not value:
        return "s/d"
    return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")


def fmt(value: float | int | None, unit: str) -> str:
    if value is None:
        return "s/d"
    return f"{value} {unit}"


def first_alert(alerts: list[str]) -> str:
    if not alerts:
        return "Sin alertas principales"
    return alerts[0]


def header_cell(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(escape_text(text), styles["table_header"])


def cell(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape_text(text), style)


def escape_text(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def pdf_filename_base(forecast: dict, selected_day: str, species_scope: str, species_id: str) -> str:
    spot_name = slugify((forecast.get("spot") or {}).get("name", "spot"))
    day_part = "semana" if selected_day == "all" else selected_day
    species_part = "todas-especies" if species_scope == "all" else slugify(species_id or "general")
    return f"arcafish_{spot_name}_{day_part}_{species_part}"


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "export"
