# Публикация на GitHub

Папка уже подготовлена: исходный код, README, лицензия, `.gitignore`, скриншот и скрипты сборки. Ниже — что осталось сделать вручную.

## 1. Проверьте данные

- В `LICENSE` при необходимости замените `Copyright (c) 2026 Vlad` на своё имя.
- В `README.md` замените `<URL-репозитория>` после создания репозитория.
- При желании переименуйте проект (сейчас `TierListMaker`).

## 2. Создайте репозиторий

На GitHub: **New repository** → имя, например, `TierListMaker` → **Create repository** (без README и лицензии, они уже есть).

## 3. Отправьте код

Если локальный Git-репозиторий ещё не создан:

```powershell
cd D:\Vlad\TierListMaker
git init -b main
git add .
git commit -m "Initial release"
```

Добавьте удалённый репозиторий и отправьте код:

```powershell
git remote add origin https://github.com/ПОЛЬЗОВАТЕЛЬ/TierListMaker.git
git push -u origin main
```

## 4. Соберите релиз

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Готовый файл: `dist\TierListMaker.exe`.

Создайте релиз через GitHub CLI:

```powershell
gh release create v1.0.0 dist\TierListMaker.exe `
  --title "Tier List Maker 1.0.0" `
  --notes "Первый публичный релиз."
```

Или вручную: **Releases → Draft a new release**, прикрепите `dist\TierListMaker.exe`.

## Что не попадает в репозиторий

- `build/`, `dist/`, `*.spec` — артефакты PyInstaller.
- `__pycache__/`, `*.pyc` — байт-код Python.
- `.venv/`, `*.tierproj` и локальные файлы IDE — см. `.gitignore`.