from __future__ import annotations
import re

def hit(t,patterns):return any(re.search(p,t,re.I) for p in patterns)

def classify(prompt:str)->set[str]:
    t=' '.join(prompt.lower().split())
    # Explanatory and truly bounded edits should not activate a lifecycle skill.
    if hit(t,[r'^(what is|what does|tell me what|explain the difference|explain |summarize )',r'^(что такое|что значит|объясни|расскажи что)',r'^(fix one|change one|rename one|add one unit test|update one patch|format this|review this small|исправь один|переименуй одну|измени один|проверь пять строк|напиши простую функцию)']):
        return set()
    out=set()
    saas=hit(t,[r'\bsaas\b',r'subscription',r'tenant',r'workspace',r'billing',r'entitlement',r'activation',r'retention',r'churn',r'\bmrr\b',r'pricing',r'dunning',r'payment',r'тариф',r'подпис',r'биллинг',r'workspace',r'организац',r'оплат'])
    ai=hit(t,[r'\bai\b',r'ai-enabled',r'\bllm\b',r'\brag\b',r'prompt',r'golden dataset',r'model',r'regression eval',r'offline eval',r'tool call',r'grounded',r'hallucination',r'нейросет',r'модел',r'промпт',r'evals?'])
    mod=hit(t,[r'legacy',r'brownfield',r'monolith',r'characterization',r'strangler',r'expand[- ]contract',r'dual read',r'dual write',r'compatib',r'decommission',r'cutover',r'old service',r'public api migration',r'стар(ый|ую|ого|ой)',r'монолит',r'миграц',r'совместим'])
    rescue=hit(t,[r'project recovery',r'recovery plan',r'recovery release',r'freeze scope',r'missed .*date',r'ci is (red|broken)',r'build is red',r'scope (grows|is uncontrolled|expands)',r'ownerless',r'project is late',r'delivery dates keep slipping',r'not reproducible',r'сроки сорв',r'проект опозд',r'сборка пада',r'не воспроизвод',r'объ[её]м работ раст',r'scope раст',r'без владельц',r'блокеры.*владельц'])
    ops=hit(t,[r'closed beta',r'public beta',r'internal alpha',r'release candidate',r'\bga\b',r'canary',r'feature flag',r'allowlist',r'rollout',r'rollback',r'restore drill',r'backup restore',r'\bslo\b',r'runbook',r'incident',r'support owner',r'support channel',r'production rollout',r'model rollback',r'staged cutover',r'decommission gate',r'release gate',r'release readiness',r'закрыт.*бет',r'публичн.*бет',r'перед ga',r'feature flag',r'откат',r'восстанов',r'алерт',r'runbook',r'готовност.*релиз'])
    audit=hit(t,[r'\baudit\b',r'readiness',r'traceability',r'project-state',r'context pack',r'context packet',r'gate can advance',r'ready for implementation',r'fresh test log',r'evidence links',r'аудит',r'проверь готов',r'готовност',r'контекст.*пакет',r'проведи readiness'])
    broad=hit(t,[r'from idea',r'from problem interviews',r'from discovery',r'through .*beta',r'through several releases',r'multi[- ]team',r'multi[- ]year',r'year-long',r'several workstreams',r'multiple subsystems',r'across four teams',r'четырьмя командами',r'многомесяч',r'от интервью.*бет',r'от идеи',r'больш.*платформ',r'несколько подсистем',r'независим.*релиз']) or sum([saas,ai,mod,rescue,ops])>=3
    if broad:out.add('orchestrating-large-projects')
    if saas:out.add('building-saas-products')
    if ai:out.add('building-ai-products')
    if mod:out.add('modernizing-existing-projects')
    if rescue:out.add('rescuing-software-projects')
    if ops:out.add('releasing-and-operating-products')
    if audit:out.add('auditing-project-readiness')
    return out
