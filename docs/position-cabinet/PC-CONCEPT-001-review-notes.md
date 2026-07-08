# PC-CONCEPT-001 — Review Notes

**Document:** [PC-CONCEPT-001-unified-position-cabinet-concept.md](./PC-CONCEPT-001-unified-position-cabinet-concept.md)  
**Status:** Draft review backlog  
**Purpose:** Вопросы для дальнейшей архитектурной ревизии. Не являются решениями.

---

## 1. Почему Position Cabinet, а не Employee Workspace / User Workspace?

В PC-CONCEPT-001 Position Cabinet описан как «единое рабочее пространство пользователя», а не как кабинет сотрудника. Требуется явное обоснование выбора термина **Position Cabinet** относительно альтернатив **Employee Workspace** и **User Workspace**:

- что именно привязано к **Position**, а что — к **Person / Employee / Platform User**;
- не создаёт ли формулировка «единое пользовательское пространство» семантический конфликт с ARCH-001 / GLOSS-B4-001, где Cabinet описан как сущность, связанная с должностью (1:1 с Position);
- нужен ли отдельный термин для presentation shell vs position-bound workspace.

## 2. Почему Cabinet открывается через Position Assignment?

Архитектурная схема (§11) строит цепочку: **Сотрудник → Назначение на должность → Должность → Position Cabinet**.

Вопросы для ревизии:

- является ли **Position Assignment** единственной и обязательной точкой входа в Cabinet для всех пользователей;
- как моделируется доступ при совмещении, acting / временном исполнении, vacancy;
- как это согласуется с ADR-051 (cabinet access resolution) и текущей реализацией `/auth/me`.

## 3. Self Visibility как отдельная модель доступа

§6–§7 вводят **Self Visibility** как модель, ортогональную ACCESS-001.

Вопросы:

- где Self Visibility фиксируется normatively (отдельный register, расширение ACCESS-001, ADR);
- какие категории данных попадают под self-read по умолчанию и как задаются исключения «повышенной конфиденциальности»;
- как Self Visibility соотносится с Permission Template и administrative permissions без смешения контуров.

## 4. Workspace Composer: кабинет агрегирует данные, но не владеет ими

§3 и §5 утверждают, что Position Cabinet **компонует** пользовательское пространство, но **не владеет** доменными данными.

Вопросы:

- нужен ли явный архитектурный паттерн **Workspace Composer** (или эквивалент) в governance-документах;
- где проходит граница между composition (UI/navigation) и orchestration (бизнес-процессы);
- как composer взаимодействует с module ownership из PC-MOD-001 без дублирования catalog vs runtime binding.

## 5. Различие Cabinet History и Personnel History

§9 разделяет **историю кабинета** (деятельность в рамках должности) и **кадровую историю сотрудника**.

Вопросы:

- где хранится и кто владеет каждым типом history;
- как пользователь видит оба контура в едином UI без смешения semantics;
- нужны ли отдельные registers / ADR для lifecycle и retention каждой истории.

## 6. Связь с PC-MOD-001

PC-CONCEPT-001 задаёт концепцию двух контуров (Рабочий контур / Self Services). [PC-MOD-001](../access/PC-MOD-001-position-cabinet-functional-composition.md) описывает functional module catalog (T1/T2/T3).

Вопросы:

- как каждый модуль PC-MOD-001 мапится на Рабочий контур vs Self Services;
- не противоречит ли tier-модель PC-MOD-001 формулировке «Position Cabinet не кабинет должности и не кабинет сотрудника»;
- какой документ является source of truth для границ «in cabinet / out of cabinet» при расхождении формулировок.

## 7. Будущая роль Self Services

§10 перечисляет потенциальные Self Services-модули (профиль, отпуска, образование, HR-запросы и т.д.).

Вопросы:

- Self Services — permanent tier внутри Position Cabinet или отдельный product contour;
- какие модули уже реализованы (например, `/education`, `/profile`) и под каким ownership их закрепить;
- нужен ли отдельный work package / ADR перед расширением Self Services beyond stub sections;
- как Self Services coexists с HR operational contour («Кадровые процессы») для ролей с administrative access.

---

## Следующий шаг (не решение)

Провести architecture review session с опорой на ARCH-001, ACCESS-001, ADR-050, ADR-051, PC-MOD-001 и зафиксировать ответы либо как amendments к PC-CONCEPT-001, либо как отдельные normative documents.
