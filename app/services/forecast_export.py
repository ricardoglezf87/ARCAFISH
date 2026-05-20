from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=pdf_filename_base(forecast, selected_day, species_scope, species_id),
        author="ARCAFISH",
    )

    styles = build_styles()
    story = build_story(forecast, rows, selected_day, species_scope, interval_hours, species_exports, styles)
    document.build(story)
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
        Paragraph("ARCAFISH - Exportacion de pronostico", styles["title"]),
        Paragraph(escape_text(spot.get("name", "Punto sin nombre")), styles["heading"]),
        Paragraph(
            f"{spot.get('latitude', 0):.4f}, {spot.get('longitude', 0):.4f} - "
            f"{describe_period(selected_day)} - Intervalo cada {interval_hours} h",
            styles["meta"],
        ),
        Paragraph(
            f"Emitido: {format_generated_at(generated_at)} - "
            f"Perfiles exportados: {describe_species_scope(species_scope, species_exports)}",
            styles["meta"],
        ),
        Spacer(1, 6),
        build_summary_table(summary, species_exports, styles),
        Spacer(1, 10),
        Paragraph("Condiciones del tramo exportado", styles["section"]),
        build_conditions_table(rows, styles),
    ]

    if species_scope == "all":
        story.extend(
            [
                Spacer(1, 10),
                Paragraph("Resumen por perfiles", styles["section"]),
                build_species_summary_table(species_exports, styles),
            ]
        )
        for index, export in enumerate(species_exports):
            story.extend(
                [
                    PageBreak() if index > 0 else Spacer(1, 10),
                    Paragraph(f"Perfil: {escape_text(export.name)}", styles["section"]),
                    Paragraph(
                        f"Score 24 h: {export.summary.get('score', 's/d')} - "
                        f"{escape_text(export.summary.get('category', 's/d'))}",
                        styles["meta"],
                    ),
                    build_species_rows_table(rows, export, styles),
                ]
            )
    else:
        story.extend(
            [
                Spacer(1, 10),
                Paragraph(f"Score exportado: {escape_text(species_exports[0].name)}", styles["section"]),
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
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#173247"),
            spaceAfter=4,
        ),
        "heading": ParagraphStyle(
            "ExportHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#16232b"),
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "ExportSection",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#173247"),
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "ExportMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#52636c"),
            spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "ExportCell",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=9,
            textColor=colors.HexColor("#16232b"),
        ),
        "cell_bold": ParagraphStyle(
            "ExportCellBold",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=colors.HexColor("#16232b"),
        ),
    }


def build_summary_table(summary: dict, species_exports: list[ExportSpecies], styles: dict[str, ParagraphStyle]) -> Table:
    target = species_exports[0].summary if len(species_exports) == 1 else summary
    data = [
        [
            cell("Score base 24 h", styles["cell_bold"]),
            cell(str(target.get("score", "s/d")), styles["cell"]),
            cell("Categoria", styles["cell_bold"]),
            cell(escape_text(target.get("category", "s/d")), styles["cell"]),
            cell("Mejor ventana", styles["cell_bold"]),
            cell(format_hour(target.get("best_datetime")), styles["cell"]),
        ],
        [
            cell("Ahora", styles["cell_bold"]),
            cell(str(target.get("current_score", summary.get("current_score", "s/d"))), styles["cell"]),
            cell("Alerta", styles["cell_bold"]),
            cell(escape_text(first_alert(target.get("safety_alerts") or summary.get("safety_alerts") or [])), styles["cell"]),
            cell("Recomendacion", styles["cell_bold"]),
            cell(escape_text(target.get("recommendation", summary.get("recommendation", "s/d"))), styles["cell"]),
        ],
    ]
    table = Table(data, colWidths=[26 * mm, 16 * mm, 22 * mm, 24 * mm, 28 * mm, 130 * mm])
    table.setStyle(base_table_style(header=False))
    return table


def build_conditions_table(rows: list[dict], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        cell("Hora", styles["cell_bold"]),
        cell("Cielo", styles["cell_bold"]),
        cell("Viento", styles["cell_bold"]),
        cell("Lluvia", styles["cell_bold"]),
        cell("Mar", styles["cell_bold"]),
        cell("Marea", styles["cell_bold"]),
        cell("Lectura", styles["cell_bold"]),
    ]]
    for row in rows:
        data.append(
            [
                cell(format_hour(row.get("datetime")), styles["cell"]),
                cell(escape_text(row.get("weather_description", "s/d")), styles["cell"]),
                cell(f"{fmt(row.get('wind_speed_ms'), 'm/s')} / racha {fmt(row.get('wind_gust_ms'), 'm/s')}", styles["cell"]),
                cell(f"{fmt(row.get('precipitation_mm'), 'mm')} / {fmt(row.get('precipitation_probability'), '%')}", styles["cell"]),
                cell(f"{fmt(row.get('wave_height_m'), 'm')} / {fmt(row.get('wave_period_s'), 's')}", styles["cell"]),
                cell(f"{escape_text(row.get('tide_state', 's/d'))} / {fmt(row.get('tide_height_m'), 'm')}", styles["cell"]),
                cell(escape_text(human_row_reading(row)), styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[24 * mm, 34 * mm, 32 * mm, 25 * mm, 25 * mm, 28 * mm, 90 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return table


def build_species_summary_table(species_exports: list[ExportSpecies], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        cell("Perfil", styles["cell_bold"]),
        cell("Score", styles["cell_bold"]),
        cell("Categoria", styles["cell_bold"]),
        cell("Mejor ventana", styles["cell_bold"]),
        cell("Mes", styles["cell_bold"]),
    ]]
    for export in species_exports:
        factor = export.summary.get("seasonality_factor")
        month_text = "100%" if export.species_id == "general" else f"{int(round((factor or 0) * 100))}%"
        data.append(
            [
                cell(escape_text(export.name), styles["cell"]),
                cell(str(export.summary.get("score", "s/d")), styles["cell"]),
                cell(escape_text(export.summary.get("category", "s/d")), styles["cell"]),
                cell(format_hour(export.summary.get("best_datetime")), styles["cell"]),
                cell(month_text, styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[65 * mm, 18 * mm, 28 * mm, 34 * mm, 18 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return table


def build_species_rows_table(rows: list[dict], export: ExportSpecies, styles: dict[str, ParagraphStyle]) -> Table:
    data = [[
        cell("Hora", styles["cell_bold"]),
        cell("Score", styles["cell_bold"]),
        cell("Categoria", styles["cell_bold"]),
        cell("Lectura", styles["cell_bold"]),
    ]]
    for row in rows:
        score_data = row_score(row, export.species_id)
        data.append(
            [
                cell(format_hour(row.get("datetime")), styles["cell"]),
                cell(str(score_data.get("score", "s/d")), styles["cell"]),
                cell(escape_text(score_data.get("category", "s/d")), styles["cell"]),
                cell(escape_text(score_data.get("explanation") or human_row_reading(row)), styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[28 * mm, 18 * mm, 24 * mm, 180 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return table


def base_table_style(header: bool = True) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e0dd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0ee")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    return TableStyle(commands)


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


def cell(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape_text(text), style)


def escape_text(value: str | None) -> str:
    text = str(value or "")
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
