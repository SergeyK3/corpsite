# PO-EDIT-003 — Personnel Order Editorial UI (Kazakh-first)

**Status:** Implemented (UI only; uses EDIT-002 API)

**Kazakh-first** means: the user works with Kazakh (`kk`) text first in the editor.
It does **not** mean Russian text is absent from editorial persistence.
Generate creates both required locales (`kk` and `ru`); the UI shows and edits only `kk`.

## UX

Section **«Текст приказа»** in the order detail drawer:

- Working document language in UI: **Қазақша (`kk`)** only
- Russian (`ru`) blocks are generated/stored but hidden in this WP
- Interface chrome (buttons, labels, messages) stays in Russian
- Заголовок / Преамбула / Пункт №N (ФИО) → Текст пункта + Основание / Заключительная часть
- Plain multiline textarea (no HTML/Markdown/rich text)
- Human statuses: `Generated` | `Edited` | `Requires review`
- Actions: Редактировать · Сохранить · Вернуть автоматически сгенерированный текст · Сформировать / обновить текст
- Manual generate asks for confirmation (neutral wording; no UI claim about override retention)
- Technical fields (block_type, fingerprint, generator_*, revision) are not shown
- Editable only in `DRAFT`; other statuses are read-only
- Hint: «Редактирование казахского текста приказа. Русский язык будет доступен на следующем этапе.»

## API usage (existing)

- `GET …/editorial` — load
- `POST …/editorial/generate` (no locale filter) — auto on first open if no `kk` UI blocks; creates/updates **both** `kk` and `ru`; manual regenerate after confirm
- `PATCH …/editorial/blocks/{id}` — save override + `expected_revision`
- `POST …/editorial/blocks/{id}/reset-to-generated` — clear override

**READY gate:** unchanged (EDIT-002). Still requires effective blocks for both `kk` and `ru`. Full generate keeps READY reachable without changing the gate.

## Files

- `corpsite-ui/.../PersonnelOrderEditorialTextEditor.tsx`
- `corpsite-ui/.../personnelOrderEditorialUi.ts` (`PERSONNEL_ORDER_EDITORIAL_UI_LOCALE = "kk"`)
- API client methods in `personnelOrdersApi.client.ts`
- Wired in `PersonnelOrderDetailDrawer.tsx` (replaces legacy localized-texts placeholder)

## Screenshots

`docs/personnel-orders/implementation/screenshots-edit-003/`

## Future work

Separate architectural question (not implemented in this WP):

> What counts as an editorially ready document?

Points to decide in a later WP:

- Automatic generation ≠ editorial review by HR
- Presence of a stored block ≠ confirmation by a кадровик
- The user may never open the Russian text while Kazakh-first UX is in effect
- Future product may need explicit confirmation per locale
- Possible statuses such as Review Pending / Reviewed, or a dedicated editorial-approval workflow

This is a future architectural decision / WP. Do not implement here.
