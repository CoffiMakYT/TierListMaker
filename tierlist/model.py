"""Модель данных проекта Tier List Maker.

Проект полностью описывается структурами из этого модуля и умеет
сериализоваться в словарь (JSON). Сами байты изображений хранятся
отдельно — в ImageStore, а в проект попадают только метаданные.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field

# Соотношение сторон карточки (ширина / высота).
ASPECTS: dict[str, float] = {"3:4": 3 / 4, "1:1": 1.0, "4:3": 4 / 3}
ASPECT_TITLES = {"3:4": "Карточка", "1:1": "Квадрат", "4:3": "Альбом"}
FIT_TITLES = {"cover": "Заполнить", "contain": "Вписать"}
FIT_KEYS = ("cover", "contain")

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Стартовый набор уровней: красный, оранжевый, жёлтый, зелёный, голубой.
DEFAULT_TIER_COLORS = ["#d9534f", "#e08a3c", "#dfc341", "#57a54f", "#3f8fd9"]
# Палитра для новых уровней (по кругу).
NEW_TIER_COLORS = ["#8a63d2", "#c9508f", "#3fa4a8", "#8c9b3f", "#b0633a", "#5f7fc9", "#c9a15f"]

DEFAULT_BACKGROUND = "#141419"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Item:
    """Изображение проекта. Байты лежат в ImageStore по тому же id."""

    id: str
    name: str
    ext: str = ".png"
    caption: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "ext": self.ext, "caption": self.caption}

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            id=str(data.get("id") or new_id()),
            name=str(data.get("name") or "image"),
            ext=_norm_ext(data.get("ext")),
            caption=str(data.get("caption") or ""),
        )


@dataclass
class Tier:
    """Строка рейтинга."""

    id: str
    label: str
    color: str
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "color": self.color, "items": list(self.items)}

    @classmethod
    def from_dict(cls, data: dict) -> "Tier":
        return cls(
            id=str(data.get("id") or new_id()),
            label=str(data.get("label") or ""),
            color=str(data.get("color") or DEFAULT_TIER_COLORS[0]),
            items=[str(i) for i in data.get("items") or []],
        )


def _norm_ext(ext) -> str:
    ext = str(ext or ".png").lower()
    if not ext.startswith("."):
        ext = "." + ext
    return ext if ext in SUPPORTED_EXTS else ".png"


@dataclass
class Project:
    name: str = "Мой тирлист"
    tiers: list[Tier] = field(default_factory=list)
    pool: list[str] = field(default_factory=list)
    items: dict[str, Item] = field(default_factory=dict)
    card_aspect: str = "3:4"
    image_fit: str = "cover"
    background: str = DEFAULT_BACKGROUND
    path: str | None = None
    dirty: bool = False

    # ------------------------------------------------------------------ создание
    @classmethod
    def default(cls, name: str = "Мой тирлист") -> "Project":
        tiers = [
            Tier(id=new_id(), label=label, color=color)
            for label, color in zip("SABCD", DEFAULT_TIER_COLORS)
        ]
        return cls(name=name, tiers=tiers, pool=[], items={})

    # ------------------------------------------------------------------ поиск
    def tier_by_id(self, tier_id: str | None) -> Tier | None:
        if tier_id is None:
            return None
        for tier in self.tiers:
            if tier.id == tier_id:
                return tier
        return None

    def container(self, tier_id: str | None) -> list[str]:
        tier = self.tier_by_id(tier_id)
        return tier.items if tier is not None else self.pool

    def locate(self, item_id: str) -> tuple[str | None, int]:
        """Возвращает (id уровня или None для корзины, позиция). Если нет — (None, -1)."""
        for tier in self.tiers:
            if item_id in tier.items:
                return tier.id, tier.items.index(item_id)
        if item_id in self.pool:
            return None, self.pool.index(item_id)
        return None, -1

    # ------------------------------------------------------------------ изменение
    def detach(self, item_id: str) -> None:
        for tier in self.tiers:
            if item_id in tier.items:
                tier.items.remove(item_id)
        if item_id in self.pool:
            self.pool.remove(item_id)

    def move(self, item_ids: list[str], tier_id: str | None, index: int | None = None) -> None:
        """Перемещает список изображений в уровень (или корзину) на позицию index.

        Порядок переданных id сохраняется. Индекс трактуется относительно
        состояния *до* перемещения и корректируется с учётом удалённых элементов.
        """
        ids = [i for i in item_ids if i in self.items]
        if not ids:
            return
        target = self.container(tier_id)
        before = list(target)
        if index is None:
            index = len(before)

        # Определяем контейнер-источник перед удалением.
        current_containers = [self.pool] + [tier.items for tier in self.tiers]
        source = next((container for container in current_containers if any(i in container for i in ids)), None)
        moving = set(ids)
        # Индекс drop рассчитан до удаления. Карточки из группы, которые
        # находились левее drop-позиции, сдвигают фактическую позицию влево.
        removed_before = sum(1 for i, item in enumerate(before) if item in moving and i < index) if source is target else 0

        self.detach_all(ids)

        container = self.container(tier_id)
        pos = max(0, min(index - removed_before, len(container)))
        for offset, item_id in enumerate(ids):
            container.insert(min(pos + offset, len(container)), item_id)

    def detach_all(self, item_ids: list[str]) -> None:
        drop = set(item_ids)
        for tier in self.tiers:
            tier.items[:] = [i for i in tier.items if i not in drop]
        self.pool[:] = [i for i in self.pool if i not in drop]

    def remove_item(self, item_id: str) -> None:
        self.detach(item_id)
        self.items.pop(item_id, None)

    def add_tier(self, label: str | None = None, color: str | None = None, index: int | None = None) -> Tier:
        used = {t.label for t in self.tiers}
        if label is None:
            label = next((ch for ch in "SABCDEFGHIJKLMNOPQRSTUVWXYZ" if ch not in used), "")
            if not label:
                label = f"Уровень {len(self.tiers) + 1}"
        if color is None:
            color = NEW_TIER_COLORS[len(self.tiers) % len(NEW_TIER_COLORS)]
        tier = Tier(id=new_id(), label=label, color=color)
        if index is None or index >= len(self.tiers):
            self.tiers.append(tier)
        else:
            self.tiers.insert(max(0, index), tier)
        return tier

    def remove_tier(self, tier_id: str) -> list[str]:
        """Удаляет уровень; его изображения возвращаются в корзину."""
        tier = self.tier_by_id(tier_id)
        if tier is None or len(self.tiers) <= 1:
            return []
        moved = list(tier.items)
        self.tiers.remove(tier)
        for item_id in moved:
            self.pool.append(item_id)
        return moved

    def move_tier(self, tier_id: str, direction: int) -> bool:
        for i, tier in enumerate(self.tiers):
            if tier.id == tier_id:
                j = i + direction
                if 0 <= j < len(self.tiers):
                    self.tiers[i], self.tiers[j] = self.tiers[j], self.tiers[i]
                    return True
        return False

    # ------------------------------------------------------------------ статистика
    def assigned_count(self) -> int:
        return sum(len(t.items) for t in self.tiers)

    def counts(self) -> tuple[int, int, int]:
        return len(self.items), self.assigned_count(), len(self.pool)

    # ------------------------------------------------------------------ сериализация
    def to_dict(self) -> dict:
        return {
            "format": "tierproj",
            "version": 1,
            "name": self.name,
            "card_aspect": self.card_aspect if self.card_aspect in ASPECTS else "3:4",
            "image_fit": self.image_fit if self.image_fit in FIT_KEYS else "cover",
            "background": self.background,
            "tiers": [t.to_dict() for t in self.tiers],
            "pool": list(self.pool),
            "items": [item.to_dict() for item in self.items.values()],
        }

    def from_dict(self, data: dict) -> None:
        self.name = str(data.get("name") or "Мой тирлист")
        aspect = str(data.get("card_aspect") or "3:4")
        self.card_aspect = aspect if aspect in ASPECTS else "3:4"
        fit = str(data.get("image_fit") or "cover")
        self.image_fit = fit if fit in FIT_KEYS else "cover"
        self.background = str(data.get("background") or DEFAULT_BACKGROUND)
        self.tiers = [Tier.from_dict(t) for t in data.get("tiers") or []]
        if not self.tiers:
            self.tiers = Project.default().tiers
        items = [Item.from_dict(i) for i in data.get("items") or []]
        self.items = {item.id: item for item in items}
        valid = set(self.items)
        for tier in self.tiers:
            tier.items = [i for i in tier.items if i in valid]
        self.pool = [i for i in data.get("pool") or [] if i in valid]
        # страховка: ни одно изображение не должно потеряться или дублироваться
        seen: set[str] = set()
        for tier in self.tiers:
            tier.items = [i for i in tier.items if not (i in seen or seen.add(i))]
        self.pool = [i for i in self.pool if not (i in seen or seen.add(i))]
        for item_id in self.items:
            if item_id not in seen:
                self.pool.append(item_id)
        self.dirty = False

    def snapshot(self) -> dict:
        return copy.deepcopy(self.to_dict())

    def restore(self, data: dict) -> None:
        self.from_dict(copy.deepcopy(data))
