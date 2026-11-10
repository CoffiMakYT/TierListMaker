"""Сохранение и загрузка проекта .tierproj (ZIP: project.json + images/)."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile

from .imagestore import ImageStore
from .model import Project

MANIFEST = "project.json"
IMAGES_DIR = "images"
PROJECT_EXT = ".tierproj"


class ProjectError(Exception):
    """Понятная пользователю ошибка чтения/записи проекта."""


def _image_entry(item_id: str, ext: str) -> str:
    return f"{IMAGES_DIR}/{item_id}{ext}"


def save_project(project: Project, path: str, store: ImageStore) -> None:
    """Пишет проект в ZIP. Байты изображений сохраняются как есть, без пережатия."""
    data = project.to_dict()
    data["images"] = [
        {
            "id": item.id,
            "file": _image_entry(item.id, item.ext),
            "size": len(store.data(item.id) or b""),
        }
        for item in project.items.values()
    ]

    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tierproj-", suffix=".tmp", dir=directory)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                MANIFEST,
                json.dumps(data, ensure_ascii=False, indent=2),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            for item in project.items.values():
                raw = store.data(item.id)
                if raw is None:
                    raise ProjectError(f"Нет данных изображения: {item.name}. Сохранение отменено.")
                # Изображения уже сжаты — храним без повторного сжатия, это быстрее.
                archive.writestr(_image_entry(item.id, item.ext), raw, compress_type=zipfile.ZIP_STORED)
        os.replace(temp_path, path)
    except OSError as error:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise ProjectError(f"Не удалось сохранить проект:\n{error}") from error
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def load_project(path: str) -> tuple[Project, ImageStore]:
    if not os.path.exists(path):
        raise ProjectError("Файл проекта не найден.")
    if not zipfile.is_zipfile(path):
        raise ProjectError("Это не файл проекта .tierproj (внутри должен быть ZIP-архив).")

    try:
        with zipfile.ZipFile(path) as archive:
            try:
                raw_manifest = archive.read(MANIFEST)
            except KeyError as error:
                raise ProjectError("В архиве нет файла project.json.") from error

            try:
                data = json.loads(raw_manifest.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ProjectError("Файл project.json повреждён.") from error

            if not isinstance(data, dict):
                raise ProjectError("Некорректная структура проекта.")

            project = Project()
            project.from_dict(data)
            project.path = path
            project.dirty = False

            store = ImageStore()
            missing = []
            for item in project.items.values():
                entry = _image_entry(item.id, item.ext)
                try:
                    payload = archive.read(entry)
                except KeyError:
                    missing.append(item.name)
                    continue
                if not store.add_bytes(item.id, payload):
                    missing.append(item.name)

            if missing:
                # Изображения без данных остаются в проекте, но выглядят пустыми.
                project.missing_images = missing  # type: ignore[attr-defined]
            return project, store
    except zipfile.BadZipFile as error:
        raise ProjectError("Архив проекта повреждён.") from error


def project_display_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]
