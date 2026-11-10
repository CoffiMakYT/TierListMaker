"""Public TierMaker catalog browser and template importer.

Only public category/template pages and the site's public template-image
endpoint are used. No login, CAPTCHA or access-control workarounds.

The catalog is loaded page by page while the user scrolls, thumbnails are
fetched lazily for the visible rows, and template imports stream images into
the project in small batches as they finish downloading.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

from PySide6.QtCore import (
    QObject,
    QSize,
    QTimer,
    Signal,
    Qt,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSplitter, QVBoxLayout,
    QWidget, QProgressBar,
)

from .imagestore import ImageStore
from .model import Item, Project, Tier, new_id

BASE = "https://tiermaker.com"
UA = "TierListMaker/1.0 (public template browser)"
MAX_PAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 18 * 1024 * 1024
# Safety ceilings, not a practical limit: TierMaker templates may contain
# thousands of images and all of them are imported now.
MAX_IMPORT_IMAGES = 5000
MAX_IMPORT_TOTAL_BYTES = 3 * 1024 * 1024 * 1024
IMPORT_WORKERS = 6
IMPORT_BATCH_SIZE = 8
THUMBNAIL_BYTES = 3 * 1024 * 1024
THUMBNAIL_CONCURRENCY = 6
IMAGE_HOSTS = ("tiermaker.com", "www.tiermaker.com", "img.tiermaker.com")


def _get(url: str, limit: int = MAX_PAGE_BYTES) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,image/*,*/*;q=0.8"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("Response exceeds the download size limit")
    return data


def _allowed_image(url: str) -> bool:
    return urllib.parse.urlparse(url).hostname in IMAGE_HOSTS


def _manifest_images(manifest: list) -> list[dict]:
    """Normalise both public manifest shapes into ``{"src": ..., "id": ...}``.

    Newer templates return a list of ``{"src", "id"}`` dicts. Older ones
    return a directory path followed by plain file names, e.g.
    ``["/template_images/2022/…", "1.png", "2.png", …]``.
    """
    images: list[dict] = []
    directory = ""
    for index, item in enumerate(manifest):
        if isinstance(item, dict) and isinstance(item.get("src"), str):
            images.append({"src": item["src"], "id": str(item.get("id", index))})
            continue
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if text.startswith(("http://", "https://")):
            images.append({"src": text, "id": str(index)})
        elif re.search(r"\.(png|jpe?g|webp|gif)$", text, re.I):
            if directory:
                prefix = "https://tiermaker.com/images" if directory.startswith("/") else "https://tiermaker.com/images/"
                images.append({"src": prefix + directory.rstrip("/") + "/" + text.lstrip("/"), "id": str(index)})
        elif "/" in text or text.startswith("template_images"):
            directory = text
    return images


def safe_tiermaker_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("tiermaker.com", "www.tiermaker.com"):
        raise ValueError("Enter a public tiermaker.com template or category link")
    return urllib.parse.urlunparse(("https", "tiermaker.com", parsed.path, "", parsed.query, ""))


class CatalogParser(HTMLParser):
    """Extract category/template links and labels from public HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries: list[dict] = []
        self._anchor: dict | None = None
        self._anchor_depth = 0
        self._label_depth = 0
        self._label = False
        self._current_text: list[str] = []
        self.labels: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and not self._anchor:
            href = attrs.get("href", "")
            if href.startswith("/") and (href.startswith("/create/") or href.startswith("/categories/")):
                self._anchor = {"url": urllib.parse.urljoin(BASE, href), "title": "", "image": "", "count": ""}
                self._anchor_depth = 1
        if self._anchor:
            if tag == "img":
                self._anchor["image"] = attrs.get("data-src") or attrs.get("src") or self._anchor["image"]
            if "image-count-container" in attrs.get("class", ""):
                self._anchor["count"] = ""
                self._anchor["count_depth"] = 1
            elif self._anchor.get("count_depth"):
                self._anchor["count_depth"] += 1
            if "cat-header" in attrs.get("class", ""):
                self._anchor["title_depth"] = 1
            elif self._anchor.get("title_depth"):
                self._anchor["title_depth"] += 1
        if tag == "div" and "label-holder" in attrs.get("class", ""):
            self._label_depth = 1
        elif self._label_depth:
            self._label_depth += 1
        if tag == "span" and "label" in attrs.get("class", ""):
            self._label = True

    def handle_endtag(self, tag):
        if self._anchor:
            if self._anchor.get("count_depth"):
                self._anchor["count_depth"] -= 1
                if self._anchor["count_depth"] <= 0:
                    self._anchor.pop("count_depth", None)
            if self._anchor.get("title_depth"):
                self._anchor["title_depth"] -= 1
                if self._anchor["title_depth"] <= 0:
                    self._anchor.pop("title_depth", None)
            if tag == "a":
                self._anchor["title"] = " ".join(self._current_text).strip() or self._anchor["title"]
                if self._anchor["title"] and self._anchor["url"].split("/")[3] in ("create", "categories"):
                    self.entries.append(self._anchor)
                self._anchor = None
                self._current_text = []
        if self._label_depth:
            self._label_depth -= 1
        if tag == "span" and self._label:
            self._label = False

    def handle_data(self, data):
        if self._anchor:
            if self._anchor.get("title_depth") or "/categories/" in self._anchor["url"]:
                self._current_text.append(data.strip())
            if self._anchor.get("count_depth"):
                self._anchor["count"] += data.strip()
        if self._label:
            text = data.strip()
            if text:
                self.labels.append(text)


def fetch_categories() -> list[dict]:
    html = _get(BASE + "/categories/").decode("utf-8", "replace")
    found: dict[str, dict] = {}
    for match in re.finditer(r'<a[^>]+href=["\'](/categories/([^"\']+))["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href, slug_path, title = match.groups()
        slug = slug_path.strip("/").split("/")[0]
        if not slug:
            continue
        name = re.sub(r"<[^>]+>", " ", title)
        name = " ".join(name.split()) or urllib.parse.unquote(slug).replace("-", " ").title()
        found.setdefault(slug, {"name": name, "url": BASE + "/categories/" + slug})
    # Parse category display names from the page's category anchors.
    return sorted(found.values(), key=lambda x: x["name"].casefold())


def fetch_category_templates(url: str, page: int = 1, sort: str = "popular") -> list[dict]:
    url = safe_tiermaker_url(url)
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query.update({"page": [str(max(1, page))], "sort": [sort]})
    page_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urllib.parse.urlencode(query, doseq=True), ""))
    html = _get(page_url).decode("utf-8", "replace")
    parser = CatalogParser()
    parser.feed(html)
    entries = [x for x in parser.entries if "/create/" in x.get("url", "")]
    if not entries:
        pattern = re.compile(
            r"<a href=['\"](/create/[^'\"]+)['\"]>.*?"
            r"(?:class=['\"]image-count-container['\"]>(.*?)</div>)?.*?"
            r"<img[^>]+data-src=['\"]([^'\"]+)['\"].*?"
            r"<div class=['\"]cat-header['\"]>(.*?)</div>", re.I | re.S
        )
        for match in pattern.finditer(html):
            path, count, image, title = match.groups()
            entries.append({
                "url": urllib.parse.urljoin(BASE, path),
                "count": re.sub(r"<[^>]+>", "", count or "").strip(),
                "image": image,
                "title": " ".join(re.sub(r"<[^>]+>", " ", title).split()),
            })
    clean, seen = [], set()
    for entry in entries:
        if entry.get("url") not in seen and entry.get("title"):
            clean.append(entry)
            seen.add(entry["url"])
    return clean


def parse_template(url: str) -> tuple[str, list[str], list[dict]]:
    """Read title, visible row labels and public image manifest from a template."""
    url = safe_tiermaker_url(url)
    html = _get(url).decode("utf-8", "replace")
    parser = CatalogParser()
    parser.feed(html)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else "TierMaker template"
    title = re.sub(r"^Create a\s+", "", title, flags=re.I)
    title = re.sub(r"\s+Tier List Maker$", "", title, flags=re.I)
    labels = parser.labels

    # The public page itself declares the template slug and date used by its
    # documented frontend to request its public image list.
    slug_match = re.search(r'tierSystem\.initList\([^,]*,\s*["\']([^"\']+)', html)
    date_match = re.search(r'dateLastEdited\s*=\s*["\']([^"\']+)', html)
    variation_match = re.search(r'tierSystem\.initList\([^,]*,\s*["\'][^"\']+["\']\s*,\s*["\']([^"\']*)', html)
    if not slug_match:
        raise RuntimeError("Could not identify the public template image list")
    slug = slug_match.group(1)
    date = date_match.group(1) if date_match else ""
    variation = variation_match.group(1) if variation_match else ""
    api = BASE + "/api/?" + urllib.parse.urlencode({"type": "templates-v2", "id": slug, "lastEdited": date, "variation": variation})
    manifest = json.loads(_get(api).decode("utf-8", "replace"))
    if not isinstance(manifest, list):
        raise RuntimeError("TierMaker returned an unsupported image manifest")
    images = _manifest_images(manifest)
    if not images:
        raise RuntimeError("This template has no publicly available images")
    return title, labels, images


class Work(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)
    partial = Signal(object)

    def __init__(self, kind: str, *args):
        super().__init__()
        self.kind, self.args = kind, args
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def start(self) -> None:
        """Run the blocking network work in a daemon thread.

        Emitting Qt signals from a plain Python thread is safe: PySide queues
        them to the object's own thread. Daemon threads also let the dialog
        and the application close without crashing on a running QThread.
        """
        threading.Thread(
            target=self.run, name=f"tierlist-{self.kind}", daemon=True
        ).start()

    def run(self):
        try:
            if self.kind == "categories":
                value = fetch_categories()
            elif self.kind == "templates":
                value = fetch_category_templates(*self.args)
            elif self.kind == "import":
                value = self._import_template(*self.args)
            else:
                raise ValueError("Unknown catalog action")
            self.done.emit(value)
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))

    def _import_template(self, url: str):
        title, labels, images = parse_template(url)
        if len(images) > MAX_IMPORT_IMAGES:
            images = images[:MAX_IMPORT_IMAGES]
        total = len(images)
        if total <= 0:
            raise RuntimeError("This template has no publicly available images")
        self.progress.emit(0, total)

        def fetch(index: int, image: dict):
            if self._cancelled:
                return index, None
            try:
                image_url = urllib.parse.urljoin(BASE, image["src"])
                if not _allowed_image(image_url):
                    return index, None
                payload = _get(image_url, MAX_IMAGE_BYTES)
                name = image_url.rsplit("/", 1)[-1] or f"image-{index}"
                return index, (str(image.get("id", index)), name, payload)
            except Exception:
                return index, None

        imported = 0
        downloaded = 0
        total_bytes = 0
        results: dict[int, tuple | None] = {}
        next_index = 0
        batch: list[tuple[str, str, bytes]] = []
        pool = ThreadPoolExecutor(max_workers=IMPORT_WORKERS)
        try:
            futures = [pool.submit(fetch, index, image) for index, image in enumerate(images)]
            for future in as_completed(futures):
                index, entry = future.result()
                results[index] = entry
                if entry is not None:
                    downloaded += 1
                    total_bytes += len(entry[2])
                    if total_bytes > MAX_IMPORT_TOTAL_BYTES:
                        self._cancelled = True
                # Emit complete batches in original template order even though
                # downloads finish out of order.
                while next_index in results:
                    current = results.pop(next_index)
                    next_index += 1
                    if current is None:
                        continue
                    batch.append(current)
                    if len(batch) >= IMPORT_BATCH_SIZE:
                        self.partial.emit(batch)
                        imported += len(batch)
                        batch = []
                self.progress.emit(downloaded, total)
                if self._cancelled:
                    break
        finally:
            pool.shutdown(wait=not self._cancelled, cancel_futures=True)
        # Keep whatever finished before a cancellation (user close or size cap).
        for index in sorted(results):
            entry = results[index]
            if entry is not None:
                batch.append(entry)
        results.clear()
        if batch:
            self.partial.emit(batch)
            imported += len(batch)
        self.progress.emit(downloaded, total)
        if imported <= 0:
            raise RuntimeError("No template images could be downloaded")
        return {
            "title": title,
            "labels": labels,
            "images": [],
            "count": imported,
            "total": total,
            "template_url": url,
            "streamed": True,
        }


class _ThumbnailSignals(QObject):
    loaded = Signal(str, bytes)


class _ThumbnailJob:
    """Fetch one catalog thumbnail outside the GUI thread."""

    def __init__(self, url: str, signals: _ThumbnailSignals) -> None:
        self._url = url
        self._signals = signals

    def start(self) -> None:
        threading.Thread(target=self._run, name="tierlist-thumb", daemon=True).start()

    def _run(self) -> None:
        data = b""
        try:
            image_url = urllib.parse.urljoin(BASE, self._url)
            if _allowed_image(image_url):
                data = _get(image_url, THUMBNAIL_BYTES)
        except Exception:
            data = b""
        try:
            self._signals.loaded.emit(self._url, data)
        except RuntimeError:
            # The dialog was closed while the job was still running.
            pass


class WorkshopDialog(QDialog):
    """Workshop-like browser: category navigation, search, sorting, import and favorites."""
    imported = Signal(object)
    importBatch = Signal(object)
    importFailed = Signal(str)

    def __init__(self, lang: str = "ru", parent=None):
        super().__init__(parent)
        self.lang = lang
        self._worker: Work | None = None
        self._busy = False
        self._job_kind = ""
        self._job_args: tuple = ()
        self._templates: list[dict] = []
        self._categories: list[dict] = []
        self._favorites: set[str] = set()
        self._favorite_entries: dict[str, dict] = {}
        self._showing_favorites = False
        self._catalog_url = ""
        self._catalog_sort = "popular"
        self._catalog_seen: set[str] = set()
        self._catalog_pages = 0
        self._catalog_exhausted = False
        self._deferred_load = False
        self._suppress_scroll = False
        self._thumb_cache: dict[str, bytes] = {}
        self._thumb_pending: set[str] = set()
        self._thumb_signals = _ThumbnailSignals(self)
        self._thumb_signals.loaded.connect(self._on_thumbnail_loaded)
        self._import_count = 0
        self._import_total = 0
        self._cancelled_import = False
        self._closing = False
        # Filled by the host window: returns False when the user declines to
        # replace the current project.
        self.confirm_import = None
        from PySide6.QtCore import QSettings
        self._settings = QSettings()
        self._favorites = set(self._settings.value("workshop/favorites", []) or [])
        try:
            self._favorite_entries = json.loads(str(self._settings.value("workshop/favorite_entries", "{}")))
        except (TypeError, json.JSONDecodeError):
            self._favorite_entries = {}
        self._build_ui()
        self._start("categories")

    def tr(self, ru: str, en: str) -> str:
        return ru if self.lang == "ru" else en

    def _build_ui(self):
        self.setWindowTitle(self.tr("Мастерская шаблонов", "Template Workshop"))
        self.resize(1060, 700)
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.category = QComboBox(self)
        self.category.setMinimumWidth(210)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(self.tr("Поиск шаблонов…", "Search templates…"))
        self.sort = QComboBox(self)
        self.sort.addItem(self.tr("Популярные", "Popular"), "popular")
        self.sort.addItem(self.tr("Недавние", "Recent"), "recent")
        self.sort.addItem(self.tr("По алфавиту", "Alphabetical"), "alphabetical")
        self.sort_label = QLabel(self.tr("Сортировка", "Sort"), self)
        self.refresh_button = QPushButton(self.tr("Обновить", "Refresh"), self)
        self.favorites_button = QPushButton(self.tr("★ Избранное", "★ Favorites"), self)
        self.all_templates_button = QPushButton(self.tr("Все шаблоны", "All templates"), self)
        toolbar.addWidget(self.category)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.sort_label)
        toolbar.addWidget(self.sort)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.favorites_button)
        toolbar.addWidget(self.all_templates_button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal, self)
        self.list = QListWidget(splitter)
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setIconSize(QSize(150, 110))
        self.list.setGridSize(QSize(190, 175))
        self.list.setWordWrap(True)
        side = QWidget(splitter)
        side_layout = QVBoxLayout(side)
        self.details = QLabel(self.tr("Выберите шаблон", "Select a template"), side)
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignTop)
        self.preview = QListWidget(side)
        self.preview.setViewMode(QListWidget.IconMode)
        self.preview.setResizeMode(QListWidget.Adjust)
        self.preview.setMovement(QListWidget.Static)
        self.preview.setIconSize(QSize(42, 42))
        self.preview.setGridSize(QSize(52, 56))
        self.preview.setMaximumHeight(170)
        self.preview.setVisible(False)
        self.url = QLineEdit(side)
        self.url.setPlaceholderText("https://tiermaker.com/create/…")
        self.load_more = QPushButton(self.tr("Загрузить ещё", "Load more"), side)
        self.load_more.setVisible(False)
        self.import_button = QPushButton(self.tr("Импортировать в проект", "Import into project"), side)
        self.open_button = QPushButton(self.tr("Открыть на TierMaker", "Open on TierMaker"), side)
        side_layout.addWidget(self.details, 1)
        side_layout.addWidget(self.preview)
        side_layout.addWidget(self.url)
        side_layout.addWidget(self.load_more)
        side_layout.addWidget(self.import_button)
        side_layout.addWidget(self.open_button)
        splitter.addWidget(side)
        splitter.setSizes([700, 330])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.progress = QProgressBar(self)
        self.progress.setVisible(False)
        self.status = QLabel(self.tr("Каталог TierMaker · публичные шаблоны", "TierMaker catalog · public templates"), self)
        self.close_button = QPushButton(self.tr("Закрыть", "Close"), self)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.progress)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

        self.category.currentIndexChanged.connect(self._load_category)
        self.sort.currentIndexChanged.connect(self._load_category)
        self.search.textChanged.connect(self._filter)
        self.refresh_button.clicked.connect(self._refresh_catalog)
        self.favorites_button.clicked.connect(self._show_favorites)
        self.all_templates_button.clicked.connect(self._show_all_templates)
        self.list.currentItemChanged.connect(self._show_details)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(lambda *_: self._import_selected())
        self.list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.load_more.clicked.connect(self._load_next_page)
        self.import_button.clicked.connect(self._import_selected)
        self.open_button.clicked.connect(self._open_template)
        self.close_button.clicked.connect(self.reject)

    # ---------------------------------------------------------------- workers
    def _start(self, kind: str, *args) -> bool:
        if self._busy:
            if kind == "import":
                self.status.setText(self.tr("Уже выполняется загрузка", "A download is already running"))
            return False
        self._job_kind = kind
        self._job_args = args
        self._worker = Work(kind, *args)
        self._worker.done.connect(self._finished)
        self._worker.failed.connect(self._failed)
        self._worker.progress.connect(self._progress)
        self._worker.partial.connect(self._on_partial)
        self._busy = True
        self._worker.start()
        self.refresh_button.setEnabled(False)
        return True

    def _detach_worker(self) -> None:
        """Cancel a running job; its daemon thread finishes on its own."""
        self._deferred_load = False
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None

    def _job_finished(self) -> None:
        self._busy = False
        self._worker = None
        if self._deferred_load and not self._showing_favorites:
            self._deferred_load = False
            QTimer.singleShot(0, self._load_next_page)

    def _finished(self, result):
        self._busy = False
        self.refresh_button.setEnabled(True)
        self.progress.setVisible(False)
        self.load_more.setEnabled(True)
        if self._closing:
            self._worker = None
            return
        kind, args = self._job_kind, self._job_args
        if kind == "categories":
            self._categories = result
            self.category.blockSignals(True)
            self.category.clear()
            self.category.addItem(self.tr("Все категории", "All categories"), "https://tiermaker.com/categories/anime")
            for category in result:
                self.category.addItem(category["name"], category["url"])
            self.category.setCurrentIndex(0)
            self.category.blockSignals(False)
            QTimer.singleShot(0, self._load_category)
        elif kind == "templates":
            if not isinstance(result, list):
                pass
            elif (self._showing_favorites or not self._catalog_url
                    or not args or args[0] != self._catalog_url or args[2] != self._catalog_sort):
                pass
            else:
                seen = self._catalog_seen
                fresh = [entry for entry in result if entry.get("url") not in seen]
                self._catalog_pages += 1
                if not fresh:
                    self._catalog_exhausted = True
                self._templates.extend(fresh)
                for entry in fresh:
                    seen.add(entry.get("url"))
                self._append_entries(fresh)
                self._update_catalog_status()
                QTimer.singleShot(0, self._schedule_thumbnails)
                QTimer.singleShot(0, self._auto_fill)
        elif isinstance(result, dict) and result.get("streamed"):
            self._cancelled_import = False
            self._deferred_load = False
            self.imported.emit(result)
            self.accept()
        self._job_finished()

    def _failed(self, message: str):
        self._busy = False
        self.refresh_button.setEnabled(True)
        self.progress.setVisible(False)
        self.load_more.setEnabled(True)
        if self._closing:
            self._worker = None
            return
        kind = self._job_kind
        if kind == "templates" and self._templates:
            self.status.setText(self.tr("Не удалось загрузить следующую страницу", "Could not load the next page"))
            self._job_finished()
            return
        if kind == "import":
            self.preview.setVisible(False)
            self._cancelled_import = True
            self.status.setText(self.tr("Не удалось загрузить изображения", "Could not download template images"))
            self.importFailed.emit(message)
        else:
            self.status.setText(self.tr("Не удалось загрузить каталог", "Could not load catalog"))
        QMessageBox.warning(self, self.tr("Мастерская", "Workshop"), message)
        self._job_finished()

    def _progress(self, current: int, total: int):
        if self._job_kind == "import":
            self._import_total = total
            self.status.setText(self.tr(f"Скачано изображений: {current} из {total}", f"Downloaded {current} of {total}"))
            return
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)

    def _on_partial(self, batch):
        if self._cancelled_import:
            return
        self._import_count += len(batch)
        self.importBatch.emit(batch)
        for _image_id, name, payload in batch:
            pixmap = QPixmap()
            pixmap.loadFromData(payload)
            item = QListWidgetItem()
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            item.setToolTip(name)
            self.preview.addItem(item)
        self.preview.scrollToBottom()

    # ---------------------------------------------------------------- catalog
    def _refresh_catalog(self):
        if self.category.currentData():
            self._load_category()
        else:
            self._start("categories")

    def _load_category(self, *_):
        url = self.category.currentData()
        if not url:
            return
        if url.rstrip("/") == BASE + "/categories":
            url = BASE + "/categories/anime"
        self._showing_favorites = False
        self._begin_catalog(url, self.sort.currentData() or "popular")

    def _clear_list(self):
        self._suppress_scroll = True
        try:
            self.list.clear()
        finally:
            self._suppress_scroll = False

    def _begin_catalog(self, url: str, sort: str):
        self._catalog_url = url
        self._catalog_sort = sort
        self._catalog_seen = set()
        self._catalog_pages = 0
        self._catalog_exhausted = False
        self._templates = []
        self._deferred_load = False
        self._clear_list()
        self.load_more.setVisible(False)
        self.status.setText(self.tr("Загружаю список шаблонов…", "Loading templates…"))
        self._load_next_page()

    def _load_next_page(self, *_):
        if self._showing_favorites or not self._catalog_url or self._catalog_exhausted:
            return
        if self._busy:
            self._deferred_load = True
            return
        self._deferred_load = False
        page = self._catalog_pages + 1
        if not self._start("templates", self._catalog_url, page, self._catalog_sort):
            self._deferred_load = True

    def _on_scroll(self, value: int):
        if self._suppress_scroll:
            return
        self._schedule_thumbnails()
        bar = self.list.verticalScrollBar()
        if not self._showing_favorites and bar.maximum() - value < 180:
            if not self._catalog_exhausted:
                self._deferred_load = True
                self._load_next_page()

    def _auto_fill(self):
        if self._showing_favorites or self._catalog_exhausted:
            return
        bar = self.list.verticalScrollBar()
        if bar.maximum() <= 0 and self._templates:
            self._load_next_page()

    def _update_catalog_status(self):
        loaded = len(self._templates)
        if self._catalog_exhausted:
            self.status.setText(self.tr(f"Шаблонов: {loaded} · всё загружено", f"Templates: {loaded} · all loaded"))
            self.load_more.setVisible(False)
        else:
            self.status.setText(self.tr(f"Шаблонов: {loaded} · продолжаю загрузку", f"Templates: {loaded} · loading more"))
            self.load_more.setVisible(True)

    def _append_entries(self, entries: list[dict]):
        for entry in entries:
            title = entry.get("title") or "TierMaker template"
            count = entry.get("count", "")
            label = f"{title}\n{count} {self.tr('изобр.', 'items')}" if count else title
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            item.setToolTip(entry["url"])
            cached = self._thumb_cache.get(entry.get("image", ""))
            if cached:
                self._apply_thumbnail(item, cached)
            self.list.addItem(item)
        self._filter()

    def _render_templates(self, entries: list[dict]):
        self._clear_list()
        self._append_entries(entries)
        QTimer.singleShot(0, self._schedule_thumbnails)

    def _filter(self, *_):
        query = self.search.text().casefold().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(query not in item.text().casefold())
        QTimer.singleShot(0, self._schedule_thumbnails)

    # ------------------------------------------------------------- thumbnails
    def _apply_thumbnail(self, item: QListWidgetItem, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if not pixmap.isNull():
            item.setIcon(QIcon(pixmap))

    def _schedule_thumbnails(self) -> None:
        if self.list.count() == 0:
            return
        viewport = self.list.viewport().rect().adjusted(0, -220, 0, 220)
        for i in range(self.list.count()):
            if len(self._thumb_pending) >= THUMBNAIL_CONCURRENCY:
                break
            item = self.list.item(i)
            if item.isHidden():
                continue
            entry = item.data(Qt.UserRole) or {}
            url = entry.get("image") or ""
            if not url:
                continue
            cached = self._thumb_cache.get(url)
            if cached is not None:
                if item.icon().isNull() and cached:
                    self._apply_thumbnail(item, cached)
                continue
            if url in self._thumb_pending:
                continue
            if not self.list.visualItemRect(item).intersects(viewport):
                continue
            self._thumb_pending.add(url)
            _ThumbnailJob(url, self._thumb_signals).start()

    def _on_thumbnail_loaded(self, url: str, data: bytes) -> None:
        self._thumb_pending.discard(url)
        if data:
            self._thumb_cache[url] = data
            for i in range(self.list.count()):
                item = self.list.item(i)
                entry = item.data(Qt.UserRole) or {}
                if entry.get("image") == url and item.icon().isNull():
                    self._apply_thumbnail(item, data)
        QTimer.singleShot(0, self._schedule_thumbnails)

    # -------------------------------------------------------------- details
    def _show_details(self, item, _previous=None):
        if item is None:
            return
        data = item.data(Qt.UserRole) or {}
        self.details.setText(f"{data.get('title','')}\n\n{data.get('count','')} {self.tr('изображений', 'images')}\n\n{data.get('url','')}")
        self.url.setText(data.get("url", ""))

    def _selected(self):
        item = self.list.currentItem()
        return (item.data(Qt.UserRole) or {}) if item else {}

    def _show_favorites(self):
        if self._showing_favorites:
            self._showing_favorites = False
            self.load_more.setVisible(not self._catalog_exhausted and bool(self._catalog_url))
            self._render_templates(self._templates)
            self._update_catalog_status()
        else:
            self._showing_favorites = True
            self.load_more.setVisible(False)
            favorites = list(self._favorite_entries.values())
            if favorites:
                self._render_templates(favorites)
                self.status.setText(self.tr(f"Избранное: {len(favorites)}", f"Favorites: {len(favorites)}"))
            else:
                self._showing_favorites = False
                QMessageBox.information(self, self.tr("Избранное", "Favorites"), self.tr("Избранных шаблонов пока нет.", "No favorite templates yet."))

    def _show_all_templates(self):
        self._showing_favorites = False
        if self.category.currentIndex() == 0:
            self._render_templates(self._templates)
            self._update_catalog_status()
        else:
            self.category.setCurrentIndex(0)

    def _context_menu(self, position):
        item = self.list.itemAt(position)
        if item is None:
            return
        from PySide6.QtWidgets import QMenu
        entry = item.data(Qt.UserRole) or {}
        url = entry.get("url", "")
        menu = QMenu(self)
        favorite_text = self.tr("Убрать из избранного", "Remove from favorites") if url in self._favorites else self.tr("Добавить в избранное", "Add to favorites")
        action = menu.addAction(favorite_text)
        menu.addAction(self.tr("Открыть на сайте", "Open website"))
        chosen = menu.exec(self.list.mapToGlobal(position))
        if chosen is action:
            if url in self._favorites:
                self._favorites.remove(url)
                self._favorite_entries.pop(url, None)
            else:
                self._favorites.add(url)
                self._favorite_entries[url] = {k: v for k, v in entry.items() if k in ("url", "title", "image", "count")}
            self._settings.setValue("workshop/favorites", sorted(self._favorites))
            self._settings.setValue("workshop/favorite_entries", json.dumps(self._favorite_entries, ensure_ascii=False))
        elif chosen and chosen.text() == self.tr("Открыть на сайте", "Open website"):
            import webbrowser
            webbrowser.open(safe_tiermaker_url(url))

    # ---------------------------------------------------------------- import
    def _import_selected(self):
        data = self._selected()
        url = data.get("url") or self.url.text().strip()
        try:
            url = safe_tiermaker_url(url)
        except ValueError as error:
            QMessageBox.warning(self, self.tr("Неверная ссылка", "Invalid link"), str(error))
            return
        if self._busy:
            self.status.setText(self.tr("Дождитесь окончания текущей загрузки", "Wait for the current download to finish"))
            return
        if self.confirm_import is not None and not self.confirm_import():
            return
        self._favorites.add(url)
        self._settings.setValue("workshop/favorites", sorted(self._favorites))
        if data:
            self._favorite_entries[url] = {k: v for k, v in data.items() if k in ("url", "title", "image", "count")}
            self._settings.setValue("workshop/favorite_entries", json.dumps(self._favorite_entries, ensure_ascii=False))
        self._import_count = 0
        self._import_total = 0
        self._cancelled_import = False
        self.preview.clear()
        self.preview.setVisible(True)
        self.status.setText(self.tr("Загружаю изображения шаблона…", "Downloading template images…"))
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self._start("import", url)

    def _open_template(self):
        import webbrowser
        url = self._selected().get("url") or self.url.text().strip()
        try:
            webbrowser.open(safe_tiermaker_url(url))
        except ValueError as error:
            QMessageBox.warning(self, self.tr("Неверная ссылка", "Invalid link"), str(error))

    # -------------------------------------------------------------- shutdown
    def _cancel_worker(self) -> None:
        if self._job_kind == "import" and self._worker is not None:
            self._cancelled_import = True
            self._worker.cancel()
        self._detach_worker()

    def reject(self) -> None:
        self._closing = True
        self._cancel_worker()
        super().reject()

    def closeEvent(self, event) -> None:
        self._closing = True
        self._cancel_worker()
        super().closeEvent(event)


def apply_import(result: dict, project: Project, store: ImageStore, include_images: bool = True) -> int:
    """Add template items to project pool and use its tier labels where available.

    ``include_images=False`` is used by the streaming import path: the images
    were already appended to the project batch by batch, so only metadata and
    tier labels are applied here.
    """
    labels = [str(x).strip() for x in result.get("labels", []) if str(x).strip()]
    if labels:
        project.tiers = [Tier(new_id(), label[:80], project.tiers[i].color if i < len(project.tiers) else "#6b8fd6") for i, label in enumerate(labels[:20])]
    added = 0
    if include_images:
        for _, name, payload in result.get("images", []):
            item_id = new_id()
            if not store.add_bytes(item_id, payload):
                continue
            ext = ".webp" if name.lower().endswith(".webp") else ".jpg" if name.lower().endswith((".jpg", ".jpeg")) else ".png"
            project.items[item_id] = Item(item_id, name, ext)
            project.pool.append(item_id)
            added += 1
    else:
        added = int(result.get("count") or 0)
    project.name = result.get("title") or project.name
    project.dirty = True
    return added