from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "output" / "pdf"
FONT_REGULAR_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]
FONT_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

NAVY = colors.HexColor("#18263D")
BLUE = colors.HexColor("#3468C0")
BLUE_LIGHT = colors.HexColor("#EAF1FC")
CORAL = colors.HexColor("#F26B5E")
GREEN = colors.HexColor("#2E8B72")
RED = colors.HexColor("#C84D4D")
INK = colors.HexColor("#233044")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#DDE4EE")
SURFACE = colors.HexColor("#F6F8FB")


def _first_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise RuntimeError("Не найден шрифт с поддержкой кириллицы для PDF")


def register_fonts() -> None:
    regular = Path(os.environ["TAMBUR_PDF_FONT_REGULAR"]) if os.environ.get("TAMBUR_PDF_FONT_REGULAR") else _first_existing(FONT_REGULAR_CANDIDATES)
    bold = Path(os.environ["TAMBUR_PDF_FONT_BOLD"]) if os.environ.get("TAMBUR_PDF_FONT_BOLD") else _first_existing(FONT_BOLD_CANDIDATES)
    if "TamburSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TamburSans", str(regular)))
        pdfmetrics.registerFont(TTFont("TamburSans-Bold", str(bold)))


def _int(value: Any) -> str:
    return f"{int(round(float(value or 0))):,}".replace(",", " ")


def _number(value: Any, digits: int = 1) -> str:
    return f"{float(value or 0):.{digits}f}".replace(".", ",")


def _delta(value: Any) -> str:
    if value is None:
        return "нет данных"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.1f}%".replace(".", ",")


def _safe(value: Any) -> str:
    return html.escape(str(value or ""))


def _decision_color(decision: str) -> colors.Color:
    normalized = decision.lower()
    if "оставить" in normalized:
        return GREEN
    if "удален" in normalized or "удалить" in normalized:
        return CORAL
    if "измен" in normalized:
        return BLUE
    return MUTED


class ComparisonBars(Flowable):
    def __init__(self, rows: list[dict[str, Any]], width: float = 170 * mm):
        super().__init__()
        self.rows = rows[:4]
        self.width = width
        self.height = 10 * mm + len(self.rows) * 11 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        label_width = 58 * mm
        chart_width = self.width - label_width - 18 * mm
        max_value = max(
            [float(row.get("users") or 0) for row in self.rows]
            + [float(row.get("previous_users") or 0) for row in self.rows]
            + [1.0]
        )
        canvas.setFont("TamburSans", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(label_width, self.height - 5 * mm, "предыдущая")
        canvas.setFillColor(BLUE)
        canvas.drawString(label_width + 26 * mm, self.height - 5 * mm, "текущая")
        canvas.setFillColor(colors.HexColor("#B9C4D4"))
        canvas.rect(label_width - 5 * mm, self.height - 4.6 * mm, 3 * mm, 1.8 * mm, fill=1, stroke=0)
        canvas.setFillColor(BLUE)
        canvas.rect(label_width + 21 * mm, self.height - 4.6 * mm, 3 * mm, 1.8 * mm, fill=1, stroke=0)
        for index, row in enumerate(self.rows):
            y = self.height - 13 * mm - index * 11 * mm
            label = str(row.get("name") or "не определено")
            if len(label) > 36:
                label = f"{label[:33]}..."
            canvas.setFillColor(INK)
            canvas.setFont("TamburSans", 8)
            canvas.drawString(0, y + 3.3 * mm, label)
            previous = float(row.get("previous_users") or 0)
            current = float(row.get("users") or 0)
            previous_width = chart_width * previous / max_value
            current_width = chart_width * current / max_value
            canvas.setFillColor(colors.HexColor("#B9C4D4"))
            canvas.roundRect(label_width, y + 4.2 * mm, previous_width, 2.8 * mm, 1.2 * mm, fill=1, stroke=0)
            canvas.setFillColor(BLUE)
            canvas.roundRect(label_width, y, current_width, 2.8 * mm, 1.2 * mm, fill=1, stroke=0)
            canvas.setFont("TamburSans", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(self.width, y + 4.7 * mm, _int(previous))
            canvas.setFillColor(INK)
            canvas.drawRightString(self.width, y + 0.5 * mm, _int(current))
        canvas.restoreState()


def _merge_segments(segment: dict[str, Any]) -> list[dict[str, Any]]:
    current = {str(item.get("name")): item for item in segment.get("current") or []}
    previous = {str(item.get("name")): item for item in segment.get("previous") or []}
    rows = []
    for name in set(current) | set(previous):
        current_row = current.get(name, {})
        previous_row = previous.get(name, {})
        rows.append(
            {
                "name": name,
                "users": float(current_row.get("users") or 0),
                "previous_users": float(previous_row.get("users") or 0),
            }
        )
    return sorted(rows, key=lambda row: max(row["users"], row["previous_users"]), reverse=True)


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=sample["Title"], fontName="TamburSans-Bold", fontSize=24, leading=29, textColor=NAVY, alignment=TA_LEFT, spaceAfter=4 * mm),
        "subtitle": ParagraphStyle("Subtitle", parent=sample["BodyText"], fontName="TamburSans", fontSize=10, leading=15, textColor=MUTED, spaceAfter=7 * mm),
        "h1": ParagraphStyle("H1", parent=sample["Heading1"], fontName="TamburSans-Bold", fontSize=15, leading=19, textColor=NAVY, spaceBefore=4 * mm, spaceAfter=3 * mm),
        "h2": ParagraphStyle("H2", parent=sample["Heading2"], fontName="TamburSans-Bold", fontSize=11, leading=14, textColor=BLUE, spaceBefore=3 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("Body", parent=sample["BodyText"], fontName="TamburSans", fontSize=9.2, leading=14, textColor=INK, spaceAfter=2 * mm),
        "small": ParagraphStyle("Small", parent=sample["BodyText"], fontName="TamburSans", fontSize=7.5, leading=11, textColor=MUTED),
        "kpi_value": ParagraphStyle("KpiValue", parent=sample["BodyText"], fontName="TamburSans-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=TA_CENTER),
        "kpi_label": ParagraphStyle("KpiLabel", parent=sample["BodyText"], fontName="TamburSans", fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_CENTER),
        "kpi_delta": ParagraphStyle("KpiDelta", parent=sample["BodyText"], fontName="TamburSans-Bold", fontSize=8, leading=10, alignment=TA_CENTER),
    }


def _kpi_card(label: str, value: str, delta: Any, styles: dict[str, ParagraphStyle], positive_is_good: bool = True) -> Table:
    delta_value = float(delta) if delta is not None else None
    good = delta_value is not None and ((delta_value >= 0) if positive_is_good else (delta_value <= 0))
    delta_color = GREEN if good else RED if delta_value is not None else MUTED
    delta_style = ParagraphStyle("KpiDeltaLocal", parent=styles["kpi_delta"], textColor=delta_color)
    table = Table(
        [
            [Paragraph(_safe(value), styles["kpi_value"])],
            [Paragraph(_safe(label), styles["kpi_label"])],
            [Paragraph(f"WoW {_safe(_delta(delta))}", delta_style)],
        ],
        colWidths=[40 * mm],
        rowHeights=[9 * mm, 7 * mm, 6 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return table


def _page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 7 * mm, width, 7 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(LINE)
    canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
    canvas.setFont("TamburSans", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 9 * mm, "TAMBUR / PRODUCT ANALYTICS")
    canvas.drawRightString(width - 20 * mm, 9 * mm, f"{doc.page}")
    canvas.restoreState()


def build_pdf(report: dict[str, Any], analysis: dict[str, Any], output: str | Path | None = None) -> Path:
    register_fonts()
    period = report["period"]
    output_path = Path(output) if output else OUTPUT_DIR / f"tambur-weekly-{period['end']}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Tambur weekly product report {period['end']}",
        author="Tambur Product Analyst",
    )
    story: list[Any] = []

    story.append(Paragraph("Еженедельный продуктовый отчёт", styles["title"]))
    story.append(Paragraph(f"Тамбур / {_safe(period['start'])} - {_safe(period['end'])} / только человеческий трафик", styles["subtitle"]))
    summary = report["summary"]
    changes = report["week_over_week_percent"]
    cards = [
        _kpi_card("Пользователи", _int(summary["users"]), changes.get("users"), styles),
        _kpi_card("Визиты", _int(summary["visits"]), changes.get("visits"), styles),
        _kpi_card("Отказы", f"{_number(summary['bounce_rate'])}%", changes.get("bounce_rate"), styles, positive_is_good=False),
        _kpi_card("Среднее время", f"{_number(summary['avg_visit_duration_seconds'])} сек.", changes.get("avg_visit_duration_seconds"), styles),
    ]
    kpi_table = Table([cards], colWidths=[42.5 * mm] * 4, hAlign="LEFT")
    kpi_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
    story.append(kpi_table)
    story.append(Spacer(1, 7 * mm))

    nsm = report["north_star"]
    nsm_status = "точная" if nsm.get("status") == "exact" else "proxy"
    nsm_value = nsm.get("users") if nsm.get("status") == "exact" else nsm.get("proxy_non_bounce_users")
    nsm_box = Table(
        [[Paragraph("NORTH STAR", styles["kpi_label"]), Paragraph(f"Weekly Valuable Users: {_int(nsm_value)} ({nsm_status})", styles["h2"])], ["", Paragraph(_safe(nsm.get("note")), styles["small"]) ]],
        colWidths=[32 * mm, 135 * mm],
    )
    nsm_box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE_LIGHT), ("BOX", (0, 0), (-1, -1), 0.7, BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("SPAN", (0, 0), (0, 1)), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm)]))
    story.append(nsm_box)
    story.append(Paragraph("Главный вывод", styles["h1"]))
    story.append(Paragraph(_safe(analysis.get("executive_summary") or "Недостаточно данных для вывода."), styles["body"]))
    for observation in analysis.get("observations") or []:
        story.append(Paragraph(f"• {_safe(observation)}", styles["body"]))

    quality = report.get("traffic_quality", {}).get("current", {})
    all_visits = float(quality.get("all_visits") or 0)
    robot_visits = float(quality.get("robot_visits") or 0)
    human_visits = max(all_visits - robot_visits, 0)
    story.append(Paragraph("Качество данных", styles["h1"]))
    quality_table = Table(
        [
            [Paragraph("Все визиты", styles["small"]), Paragraph("Роботы", styles["small"]), Paragraph("Люди", styles["small"])],
            [Paragraph(_int(all_visits), styles["kpi_value"]), Paragraph(f"{_int(robot_visits)} / {_number(quality.get('robot_visits_percent'))}%", styles["kpi_value"]), Paragraph(_int(human_visits), styles["kpi_value"])],
        ],
        colWidths=[56 * mm] * 3,
    )
    quality_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SURFACE), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm)]))
    story.append(quality_table)

    story.append(PageBreak())
    story.append(Paragraph("Что изменило результат", styles["title"]))
    story.append(Paragraph("Сравнение уникальных пользователей с предыдущей завершённой неделей", styles["subtitle"]))
    story.append(Paragraph("Источники трафика", styles["h1"]))
    story.append(ComparisonBars(_merge_segments(report["segments"]["traffic_sources"])))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Устройства", styles["h1"]))
    story.append(ComparisonBars(_merge_segments(report["segments"]["devices"])))

    landings = report["segments"]["landing_pages"].get("current") or []
    story.append(Paragraph("Крупнейшие посадочные страницы", styles["h1"]))
    landing_rows = [[Paragraph("Страница", styles["small"]), Paragraph("Польз.", styles["small"]), Paragraph("Отказы", styles["small"])]]
    for item in landings[:6]:
        name = str(item.get("name") or "")
        if len(name) > 72:
            name = f"{name[:69]}..."
        landing_rows.append([Paragraph(_safe(name), styles["small"]), Paragraph(_int(item.get("users")), styles["small"]), Paragraph(f"{_number(item.get('bounce_rate'))}%", styles["small"])])
    landing_table = Table(landing_rows, colWidths=[130 * mm, 18 * mm, 22 * mm], repeatRows=1)
    landing_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm)]))
    story.append(landing_table)

    story.append(PageBreak())
    story.append(Paragraph("Внутренняя продуктовая активность", styles["title"]))
    story.append(Paragraph("Серверные действия авторизованных пользователей: регистрации, публикации, комментарии, реакции, прочтения и подписки.", styles["subtitle"]))
    internal = report.get("internal_product") or {}
    if internal.get("status") == "fresh":
        internal_summary = internal.get("summary") or {}
        internal_changes = internal.get("week_over_week_percent") or {}
        internal_nsm = internal.get("north_star") or {}
        internal_cards = [
            _kpi_card("Auth value users", _int(internal_nsm.get("users")), internal_changes.get("value_users_authenticated"), styles),
            _kpi_card("Регистрации", _int(internal_summary.get("registered_users")), internal_changes.get("registered_users"), styles),
            _kpi_card("Комментарии", _int(internal_summary.get("comments")), internal_changes.get("comments"), styles),
            _kpi_card("Посты с сайта", _int(internal_summary.get("site_posts")), internal_changes.get("site_posts"), styles),
        ]
        internal_kpi_table = Table([internal_cards], colWidths=[42.5 * mm] * 4, hAlign="LEFT")
        internal_kpi_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
        story.append(internal_kpi_table)
        story.append(Spacer(1, 7 * mm))
        activation = internal_summary.get("same_week_activation_rate")
        activation_text = _number(activation) + "%" if activation is not None else "нет регистраций"
        story.append(Paragraph("Активация новых участников", styles["h1"]))
        story.append(Paragraph(f"В ту же неделю ценностное серверное действие совершили {_int(internal_summary.get('registered_users_activated_same_week'))} новых пользователей; конверсия регистрации в активацию — {activation_text}.", styles["body"]))
        activity_rows = [[Paragraph("Действие", styles["small"]), Paragraph("Текущая", styles["small"]), Paragraph("Прошлая", styles["small"]), Paragraph("WoW", styles["small"])]]
        previous_internal = internal.get("previous_summary") or {}
        for label, key in [
            ("Лайки", "positive_likes"),
            ("Голосования", "votes"),
            ("Отметки прочтения", "reads_marked"),
            ("Избранное", "favorites"),
            ("Подписки", "subscriptions_gained"),
            ("Отписки", "subscriptions_lost"),
            ("Реальные просмотры постов", "real_post_views"),
        ]:
            activity_rows.append([
                Paragraph(label, styles["small"]),
                Paragraph(_int(internal_summary.get(key)), styles["small"]),
                Paragraph(_int(previous_internal.get(key)), styles["small"]),
                Paragraph(_delta(internal_changes.get(key)), styles["small"]),
            ])
        activity_table = Table(activity_rows, colWidths=[88 * mm, 26 * mm, 26 * mm, 26 * mm], repeatRows=1)
        activity_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm)]))
        story.append(activity_table)
        story.append(Paragraph("Как читать North Star", styles["h1"]))
        story.append(Paragraph(_safe(internal_nsm.get("definition")), styles["body"]))
        story.append(Paragraph(_safe(internal_nsm.get("caveat")), styles["small"]))
    else:
        latest_raw = str(internal.get("latest_activity_at") or "не определена")
        latest = latest_raw.split("T", 1)[0]
        unavailable = internal.get("status") == "unavailable"
        stale_box = Table(
            [[
                Paragraph(
                    "ИСТОЧНИК НЕДОСТУПЕН" if unavailable else "ДАННЫЕ НЕСВЕЖИЕ",
                    styles["kpi_delta"],
                ),
                Paragraph(
                    "Production backend не ответил по SSH"
                    if unavailable
                    else f"Последняя активность production-БД: {_safe(latest)}",
                    styles["body"],
                ),
            ]],
            colWidths=[45 * mm, 121 * mm],
        )
        stale_box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF1EF")), ("BOX", (0, 0), (-1, -1), 0.7, CORAL), ("TEXTCOLOR", (0, 0), (0, 0), CORAL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm)]))
        story.append(stale_box)
        story.append(Paragraph("Нули не интерпретировались", styles["h1"]))
        story.append(Paragraph(
            "Серверные продуктовые события берутся только из production backend через SSH. "
            "Если SSH недоступен или production-команда вернула несвежие данные, нули не интерпретируются.",
            styles["body"],
        ))
        story.append(Paragraph("После подключения этот раздел покажет Authenticated Weekly Value Users, активацию регистраций, публикации, комментарии, лайки, голосования, отметки прочтения, избранное и подписки/отписки.", styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("Ревизия существующих фич", styles["title"]))
    story.append(Paragraph("Решения по выпущенным возможностям. До/после показывает связь во времени, но не доказывает причинность без контрольной группы.", styles["subtitle"]))
    existing_decisions = analysis.get("existing_feature_decisions") or []
    for index, item in enumerate(existing_decisions, 1):
        if index == 3:
            story.append(PageBreak())
            story.append(Paragraph("Ревизия существующих фич — продолжение", styles["h1"]))
            story.append(Spacer(1, 2 * mm))
        decision = str(item.get("decision") or "недостаточно данных")
        badge_style = ParagraphStyle(
            f"DecisionBadge{index}",
            parent=styles["small"],
            fontName="TamburSans-Bold",
            textColor=colors.white,
            alignment=TA_CENTER,
        )
        task_title = _safe(item.get("task_title"))
        task_url = _safe(item.get("task_url"))
        task_markup = (
            f'<a href="{task_url}" color="#3468C0">Задача: {task_title}</a>'
            if task_url and task_title
            else "Отдельная задача не требуется"
        )
        card = Table(
            [
                [
                    Paragraph(f"{index}. {_safe(item.get('feature'))}", styles["h1"]),
                    Paragraph(_safe(decision).upper(), badge_style),
                ],
                [
                    Paragraph(
                        f"Релиз: {_safe(item.get('release_date'))} · pre: {_safe(item.get('pre_period'))} · post: {_safe(item.get('post_period'))}",
                        styles["small"],
                    ),
                    "",
                ],
                [Paragraph(_safe(item.get("metric_changes")), styles["body"]), ""],
                [Paragraph(_safe(item.get("rationale")), styles["body"]), ""],
                [
                    Paragraph(task_markup, styles["small"]),
                    Paragraph(f"Confidence: {_safe(item.get('confidence'))}", styles["small"]),
                ],
            ],
            colWidths=[125 * mm, 41 * mm],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BACKGROUND", (1, 0), (1, 0), _decision_color(decision)),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("SPAN", (0, 1), (1, 1)),
                    ("SPAN", (0, 2), (1, 2)),
                    ("SPAN", (0, 3), (1, 3)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ]
            )
        )
        story.append(KeepTogether(card))
        story.append(Spacer(1, 3 * mm))

    removal_note = analysis.get("removal_note")
    if removal_note:
        story.append(Paragraph("Про удаление", styles["h1"]))
        story.append(Paragraph(_safe(removal_note), styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("Продуктовые гипотезы", styles["title"]))
    story.append(Paragraph("Только изменения пользовательского опыта и поведения; задачи аналитики вынесены отдельно.", styles["subtitle"]))
    hypotheses = analysis.get("product_hypotheses") or analysis.get("new_feature_decisions") or analysis.get("hypotheses") or []
    for index, item in enumerate(hypotheses, 1):
        title = _safe(item.get("title") or f"Гипотеза {index}")
        url = _safe(item.get("url"))
        title_markup = f'<a href="{url}" color="#3468C0">{title}</a>' if url else title
        product_details = []
        if item.get("audience"):
            product_details.append(f"Аудитория: {_safe(item.get('audience'))}")
        if item.get("product_change"):
            product_details.append(f"Изменение: {_safe(item.get('product_change'))}")
        if item.get("target_behavior"):
            product_details.append(f"Поведение: {_safe(item.get('target_behavior'))}")
        if item.get("success_metric"):
            product_details.append(f"Успех: {_safe(item.get('success_metric'))}")
        card_rows = [[Paragraph(f"{index}. {title_markup}", styles["h1"])]]
        if product_details:
            card_rows.append([Paragraph("<br/>".join(product_details), styles["small"])])
        card_rows.extend([[Paragraph(_safe(item.get("rationale")), styles["body"])], [Paragraph(f"Приоритет: <b>{_safe(item.get('priority') or 'не указан')}</b> · Уверенность: {_safe(item.get('confidence') or 'не указана')}", styles["small"])]])
        card = Table(
            card_rows,
            colWidths=[166 * mm],
        )
        card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SURFACE), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, 0), 1 * mm), ("BOTTOMPADDING", (0, -1), (-1, -1), 3 * mm)]))
        story.append(KeepTogether(card))
        story.append(Spacer(1, 3 * mm))

    measurement_tasks = analysis.get("measurement_tasks") or []
    if measurement_tasks:
        story.append(Paragraph("Задачи измерения — не продуктовые гипотезы", styles["h1"]))
        for item in measurement_tasks:
            title = _safe(item.get("title"))
            url = _safe(item.get("url"))
            title_markup = f'<a href="{url}" color="#3468C0">{title}</a>' if url else title
            story.append(Paragraph(f"• {title_markup}: {_safe(item.get('rationale'))}", styles["body"]))

    related = analysis.get("existing_related") or []
    if related:
        story.append(Paragraph("Не дублировали", styles["h1"]))
        for item in related:
            title = _safe(item.get("title"))
            url = _safe(item.get("url"))
            title_markup = f'<a href="{url}" color="#3468C0">{title}</a>' if url else title
            story.append(Paragraph(f"• {title_markup}: {_safe(item.get('reason'))}", styles["body"]))

    story.append(Paragraph("Следующие шаги", styles["h1"]))
    for step in analysis.get("next_steps") or []:
        story.append(Paragraph(f"• {_safe(step)}", styles["body"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Методика", styles["h1"]))
    story.append(Paragraph("Источники: Яндекс Метрика (только люди) и production backend Тамбура через SSH. Сравнения до/после наблюдательные; Git-коммиты — кандидаты на даты релизов.", styles["small"]))
    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return output_path


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
