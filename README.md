# Tier List Maker

Локальный редактор тирлистов для Windows 10/11. Проект и изображения хранятся на компьютере; для обычной работы интернет не нужен. Встроенная «Мастерская» умеет импортировать публичные шаблоны TierMaker.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🇷🇺 Русский

### Возможности

- Импорт JPG/JPEG, PNG и WEBP: мультивыбор или перетаскивание из Проводника.
- Уровни рейтинга: добавление, удаление, переименование, цвет и изменение порядка.
- Перетаскивание изображений между уровнями и нераспределённой областью, изменение порядка карточек.
- Форматы карточек 3:4, 1:1, 4:3; режимы отображения «Заполнить» и «Вписать» без искажения пропорций.
- Отмена и повтор действий.
- Проект `.tierproj` — ZIP с `project.json` и оригиналами изображений в `images/`.
- Экспорт PNG/JPG с предпросмотром, заголовком, цветом фона, разрешением и настройкой нераспределённых карточек.
- Тёмная и светлая темы, переключение интерфейса RU/EN.
- «Мастерская»: категории, поиск, сортировка и избранное шаблонов TierMaker.
- Динамическая загрузка каталога: страницы шаблонов подгружаются по мере прокрутки, миниатюры — по мере появления на экране.
- Потоковый импорт: картинки шаблона добавляются в проект небольшими порциями сразу после скачивания. Шаблоны с тысячами изображений (больше 150) поддерживаются.

### Быстрый старт

Скачайте `TierListMaker.exe` из раздела **Releases** (если сборка опубликована) и запустите. Установка не требуется.

### Запуск из исходников

Нужен Python 3.10 или новее.

```powershell
git clone <URL-репозитория>
cd TierListMaker

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python main.py
```

### Сборка EXE

Скрипты сборки используют PyInstaller и создают один самодостаточный файл `dist\TierListMaker.exe`.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Или двойным щелчком по `build_exe.cmd` из Проводника.

### Мастерская TierMaker

Используются только публичные страницы каталога и публичный endpoint изображений: без входа в аккаунт, без обхода CAPTCHA и ограничений доступа. Для мастерской нужен интернет.

- список шаблонов подгружается постранично по мере прокрутки;
- миниатюры загружаются лениво, только для видимых элементов;
- изображения шаблона скачиваются параллельно и сразу попадают в проект пачками;
- защитные ограничения: до 5000 изображений и 3 ГБ на один шаблон.

### Горячие клавиши

| Действие | Клавиши |
|---|---|
| Новый проект | `Ctrl+N` |
| Открыть проект | `Ctrl+O` |
| Сохранить | `Ctrl+S` |
| Сохранить как | `Ctrl+Shift+S` |
| Импорт изображений | `Ctrl+I` |
| Экспорт | `Ctrl+E` |
| Отменить / повторить | `Ctrl+Z` / `Ctrl+Y` |

### Формат проекта

`.tierproj` — обычный ZIP-архив:

```text
project.json      метаданные: уровни, порядок карточек, настройки вида
images/<id>.png   оригиналы изображений без пережатия
```

### Структура репозитория

```text
main.py                 запуск приложения
tierlist/               исходный код: интерфейс, модель, импорт, экспорт
  workshop.py           каталог и парсер публичных шаблонов TierMaker
  main_window.py        главное окно
  model.py              модель проекта
  imagestore.py         хранение изображений
  export_dialog.py      диалог экспорта
  i18n.py               строки интерфейса RU/EN
assets/                 иконки приложения
build_exe.ps1           сборка EXE (PowerShell)
build_exe.cmd           сборка EXE (CMD, двойной щелчок)
requirements.txt        зависимости приложения
requirements-dev.txt    зависимости сборки (PyInstaller)
```

---

## 🇬🇧 English

A local tier list editor for Windows 10/11. Projects and images are stored on your computer; the internet is not required for everyday work. The built-in Workshop can import public TierMaker templates.

### Features

- Import JPG/JPEG, PNG and WEBP: multi-select or drag & drop from Explorer.
- Rating tiers: add, delete, rename, recolor and reorder.
- Drag images between tiers and the unranked area, reorder cards.
- Card shapes 3:4, 1:1, 4:3; "Cover" and "Contain" fit modes without distortion.
- Undo and redo.
- `.tierproj` project — a ZIP with `project.json` and original images in `images/`.
- PNG/JPG export with preview, title, background color, resolution and unranked card options.
- Dark and light themes, RU/EN interface switch.
- Workshop: categories, search, sorting and favorites for TierMaker templates.
- Dynamic catalog loading: template pages load as you scroll, thumbnails load as they become visible.
- Streaming import: template images are added to the project in small batches right after downloading. Templates with thousands of images (more than 150) are supported.

### Quick start

Download `TierListMaker.exe` from **Releases** (if published) and run it. No installation required.

### Running from source

Python 3.10 or newer is required.

```powershell
git clone <REPOSITORY-URL>
cd TierListMaker

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python main.py
```

### Building the EXE

The build scripts use PyInstaller and produce a single self-contained `dist\TierListMaker.exe`.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Or double-click `build_exe.cmd` in Explorer.

### TierMaker Workshop

Only public catalog pages and the public template-image endpoint are used: no login, no CAPTCHA or access-control workarounds. The Workshop requires an internet connection.

- the template list loads page by page as you scroll;
- thumbnails are loaded lazily, only for visible items;
- template images are downloaded in parallel and added to the project in batches;
- safety limits: up to 5000 images and 3 GB per template.

### Keyboard shortcuts

| Action | Keys |
|---|---|
| New project | `Ctrl+N` |
| Open project | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save as | `Ctrl+Shift+S` |
| Import images | `Ctrl+I` |
| Export | `Ctrl+E` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` |

### Project format

`.tierproj` is a plain ZIP archive:

```text
project.json      metadata: tiers, card order, view settings
images/<id>.png   original images without re-encoding
```

### Repository layout

```text
main.py                 application entry point
tierlist/               source code: UI, model, import, export
  workshop.py           TierMaker catalog browser and parser
  main_window.py        main window
  model.py              project model
  imagestore.py         image storage
  export_dialog.py      export dialog
  i18n.py               RU/EN UI strings
assets/                 application icons
build_exe.ps1           EXE build (PowerShell)
build_exe.cmd           EXE build (CMD, double-click)
requirements.txt        application dependencies
requirements-dev.txt    build dependencies (PyInstaller)
```

---

## License

[MIT](LICENSE)
