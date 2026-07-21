# Agentic Project Lifecycle

Agentic Project Lifecycle — плагин Codex с набором навыков для управления крупными программными проектами: от исследования задачи и планирования до выпуска, эксплуатации и разбора инцидентов.

Версия плагина `1.0.0-rc.1` упаковывает стабильный набор навыков `1.0.0` в проверяемый формат плагина. Статус release candidate нужен для проверки публичной установки перед первым GA-релизом плагина.

[English README](README.md)

## Что входит в набор

- `orchestrating-large-projects` — управляет жизненным циклом и направляет работу в профильные навыки.
- `building-saas-products` — помогает проектировать SaaS: tenancy, доступы, биллинг, активацию и эксплуатацию.
- `building-ai-products` — задаёт границы AI-продукта, оценки качества, меры безопасности и эксплуатационные проверки.
- `modernizing-existing-projects` — поддерживает анализ старой системы, миграцию, переключение и вывод старых компонентов.
- `rescuing-software-projects` — выполняет доказательный аудит проблемного проекта и формирует план восстановления.
- `releasing-and-operating-products` — готовит поэтапный релиз, откат, наблюдаемость и работу с инцидентами.
- `auditing-project-readiness` — проверяет состояние проекта, трассируемость требований и достаточность доказательств готовности.

## Установка в Codex

```text
codex plugin marketplace add VKK-00/agentic-project-lifecycle --ref v1.0.0-rc.1
codex plugin add agentic-project-lifecycle@vkk-00-agent-plugins
```

В Codex Desktop репозиторий можно добавить через **Plugins > Marketplaces**, а затем установить **Agentic Project Lifecycle**.

Для установки только навыков в Agent Skills-совместимый каталог:

```bash
python scripts/install_skills.py --target /path/to/project/.agents/skills
```

Без флага `--force` установщик не перезаписывает существующие навыки.

## Проверка исходного кода

Нужен Python 3.11 или новее.

```bash
python -m pip install -e ".[dev]"
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.0.0-rc.1 --output dist
```

Подробные результаты и ограничения описаны в [VALIDATION.md](VALIDATION.md), [STABILITY_REPORT.md](STABILITY_REPORT.md) и [evals/README.md](evals/README.md).

Оценки проверяют маршрутизацию и правила работы с артефактами, но не гарантируют корректность каждого ответа модели или успех любого проекта. Пользователь должен просматривать изменения и отдельно подтверждать действия с существенными последствиями.

## Документация

- [Архитектура](docs/ARCHITECTURE.md)
- [Процесс релиза](docs/RELEASE_PROCESS.md)
- [Поддержка](docs/SUPPORT.md)
- [Безопасность](SECURITY.md)
- [Участие в разработке](CONTRIBUTING.md)
- [Конфиденциальность](docs/PRIVACY.md)
- [Условия использования](docs/TERMS.md)

Лицензия — Apache-2.0. Это независимый общественный проект VKK-00, а не официальный продукт OpenAI. При разработке использовался OpenAI Codex; ответственность за опубликованный результат несёт сопровождающий проекта.
