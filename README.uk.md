# Agentic Project Lifecycle

Agentic Project Lifecycle — плагін Codex із набором навичок для керування великими програмними проєктами: від дослідження завдання та планування до випуску, експлуатації й аналізу інцидентів.

Версія плагіна `1.0.0-rc.1` пакує стабільний набір навичок `1.0.0` у перевірюваний формат плагіна. Статус release candidate потрібен для перевірки публічного встановлення перед першим GA-релізом плагіна.

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
codex plugin marketplace add VKK-00/agentic-project-lifecycle --ref v1.0.0-rc.1
codex plugin add agentic-project-lifecycle@vkk-00-agent-plugins
```

У Codex Desktop репозиторій можна додати через **Plugins > Marketplaces**, а потім встановити **Agentic Project Lifecycle**.

Для встановлення лише навичок у каталог, сумісний з Agent Skills:

```bash
python scripts/install_skills.py --target /path/to/project/.agents/skills
```

Без прапорця `--force` інсталятор не перезаписує наявні навички.

## Перевірка вихідного коду

Потрібен Python 3.11 або новіший.

```bash
python -m pip install -e ".[dev]"
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.0.0-rc.1 --output dist
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
