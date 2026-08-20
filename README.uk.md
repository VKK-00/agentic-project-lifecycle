# Agentic Project Lifecycle

Agentic Project Lifecycle — плагін Codex із набором навичок для керування великими програмними проєктами: від дослідження завдання та планування до випуску, експлуатації й аналізу інцидентів.

[`v1.1.0-rc.1`](https://github.com/VKK-00/agentic-project-lifecycle/releases/tag/v1.1.0-rc.1) — опублікований prerelease із детермінованими assets, SHA-256 checksums і provenance/SBOM attestations. Stable `1.1.0` залишається заблокованим до повторюваного authenticated live-agent evaluation.

[English](README.md) | [Русский](README.ru.md) | [Українська](README.uk.md)

## Що входить до набору

- `orchestrating-large-projects` — керує життєвим циклом і спрямовує роботу до профільних навичок.
- `building-saas-products` — допомагає проєктувати SaaS: tenancy, доступи, білінг, активацію та експлуатацію.
- `building-ai-products` — визначає межі AI-продукту, оцінювання якості, заходи безпеки й експлуатаційні перевірки.
- `modernizing-existing-projects` — підтримує аналіз наявної системи, міграцію, перемикання та виведення старих компонентів з експлуатації.
- `rescuing-software-projects` — виконує доказовий аудит проблемного проєкту та формує план відновлення.
- `releasing-and-operating-products` — готує поетапний реліз, відкат, спостережуваність і роботу з інцидентами.
- `auditing-project-readiness` — перевіряє стан проєкту, трасованість вимог і достатність доказів готовності.

## Встановлення в Codex

```text
codex plugin marketplace add VKK-00/agentic-project-lifecycle --ref v1.1.0-rc.1
codex plugin add agentic-project-lifecycle@vkk-00-agent-plugins
```

У Codex Desktop репозиторій можна додати через **Plugins > Marketplaces**, а потім встановити **Agentic Project Lifecycle**.

## Поширення для платформ

APL має один канонічний набір із семи навичок і створює детерміновані bundles для Agent Skills, Codex, Claude Code, GitHub Copilot, Cursor, Kimi Code, Gemini CLI, OpenCode, Factory Droid, Amp, Devin, Pi, Hermes, Antigravity та Gemini Enterprise.

```bash
python apl platform list
python apl platform install codex --scope project --root /path/to/project
python apl platform verify /path/to/project/.codex/skills/agentic-project-lifecycle
```

Інсталятор перевіряє staging-копію перед атомарною публікацією та відновлює попередню інсталяцію, якщо фінальна перевірка не пройшла. Для `--scope user` завжди потрібен явний `--root`.

Distribution не є доказом того, що платформа активувала навички або що модель їх виконувала: activation evidence й bounded execution — окремі claims. У committed activation matrix усі платформи навмисно мають стан `not-live-tested`.

## Встановлення у сумісний каталог

Для встановлення лише навичок у каталог, сумісний з Agent Skills:

```bash
python apl platform install agent-skills --scope project --root /path/to/project
```

Без прапорця `--force` інсталятор не перезаписує наявну інсталяцію.

## Перевірка вихідного коду

Потрібен Python 3.11 або новіший.

```bash
python -m pip install -e ".[dev]"
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.1.0-rc.1 --output dist
```

Докладні результати й обмеження описані у [VALIDATION.md](VALIDATION.md), [STABILITY_REPORT.md](STABILITY_REPORT.md) та [evals/README.md](evals/README.md).

Оцінювання перевіряють маршрутизацію та правила роботи з артефактами, але не гарантують правильність кожної відповіді моделі або успіх будь-якого проєкту. Користувач має переглядати зміни й окремо підтверджувати дії з істотними наслідками.

## Документація

- [Архітектура](docs/ARCHITECTURE.md)
- [Процес релізу](docs/RELEASE_PROCESS.md)
- [Підтримка](docs/SUPPORT.md)
- [Безпека](SECURITY.md)
- [Участь у розробці](CONTRIBUTING.md)
- [Конфіденційність](docs/PRIVACY.md)
- [Умови використання](docs/TERMS.md)

Ліцензія — Apache-2.0. Це незалежний проєкт спільноти VKK-00, а не офіційний продукт OpenAI. Під час розробки використовувався OpenAI Codex; відповідальність за опублікований результат несе супроводжувач проєкту.
