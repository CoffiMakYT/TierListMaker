"""Small runtime Russian/English UI translations."""

from PySide6.QtCore import QSettings

_LANG = "ru"

TEXT = {
    "new": ("Новый", "New"), "open": ("Открыть", "Open"), "save": ("Сохранить", "Save"),
    "save_as": ("Сохранить как", "Save As"), "import": ("Импорт изображений", "Import Images"),
    "export": ("Экспорт", "Export"), "theme": ("Тема", "Theme"), "language": ("Язык", "Language"),
    "aspect": ("Форма карточки:", "Card shape:"), "fit": ("Изображение:", "Image fit:"),
    "cover": ("Заполнить", "Cover"), "contain": ("Вписать", "Contain"), "add_tier": ("＋ Уровень", "＋ Tier"),
    "drag_hint": ("Перетаскивайте картинки мышью — внутри уровня и между уровнями", "Drag images between tiers and reorder them"),
    "pool": ("Нераспределённые изображения", "Unranked images"),
    "pool_hint": ("Сюда попадают новые картинки — перетащите их в нужный уровень", "New images appear here — drag them into a tier"),
    "pool_empty": ("Перетащите файлы JPG, PNG или WEBP сюда — или нажмите «Импорт изображений»", "Drop JPG, PNG or WEBP files here — or click Import Images"),
    "status": ("Изображений: {total}   ·   в уровнях: {assigned}   ·   нераспределённых: {free}   ·   всего данных: {size}", "Images: {total}   ·   ranked: {assigned}   ·   unranked: {free}   ·   data: {size}"),
    "workshop": ("Мастерская", "Workshop"), "unsaved": ("Несохранённые изменения", "Unsaved changes"),
    "save_changes": ("Сохранить изменения в текущем проекте?", "Save changes to the current project?"),
    "invalid_link": ("Неверная ссылка", "Invalid link"), "deleted_image": ("Изображение удалено (Ctrl+Z — вернуть)", "Image deleted (Ctrl+Z to restore)"),
    "untitled": ("Без названия", "Untitled"), "project_name": ("Название проекта", "Project name"),
    "row_drop": ("Перетащите изображения в этот уровень", "Drop images into this tier"),
    "badge_tip": ("Левый клик — изменить цвет, правый — название", "Left click: change color, right click: rename"),
    "move_up": ("Переместить уровень выше", "Move tier up"), "move_down": ("Переместить уровень ниже", "Move tier down"),
    "delete_tier": ("Удалить уровень", "Delete tier"), "empty_project": ("В проекте пока нет изображений — добавьте их кнопкой «Импорт изображений».", "No images yet — add some with Import Images."),
    "aspect_card": ("Карточка", "Portrait"), "aspect_square": ("Квадрат", "Square"), "aspect_landscape": ("Альбом", "Landscape"),
    "cover_tip": ("Заполнить: картинка обрезается по краям", "Cover: crop the edges"), "contain_tip": ("Вписать: картинка видна целиком, края — фон", "Contain: show full image with background padding"),
    "export_title": ("Экспорт изображения", "Export image"), "export_settings": ("Настройки экспорта", "Export settings"),
    "format": ("Формат", "Format"), "quality": ("Качество", "Quality"), "resolution": ("Разрешение", "Resolution"),
    "normal": ("Обычное", "Standard"), "high": ("Высокое", "High"), "custom": ("Пользовательское", "Custom"),
    "show_title": ("Показывать заголовок", "Show title"), "title_text": ("Текст заголовка", "Title text"),
    "background_button": ("Фон…", "Background…"), "include_unranked": ("Включать нераспределённые", "Include unranked images"),
    "show_empty": ("Показывать пустые уровни", "Show empty tiers"), "cancel": ("Отмена", "Cancel"),
    "export_button": ("Экспортировать", "Export"), "choose_bg": ("Цвет фона", "Background color"),
    "export_info": ("Итоговый файл: {width} × {height} px, {fmt}", "Output: {width} × {height} px, {fmt}"),
    "preview_none": ("Нет данных", "No preview"), "preview_error": ("Не удалось построить предпросмотр:\n{error}", "Could not render preview:\n{error}"),
    "export_error": ("Ошибка экспорта", "Export error"), "save_export": ("Экспорт изображения", "Export image"),
    "theme_dark": ("Тёмная", "Dark"), "theme_light": ("Светлая", "Light"),
    "reset_action": ("Действие отменено", "Action undone"), "redo_action": ("Действие повторено", "Action redone"),
    "new_project": ("Новый тирлист", "New tier list"), "project_title_prompt": ("Название проекта:", "Project name:"),
    "save_project_title": ("Сохранить проект", "Save project"), "open_project_title": ("Открыть проект", "Open project"),
    "discard_title": ("Несохранённые изменения", "Unsaved changes"), "save_prompt": ("Сохранить изменения в текущем проекте?", "Save changes to the current project?"),
    "new_created": ("Создан новый проект", "New project created"), "one_tier_min": ("Должен остаться хотя бы один уровень.", "At least one tier must remain."),
    "rename_tip": ("Название тирлиста (Enter — применить)", "Tier list title (press Enter to apply)"),
    "card_shape_tip": ("Карточка {key}", "Card shape {key}"), "replace_template": ("Заменить текущий тирлист шаблоном?", "Replace the current tier list with this template?"),
    "import_dialog": ("Импорт изображений", "Import images"), "image_filter": ("Изображения (*.jpg *.jpeg *.png *.webp)", "Images (*.jpg *.jpeg *.png *.webp)"),
    "added_count": ("Добавлено изображений: {count}", "Images added: {count}"), "import_error_title": ("Не удалось добавить", "Could not add images"),
    "import_error_body": ("Эти файлы не добавлены (неподдерживаемый формат или повреждены):\n\n{names}", "These files were not added (unsupported or damaged):\n\n{names}"),
    "tier_name_title": ("Название уровня", "Tier name"), "name_label": ("Название:", "Name:"), "tier_color_title": ("Цвет уровня", "Tier color"),
    "delete_tier_title": ("Удалить уровень?", "Delete tier?"), "tier_delete_confirm": ("Уровень «{label}» содержит изображений: {count}.\nОни вернутся в «Нераспределённые». Продолжить?", "Tier “{label}” contains {count} images.\nThey will return to Unranked. Continue?"),
    "project_filter": ("Проект Tier List (*{ext})", "Tier List project (*{ext})"), "open_error": ("Не удалось открыть проект", "Could not open project"),
    "opened_project": ("Открыт проект: {path}", "Opened project: {path}"), "incomplete_archive": ("Неполный архив", "Incomplete archive"),
    "missing_images": ("В архиве нет данных для изображений:\n\n{names}", "Image data is missing from the archive:\n\n{names}"),
    "save_error": ("Ошибка сохранения", "Save error"), "save_error_body": ("Не удалось сохранить проект:\n{error}", "Could not save project:\n{error}"),
    "saved_path": ("Сохранено: {path}", "Saved: {path}"), "export_empty": ("Экспорт", "Export"),
    "exported_path": ("Экспортировано: {path}", "Exported: {path}"), "saved_status": ("Сохранено: {path}", "Saved: {path}"),
}


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if lang == "en" else "ru"
    QSettings().setValue("ui/language", _LANG)


def language() -> str:
    return _LANG


def load_language() -> str:
    value = str(QSettings().value("ui/language", "ru"))
    set_language(value)
    return _LANG


def tr(token: str, **values) -> str:
    pair = TEXT.get(token)
    text = pair[1 if _LANG == "en" else 0] if pair else token
    return text.format(**values) if values else text
