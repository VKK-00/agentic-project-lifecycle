---
name: building-large-software-projects
description: Use when a broad or ambiguous software-product request spans multiple subsystems, stakeholders, teams, or releases, or when the user asks to take an idea from brainstorming/discovery through UX/UI, architecture, implementation, beta, launch, and operations. Do not use for an isolated bugfix, small refactor, or one already-approved feature.
---

# Ведение большого software-проекта

## Основной принцип

Веди проект как state machine со stage gates. Чат — временный контекст; репозиторий, утверждённые документы, код, тесты и verification evidence — источники истины.

## Жёсткие правила

1. Определи текущую фазу, outcome и недостающие решения. Не начинай production-bound код до утверждения problem, scope, acceptance criteria и релевантного design. Допустим только явно disposable spike/prototype с hypothesis, timebox и exit criteria.
2. Задавай один существенный вопрос за сообщение, не повторяй уже отвеченное и предпочитай 2–4 варианта.
3. Разделяй facts, assumptions, decisions, open questions и contradictions. Не превращай assumption в requirement молча.
4. Для материального product, UX или architecture decision предложи 2–3 подхода с trade-offs и рекомендацией.
5. Если есть независимые outcomes, release cadences или data/security boundaries, сначала разложи работу на subprojects. Каждый проходит собственный `spec → plan → implementation → verification`.
6. Создавай документы just-in-time. Не объявляй `done` без воспроизводимых проверок и не планируй release без telemetry, rollout и rollback.

## Рабочий цикл

1. **Orient.** Исследуй существующие файлы, docs, `AGENTS.md`, code structure, `git status` и recent commits. Найди `docs/project-state.yaml` или зафиксируй greenfield state.
2. **Выбери фазу.** Используй [lifecycle.md](references/lifecycle.md). Назови deliverable, ближайший gate и главный risk.
3. **Уточни.** Для discovery используй [interviewing.md](references/interviewing.md). После тематического блока обнови decision ledger и кратко перескажи понимание.
4. **Зафиксируй.** Используй [artifacts-and-traceability.md](references/artifacts-and-traceability.md). Обновляй canonical source и связанные IDs; не дублируй полные правила.
5. **Спланируй и поставь.** Используй [planning-and-execution.md](references/planning-and-execution.md). Детализируй только ближайшую ready-часть, начни с walking skeleton, работай вертикальными independently verifiable tasks и изолируй parallel work по branches/worktrees.
6. **Проверь и выпусти.** Используй [quality-release-operations.md](references/quality-release-operations.md). Сохрани commands/results, ручные сценарии, limitations, approvals и rollback evidence; после release сравни hypothesis с metrics и обнови roadmap.

## Stage gates

Остановись перед решением, меняющим scope, стоимость, безопасность, public contracts или release commitment. Запроси approval конкретного bounded decision, не абстрактное «продолжать?». После approval обнови status и, в Git-проекте, зафиксируй логически завершённый change.

## Контракт результата

В конце сессии сообщи: current phase и goal; прочитанные/изменённые files; decisions и assumptions; фактические verification results; residual risks; следующий gate или independently executable task.

## Шаблоны

Используй `assets/templates/` и замени все markers перед commit. Для безопасного scaffolding запусти из директории skill: `python3 scripts/scaffold_project.py --help`; скрипт не перезаписывает файлы без `--force`.

## Красные флаги

Вернись к пропущенному gate при любом признаке: architecture до problem validation; один mega-plan для всех горизонтов; несколько агентов меняют один contract; horizontal layers без раннего end-to-end path; acceptance уровня «выглядит нормально»; `done` без evidence; beta/GA без monitoring, support owner или rollback.
