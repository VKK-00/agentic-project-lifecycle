# Анализ проекта

## Цель проекта

Опубликовать Agentic Project Lifecycle как проверяемый skills-only plugin для Codex и совместимых с Agent Skills клиентов. Репозиторий должен предоставлять GitHub marketplace source, воспроизводимый prerelease и доказательства качества без заявления об официальной поддержке OpenAI.

## Что делает проект

Проект объединяет семь специализированных skills для управления крупными software-, SaaS- и AI-проектами:

- оркестрация жизненного цикла и stage gates;
- SaaS-архитектура, billing и продуктовые метрики;
- AI evaluation, model operations и safety;
- модернизация brownfield-систем;
- восстановление проблемных проектов;
- staged releases и эксплуатация;
- аудит project state, traceability и release readiness.

## Структура репозитория

Каноническая структура:

```text
.agents/plugins/marketplace.json
plugins/agentic-project-lifecycle/
  .codex-plugin/plugin.json
  skills/<seven-skill-directories>/
  assets/
evals/
tests/
scripts/
docs/
.github/workflows/
```

`plugins/agentic-project-lifecycle/skills/` является единственным каноническим источником устанавливаемых skills. Evals, fixture-проекты, тесты и release tooling не входят в installable plugin payload.

## Ключевые файлы, модули, классы и функции

- `.agents/plugins/marketplace.json` — repo marketplace и путь к plugin.
- `plugins/agentic-project-lifecycle/.codex-plugin/plugin.json` — manifest версии, publisher metadata, bundled skills и UI metadata.
- `plugins/agentic-project-lifecycle/skills/*/SKILL.md` — trigger contracts и нормативные правила.
- `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/` — детерминированные проверки state, traceability, evidence и release readiness.
- `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/scripts/scaffold_project.py` — безопасный генератор проектных артефактов.
- `validate.py` — агрегированная проверка manifest, skills, Python и evaluation gates.
- `evals/` — trigger routing, pressure scenarios, fixture trials, public-repository evidence и ablation.
- `tests/test_suite.py` — regression-проверки стабильности suite и installer behavior.
- `scripts/build_release.py` — воспроизводимая упаковка plugin и checksums.
- `.github/dependabot.yml` — еженедельная проверка обновлений GitHub Actions и Python-зависимостей.

## Как система работает end-to-end

1. Пользователь добавляет GitHub-репозиторий как Codex marketplace source.
2. Codex читает `.agents/plugins/marketplace.json` и находит plugin.
3. Plugin manifest подключает семь каталогов из `skills/`.
4. Trigger description выбирает минимальный набор skills для задачи.
5. Оркестратор направляет работу к профильным skills.
6. Аудиторы запускают детерминированные validators и сохраняют фактические evidence.
7. CI воспроизводит tests, evals, plugin validation и release packaging.

## Поток данных

Plugin не содержит MCP-сервера, внешней базы данных или собственной telemetry. Skills читают файлы проекта только в контексте разрешений Codex. Bundled scripts получают пути и конфигурацию через CLI-аргументы, читают локальные YAML/JSON/Markdown-файлы и пишут только явно указанные output-артефакты.

`collect_verification.py` запускает массив argv из явно переданного YAML. Он не использует shell-строку, но конфигурацию следует считать исполняемой и проверять перед запуском.

## Внешние интеграции

- GitHub — исходный код, issues, Actions и releases.
- GitHub Dependabot и secret scanning — alerts, security updates и защита push от известных типов секретов.
- Codex Plugins — plugin manifest, marketplace discovery, installation cache и Plugins Directory.
- OpenAI Platform — отдельная последующая submission/review процедура для публичного Plugins Directory.

## Конфигурация, переменные окружения и секреты

Runtime-секреты не требуются. Repository и plugin не должны содержать токены, cookies, `.env`, приватные ключи, machine-local paths или demo credentials.

Release builder может принимать стандартный `SOURCE_DATE_EPOCH` для воспроизводимых timestamps. GitHub Actions использует автоматически предоставляемый `GITHUB_TOKEN`; он не записывается в репозиторий.

## Команды запуска, тестирования, проверки и отладки

Планируемый обязательный набор:

```powershell
python -m pip install -e .[dev]
python validate.py
python -m pytest -q
python scripts/validate_publication.py
python scripts/build_release.py --version 1.0.0-rc.1 --output dist
```

Дополнительно каждый skill проверяется локальным Codex `quick_validate.py`, а plugin — `plugin-creator/scripts/validate_plugin.py`.

## Важные архитектурные решения

- `DEC-001`: использовать orchestrator-plus-specialists вместо монолитного skill.
- `DEC-002`: хранить plugin в `plugins/agentic-project-lifecycle`, чтобы repo marketplace мог расширяться без смены формата.
- `DEC-003`: не включать evals/tests в installable plugin payload.
- `DEC-004`: выпускать сначала `v1.0.0-rc.1`; окончательный `v1.0.0` возможен после clean-install и внешнего smoke test.
- `DEC-005`: фактический publisher — `VKK-00`; OpenAI/ChatGPT указывается только как используемый инструмент, без заявления об официальном авторстве или endorsement.
- `DEC-006`: plugin не содержит MCP/app/hooks; функции ограничены skills, references, templates и локальными scripts.

## Рассмотренные варианты реализации

1. Plugin в корне репозитория. Проще, но хуже масштабируется как marketplace и отклоняется от документированного repo layout.
2. Plugin в `plugins/agentic-project-lifecycle` — выбранный вариант. Он соответствует repo marketplace pattern и отделяет устанавливаемый payload от evidence/tooling.
3. Дублировать `skills/` в корне и внутри plugin. Отклонено из-за риска расхождения двух источников истины.

## Текущие ограничения, риски и открытые вопросы

- Два held-out routing case из исходных 50 не активировали по одному вторичному skill; promotion thresholds при этом пройдены.
- Evaluation измеряет детерминированное покрытие инструкций и ограниченные trials, а не гарантированное поведение любой модели.
- Public OpenAI submission требует verified developer identity и Apps Management Write; это проверяется только в Platform portal.
- Privacy/terms/support URL должны быть публичны до submission.
- GitHub repository становится public только после secret scan и проверки release candidate.

## Что нужно обновлять при изменениях проекта

- version одновременно в `suite.yaml`, plugin manifest, skill metadata и release notes;
- список skills одновременно в `suite.yaml`, plugin tree, README и submission materials;
- eval evidence после изменения normative rules или trigger descriptions;
- checksums и release report для каждого release artifact;
- privacy/security документацию при добавлении MCP, connectors, networking или telemetry;
- этот анализ при изменении plugin layout, data flow, external integrations или release process.

## Журнал существенных изменений анализа

- 2026-07-21 — создан начальный анализ перед публикацией greenfield GitHub-репозитория и упаковкой suite 1.0.0 как Codex skills-only plugin.
- 2026-07-21 — CI actions закреплены на immutable SHA актуальных релизов; добавлены Dependabot, secret scanning, push protection и private vulnerability reporting.
