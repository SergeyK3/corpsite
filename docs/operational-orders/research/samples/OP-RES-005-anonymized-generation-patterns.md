# OP-RES-005 — Анонимизированные паттерны генерации

Иллюстративные шаблоны clause rendering без ФИО и без привязки к конкретным документам.  
Источник: корпус 183 DOCX + OP-RES-004 execution patterns.

---

## 1. Базовая анатомия пункта (RU)

```text
[номер]. [ACTION] [PARTY_dative] [MANAGED_OBJECT] [CONDITIONS] [DEADLINE] [EXPECTED_RESULT].
```

**Порядок по корпусу (183 DOCX, 1 855 пунктов):**

| Порядок | Item hits | Доля |
|---|---:|---:|
| action_first (глагол → адресат) | 207 | ~11% явных |
| party_first (дательный → глагол) | 37 | ~2% |
| kk_mandate (жүктелсін / тағайындалсын) | 162 | ~9% |

**Вывод:** в русском тексте доминирует **action → party**; в казахском блоке — **mandate suffix pattern**. Оба порядка должны поддерживаться renderer'ом, не одним шаблоном.

---

## 2. Party rendering (role-first)

| Semantic | RU pattern | KK pattern (corpus-limited) |
|---|---|---|
| PositionRole | «Заведующему [отделение]» | «[Бөлім] меңгерушісіне» |
| NamedPerson | «[Инициалы] [Фамилия]» (дательный) | «[А.А.] [Тегі]» |
| OrganizationalUnit | «[Отдел/Служба]» (им. или дат.) | «[Бөлім/Қызмет]» |
| Signatory self-control | «Контроль … оставляю за собой» | «Бақылауды өзіме қалдырамын» |

**Role-first:** в смысловой модели хранится `PositionRole`; `NamedPerson` — опциональное разрешение на дату документа.

---

## 3. Deadline rendering

| Model | RU example | Formalizable | Manual review |
|---|---|---|---|
| exact_date | «до 15 марта 2026 года» | High | Rare |
| period_range | «с 11 по 13 марта 2026 года» | High | Rare |
| within_duration | «в течение 3 (трёх) рабочих дней» | High | Sometimes |
| from_signature | «со дня подписания настоящего приказа» | High | Rare |
| from_acknowledgement | «со дня ознакомления» | Medium | Sometimes |
| until_event | «по окончании [мероприятия]» | Medium | **Often** |
| after_event | «после [события]» | Medium | **Often** |
| period | «за апрель 2026 года» | High | Rare |
| recurring | «ежемесячно» | High | Rare |
| permanent | «на постоянной основе» | Low | **Often** |
| as_needed | «по мере необходимости» | Low | **Always** |
| immediately | «незамедлительно» | Medium | Sometimes |
| attachment_defined | «согласно приложению 1» | Medium | When attachment vague |
| external_document_defined | «в сроки установленные [документ]» | Low | **Always** |
| unspecified | (отсутствует) | N/A | Default for ongoing duties |

---

## 4. Expected Result patterns

| Pattern | RU clause fragment | Auto-derived from intent? |
|---|---|---|
| travel_done | (implicit) | Yes — from DIRECT |
| commission_constituted | (implicit after CREATE_BODY) | Yes |
| service_organized | «обеспечить работу в режиме …» | Yes — from ORGANIZE/ENSURE |
| act_done | «оформить акт по результатам» | Partial — scenario S_ACCOUNTING |
| report_submitted | «представить отчёт / авансовый отчёт» | No — explicit item preferred |
| ack_completed | «ознакомить с настоящим приказом» | No — separate ACKNOWLEDGE item |
| regime_maintained | (implicit) | Yes — from ESTABLISH/ENSURE |

**Правило:** не добавлять expected result автоматически, если это создаёт новое обязательство.

---

## 5. Control meta-item patterns

| Mode | RU | Controller |
|---|---|---|
| delegated_order | «Контроль за исполнением настоящего приказа возложить на [должность].» | PositionRole |
| self | «Контроль за исполнением настоящего приказа оставляю за собой.» | Signatory |
| embedded | «[Должность] взять на контроль [объект].» | PositionRole — separate item |
| kk_delegated | «Бұйрықтың орындалуын бақылау [лауазым] жүктелсін.» | PositionRole |

**Placement:** final or penultimate item in 156/183 docs.

---

## 6. Manual override states (conceptual)

| State | Meaning |
|---|---|
| GENERATED | Text from clause renderer |
| MANUALLY_EDITED | User override on block |
| REGENERATED | New generated snapshot; override preserved as stale |
| LOCKED | Post-approval; no auto-regeneration |

**Levels:** document / locale / item / obligation / preamble / control — aligned with PO-EDIT-001 block model.
