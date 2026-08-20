# Agentic Project Lifecycle

Agentic Project Lifecycle — кроссплатформенный набор навыков для управления крупными программными проектами: от исследования задачи и планирования до выпуска, эксплуатации и разбора инцидентов. Codex — один из поддерживаемых native distribution targets, а не единственная платформа.

[`v1.1.0-rc.1`](https://github.com/VKK-00/agentic-project-lifecycle/releases/tag/v1.1.0-rc.1) — опубликованный prerelease с детерминированными assets, SHA-256 checksums и provenance/SBOM attestations. Stable `1.1.0` остаётся заблокированным до повторяемого authenticated live-agent evaluation.

[English](README.md) | [Русский](README.ru.md) | [Українська](README.uk.md)

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
codex plugin marketplace add VKK-00/agentic-project-lifecycle --ref v1.1.0-rc.1
codex plugin add agentic-project-lifecycle@vkk-00-agent-plugins
```

В Codex Desktop репозиторий можно добавить через **Plugins > Marketplaces**, а затем установить **Agentic Project Lifecycle**.

## Распространение для платформ

APL использует один канонический набор из семи навыков и создаёт детерминированные bundles для Agent Skills, Codex, Claude Code, GitHub Copilot, Cursor, Kimi Code, Gemini CLI, OpenCode, Factory Droid, Amp, Devin, Pi, Hermes, Antigravity и Gemini Enterprise.

```bash
python apl platform list
python apl platform install codex --scope project --root /path/to/project
python apl platform verify /path/to/project/.codex/skills/agentic-project-lifecycle
```

Установщик проверяет staging-копию до атомарной публикации и восстанавливает предыдущую установку, если финальная проверка не проходит. Для `--scope user` всегда нужен явный `--root`.

Distribution не доказывает, что платформа активировала навыки или что модель им следовала: activation evidence и bounded execution — отдельные claims. В committed activation matrix все платформы намеренно имеют статус `not-live-tested`.

## Установка в совместимый каталог

Для установки только навыков в Agent Skills-совместимый каталог:

```bash
python apl platform install agent-skills --scope project --root /path/to/project
```

Без флага `--force` установщик не перезаписывает существующую установку.

## Проверка исходного кода

Нужен Python 3.11 или новее.

```bash
python -m pip install -e ".[dev]"
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.1.0-rc.1 --output dist
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
