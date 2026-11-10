"""Рендер тирлиста в изображение — с нуля, по данным проекта.

Логическая ширина холста постоянная (BASE_WIDTH), поэтому «1x» и «2x» —
это просто масштаб отрисовки: картинки берутся из оригиналов и остаются
резкими на любом разрешении.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import QApplication

from .imagestore import ImageStore
from .model import ASPECTS, DEFAULT_BACKGROUND, Project, Tier
from .painting import contrast_text, draw_image, rounded_path, shade

BASE_WIDTH = 1400
PAD = 26
LABEL_WIDTH = 200
CARD_HEIGHT = 150
GAP = 12
ROW_GAP = 14
RADIUS = 12
TITLE_HEIGHT = 58
TITLE_GAP = 18
POOL_HEADER_HEIGHT = 34
POOL_HEADER_GAP = 12

MAX_CANVAS_PIXELS = 120_000_000  # предохранитель от «случайных» гигантских экспортов


@dataclass
class ExportOptions:
    include_title: bool = True
    title: str = ""
    background: str = DEFAULT_BACKGROUND
    include_pool: bool = False
    include_empty: bool = False
    scale: float = 1.0


@dataclass
class TierBlock:
    tier: Tier
    lines: list[list[str]]
    height: float
    top: float = 0.0


@dataclass
class Layout:
    width: float
    height: float
    title_height: float
    blocks: list[TierBlock] = field(default_factory=list)
    pool_top: float = 0.0
    pool_height: float = 0.0
    pool_lines: list[list[str]] = field(default_factory=list)


def _wrap(ids: list[str], available: float, card_w: float) -> list[list[str]]:
    if not ids:
        return []
    per_line = max(1, int((available + GAP) // (card_w + GAP)))
    return [ids[i : i + per_line] for i in range(0, len(ids), per_line)]


def _block_height(lines: list[list[str]]) -> float:
    if not lines:
        return CARD_HEIGHT
    return len(lines) * CARD_HEIGHT + (len(lines) - 1) * GAP


def card_width_for(aspect: str) -> float:
    return CARD_HEIGHT * ASPECTS.get(aspect, 0.75)


def build_layout(project: Project, options: ExportOptions) -> Layout:
    content_width = BASE_WIDTH - 2 * PAD
    card_w = card_width_for(project.card_aspect)
    cards_width = content_width - LABEL_WIDTH - GAP

    layout = Layout(width=float(BASE_WIDTH), height=0.0, title_height=0.0)
    y = float(PAD)

    if options.include_title and options.title.strip():
        layout.title_height = TITLE_HEIGHT + TITLE_GAP
        y += layout.title_height

    for tier in project.tiers:
        if not tier.items and not options.include_empty:
            continue
        lines = _wrap(list(tier.items), cards_width, card_w)
        block = TierBlock(tier=tier, lines=lines, height=_block_height(lines), top=y)
        layout.blocks.append(block)
        y += block.height + ROW_GAP

    if options.include_pool and project.pool:
        layout.pool_top = y
        layout.pool_lines = _wrap(list(project.pool), content_width, card_w)
        layout.pool_height = POOL_HEADER_HEIGHT + POOL_HEADER_GAP + _block_height(layout.pool_lines)
        y += layout.pool_height

    layout.height = y + PAD
    return layout


def estimate_size(project: Project, options: ExportOptions) -> tuple[int, int]:
    layout = build_layout(project, options)
    scale = max(options.scale, 0.05)
    return int(round(layout.width * scale)), int(round(layout.height * scale))


def _draw_label(painter: QPainter, tier: Tier, rect: QRectF) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(tier.color))
    painter.drawPath(rounded_path(rect, RADIUS))

    text = tier.label.strip() or "?"
    inner = rect.adjusted(14, 8, -14, -8)
    font = QFont("Segoe UI")
    font.setBold(True)
    size = 30
    font.setPixelSize(size)
    while size > 14 and QFontMetrics(font).horizontalAdvance(text) > inner.width():
        size -= 2
        font.setPixelSize(size)
    painter.setFont(font)
    painter.setPen(contrast_text(tier.color))
    painter.drawText(inner, Qt.AlignCenter | Qt.TextWordWrap, text)


def _draw_cards(
    painter: QPainter,
    lines: list[list[str]],
    left: float,
    top: float,
    store: ImageStore,
    project: Project,
    background: QColor,
) -> None:
    card_w = card_width_for(project.card_aspect)
    holder = background.lighter(118) if background.lightness() < 128 else background.darker(106)
    y = top
    for line in lines:
        x = left
        for item_id in line:
            rect = QRectF(x, y, card_w, CARD_HEIGHT)
            path = rounded_path(rect, RADIUS - 4)
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(rect, holder)
            picture = store.image(item_id)
            if picture is not None:
                draw_image(painter, picture, rect, project.image_fit)
            painter.restore()
            x += card_w + GAP
        y += CARD_HEIGHT + GAP


def render_project(project: Project, store: ImageStore, options: ExportOptions) -> QImage:
    layout = build_layout(project, options)
    scale = max(options.scale, 0.05)
    width = max(1, int(round(layout.width * scale)))
    height = max(1, int(round(layout.height * scale)))
    if width * height > MAX_CANVAS_PIXELS:
        raise ValueError(
            f"Слишком большое изображение: {width}×{height} px. Уменьшите разрешение."
        )

    background = QColor(options.background)
    if not background.isValid():
        background = QColor(DEFAULT_BACKGROUND)

    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(background)
    image.setDevicePixelRatio(1.0)

    painter = QPainter(image)
    painter.setRenderHints(
        QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
    )
    painter.scale(scale, scale)

    content_width = BASE_WIDTH - 2 * PAD

    # Заголовок
    if options.include_title and options.title.strip():
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(38)
        painter.setFont(font)
        painter.setPen(contrast_text(background))
        painter.drawText(
            QRectF(PAD, PAD - 4, content_width, TITLE_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            options.title.strip(),
        )

    # Уровни
    for block in layout.blocks:
        label_rect = QRectF(PAD, block.top, LABEL_WIDTH, block.height)
        _draw_label(painter, block.tier, label_rect)
        _draw_cards(
            painter,
            block.lines,
            PAD + LABEL_WIDTH + GAP,
            block.top,
            store,
            project,
            background,
        )

    # Нераспределённые изображения
    if options.include_pool and project.pool and layout.pool_lines:
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(26)
        painter.setFont(font)
        painter.setPen(contrast_text(background))
        painter.drawText(
            QRectF(PAD, layout.pool_top, content_width, POOL_HEADER_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Нераспределённые изображения",
        )
        _draw_cards(
            painter,
            layout.pool_lines,
            PAD,
            layout.pool_top + POOL_HEADER_HEIGHT + POOL_HEADER_GAP,
            store,
            project,
            background,
        )

    painter.end()
    return image


def default_options(project: Project) -> ExportOptions:
    return ExportOptions(
        include_title=True,
        title=project.name,
        background=project.background or DEFAULT_BACKGROUND,
        include_pool=False,
        include_empty=False,
        scale=2.0,
    )


def save_image(image: QImage, path: str, fmt: str, quality: int = 95) -> bool:
    fmt = fmt.upper()
    if fmt == "JPG":
        # JPEG не поддерживает прозрачность — холст уже залит фоном.
        return image.save(path, "JPG", quality)
    return image.save(path, "PNG")


def screen_dpi_scale() -> float:
    app = QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    return float(screen.devicePixelRatio()) if screen else 1.0