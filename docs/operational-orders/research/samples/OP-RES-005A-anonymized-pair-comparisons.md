# OP-RES-005A — Анонимизированные сравнения языковых версий

Иллюстративные паттерны без ФИО. Pair IDs ссылаются на anonymized doc_id из probe.

---

## Pattern A — Intra-document: RU block then KK block (probable RU-first layout)

**Pair type:** `intra_document_bilingual` · **Layout:** `bilingual_kk_after_ru`  
**Corpus frequency:** 75 / 183 DOCX  
**Relation:** `direct_translation` (85 docs corpus-wide)

```text
[RU SECTION]
ПРИКАЗЫВАЮ:
1. Направить [должность, инициалы] в [город] [даты] для [цель].
2. Расходы за счёт [источник].
3. Сохранить место работы и средний заработок.
4. Контроль оставляю за собой.

[KK SECTION — follows RU]
БҰЙЫРАМЫН:
1. [Лауазым, А.А.] [қала] [күндер] [мақсат] [жіберілсін].
2. [Шығын] [көз] есебінен өтелсін.
3. [Орын табы] мен [орташа жалақы] сақталсын.
4. [Бақылауды] өзіме қалдырамын.
```

**Observations:**

- Same item count (4+4)
- Same numeric dates and amounts (when present)
- KK follows RU in document order
- **Interpretation:** consistent with RU-first drafting or RU-first template; **not** proof of separate-file workflow

---

## Pattern B — Intra-document: KK block before RU block

**Layout:** `bilingual_ru_after_kk` · **Frequency:** 54 / 183 DOCX

```text
[KK SECTION first]
БҰЙЫРАМЫН:
1. [Комиссия] құру …
2. [Бақылау] [лауазым] жүктелсін.

[RU SECTION second]
ПРИКАЗЫВАЮ:
1. Создать комиссию …
2. Контроль возложить на [должность].
```

**Interpretation:** template variant or KK-first boilerplate in specific folders (e.g. АХЧ); mixed practice — weakens strict RU-first universal claim

---

## Pattern C — Partial translation (semantic drift)

**Relation:** `partial_translation` · **Frequency:** 12 intra-document cases

| Signal | RU | KK |
|---|---|---|
| Item count | 6 | 6 |
| Control clause | «Контроль возложить на [должность]» | absent or merged |
| Attachment ref | «Приложение 1» | «1-қосымша» missing |

**Drift score:** 0.15–0.35 (item ratio match but control/evidence mismatch)

**Risk:** bilingual package appears complete but KK omits control or evidence language

---

## Pattern D — Abbreviated or expanded KK

**Relation:** `abbreviated_or_expanded` · **Frequency:** 33 cases

```text
RU: 12 numbered items (parallel unit directives)
KK: 8 numbered items (summary mandate forms)
```

**Interpretation:** adapted edition, not line-by-line translation; **human reconciliation required**

---

## Pattern E — RU-only document (no KK block)

**Layout:** `ru_only_content` · **Frequency:** 4 / 183 DOCX

- Domains: mixed (accounting, clinical tail)
- **No KK section detected** in same file
- **Does not prove** KK was never produced — may exist as unarchived separate artifact

---

## Pattern F — KK-primary single-language content

**Layout:** `kk_only_content` · **Frequency:** 41 / 183 DOCX

- Filename often Kazakh or mixed
- No «ПРИКАЗЫВАЮ» block detected
- May be KK working draft without RU mirror in same artifact

---

## Pattern G — Separate-file translation pair

**Corpus result:** **0 true cross-file translation candidates** after refined filtering

Automated scoring produced 64 «high» separate-file pairs; manual refinement rejected all — both files were already intra-document bilingual or unrelated template siblings.

**Known revision sibling (not language pair):**

- Same normalized stem, identical content hash — accounting policy document variants (OP-RES-001)

---

## Pattern H — Version marker without language split

Filename markers: `(1)`, `(5)`, `копия`, `испр.`

- Indicate **document revision**, not RU/KK language pairing
- 16 probable bilingual revision siblings in same scenario

---

## Staleness illustration (conceptual)

```text
T0: RU effective text approved internally
T1: KK translated from RU snapshot
T2: RU item 2 amount changed manually
T3: KK still reflects T1 → language_version_staleness = STALE / REVIEW_REQUIRED
```

No corpus file proves T2→T3 sequence; inferred from version markers and partial_translation patterns.
