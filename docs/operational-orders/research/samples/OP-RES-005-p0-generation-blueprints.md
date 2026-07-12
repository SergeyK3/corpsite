# OP-RES-005 — P0 Generation Blueprints

Анонимизированные generation blueprints для четырёх P0-сценариев (~59% корпуса). Без ФИО.

---

## Blueprint 1 — S_TRAVEL (33 docs, 17.1%)

### Input parameters

| Field | Required | Source |
|---|---|---|
| scenario_code=S_TRAVEL | Yes | Selection |
| traveler(s), destination, purpose | Yes | Manual |
| travel_period | Yes | period_range |
| funding_source | Conditional | Manual |
| controller | Default director_self | Scenario |
| basis_application | Conditional | Trailing basis |
| language_mode | Yes | ru / bilingual |

### Items (mandatory)

| Seq | Kind | Party | Deadline |
|---|---|---|---|
| 1 | DIRECT | HR/unit head | period_range |
| 2 | FUND | — | — |
| 3 | ENSURE (salary) | — | period |
| 4 | CONTROL | Signatory | — |
| 5 | META_EFFECT | — | from_signature |

### RU skeleton

```text
ПРИКАЗЫВАЮ:
1. Направить [должность, инициалы] в [город] с [дата] по [дата] для [цель].
2. Расходы по командировке оплатить за счёт [источник].
3. Сохранить место работы и средний заработок на период командировки.
4. Контроль за исполнением оставляю за собой.
5. Приказ вступает в силу со дня подписания.
Основание: заявление [должность, инициалы].
```

### KK skeleton (partial)

```text
БҰЙЫРАМЫН:
1. [Лауазым, А.А.] [қала] [күннен] [күнге дейін] [жіберілсін].
2. Шығын [көз] есебінен өтелсін.
3. Орын табы мен орташа жалақы сақталсын.
4. Бақылауды өзіме қалдырамын.
5. Бұйрық кол қойылған күннен бастап күшіне енеді.
Негіздеме: [өтініш].
```

### Validation: V001–V007, V012–V016

---

## Blueprint 2 — S_COMMISSION (28 docs, 14.5%)

### Input parameters

commission_subject, chair, members[], secretary (optional), roster inline/attachment, controller=chief_accountant, legal_basis[].

### Items

| Seq | Kind |
|---|---|
| 1 | CREATE_BODY + DEFINE_COMPOSITION |
| 2 | CONTROL |

### RU skeleton

```text
ПРИКАЗЫВАЮ:
1. Создать комиссию по [предмет].
   Председатель: [должность] – [инициалы].
   Члены: [список].
2. Контроль возложить на [главного бухгалтера].
```

### Validation: V008, V007, V012

---

## Blueprint 3 — S_CLINICAL (35 docs, 18.1%)

### Input parameters

event_or_regime, target_units[] (1..N), event_date, controller=deputy_clinical.

### Items

Parallel ORGANIZE/ENSURE per unit → CONTROL → META_EFFECT.

### RU skeleton

```text
ПРИКАЗЫВАЮ:
1. Заведующему [отделение X] обеспечить [действие] [дата].
2. Заведующему [отделение Y] организовать [действие] [дата].
N. Контроль возложить на [зам. директора по лечебной работе].
N+1. Приказ вступает в силу со дня подписания.
```

KK: insufficient templates — manual review.

---

## Blueprint 4 — S_ACCOUNTING (18 docs, 9.3%)

### Input parameters

accounting_action, commission composition, controller=chief_accountant, act/report conditional.

### Items

CREATE_BODY or APPROVE → optional REPORT → CONTROL.

### RU skeleton

```text
ПРИКАЗЫВАЮ:
1. Создать комиссию по [предмет] в составе: …
2. Комиссии провести [инвентаризацию] и оформить акт [срок].
3. Контроль возложить на [главного бухгалтера].
```

---

## Cross-blueprint invariants

- Entry via scenario (not arbitrary items)
- Unit: Order Item → Execution Obligation(s)
- Control: auto-suggested meta-item, editable
- Party: role-first
- Shared with Personnel Orders: document shell, editorial override, independent RU/KK render
