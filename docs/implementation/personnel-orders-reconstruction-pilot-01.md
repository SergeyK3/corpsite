# Personnel orders reconstruction pilot 01

Local-only draft reconstruction. No employee events or assignments were created or changed.

Source: `D:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Журнал кадровых приказов\Ручное распознавание журналов.xlsx` · sheet `Лист1`.

## Imported drafts

| Excel row | Order | Date | template_key | order_id | DOCX | Visual check |
|---:|---|---|---|---:|---|---|
| 113 | 1262-ж | 2026-07-22 | personnel.termination.employee-initiative-unused-leave | 4826 | not found | /directory/personnel/orders?order_id=4826 |
| 125 | 1273-ж | 2026-07-23 | personnel.termination.employee-initiative-unused-leave | 4827 | not found | /directory/personnel/orders?order_id=4827 |
| 134 | 1282-ж | 2026-07-27 | personnel.transfer.permanent | 4828 | not found | /directory/personnel/orders?order_id=4828 |
| 148 | 1296-ж | 2026-08-03 | personnel.transfer.permanent | 4829 | not found | /directory/personnel/orders?order_id=4829 |
| 183 | 1329-ж | 2026-08-07 | personnel.termination.employee-initiative-unused-leave | 4830 | not found | /directory/personnel/orders?order_id=4830 |
| 190 | 1336-ж | 2026-08-10 | personnel.transfer.permanent | 4831 | not found | /directory/personnel/orders?order_id=4831 |
| 240 | 7-ж | 2026-01-05 | personnel.hire.standard | 4832 | found | /directory/personnel/orders?order_id=4832 |
| 241 | 8-ж | 2026-01-05 | personnel.hire.standard | 4833 | found | /directory/personnel/orders?order_id=4833 |
| 264 | 27-ж | 2026-01-08 | personnel.hire.standard | 4834 | found | /directory/personnel/orders?order_id=4834 |
| 282 | 43-ж | 2026-01-14 | personnel.transfer.permanent | 4835 | found | /directory/personnel/orders?order_id=4835 |
| 284 | 45-ж | 2026-01-14 | personnel.concurrent-duty.start | 4836 | found | /directory/personnel/orders?order_id=4836 |
| 315 | 71-ж | 2026-01-22 | personnel.transfer.permanent | 4837 | found | /directory/personnel/orders?order_id=4837 |
| 327 | 83-У-ж | 2026-01-26 | personnel.termination.employee-initiative-unused-leave | 4838 | not found | /directory/personnel/orders?order_id=4838 |
| 396 | 149-ж | 2026-02-09 | personnel.termination.employee-initiative-unused-leave | 4839 | found | /directory/personnel/orders?order_id=4839 |
| 418 | 170-ж | 2026-02-12 | personnel.termination.employee-initiative-unused-leave | 4840 | not found | /directory/personnel/orders?order_id=4840 |
| 423 | 174-ж | 2026-02-13 | personnel.concurrent-duty.start | 4841 | not found | /directory/personnel/orders?order_id=4841 |
| 438 | 186-ж | 2026-02-17 | personnel.concurrent-duty.start | 4842 | not found | /directory/personnel/orders?order_id=4842 |
| 463 | 210-ж | 2026-02-25 | personnel.hire.standard | 4843 | not found | /directory/personnel/orders?order_id=4843 |
| 478 | 222-ж | 2026-03-02 | personnel.hire.standard | 4844 | found | /directory/personnel/orders?order_id=4844 |
| 491 | 235-ж | 2026-03-02 | personnel.concurrent-duty.start | 4845 | not found | /directory/personnel/orders?order_id=4845 |

## Template resolution

- No pilot order is without an approved template.

## Matching and assumptions

- Matched people: 15 automatic, 5 ambiguous (their source FIO is retained without employee_id); no unresolved people were imported.
- employee_id is written only for an unambiguous surname-and-initials match; ambiguous matches retain source FIO in the item payload.
- The database has no historical assignment table. Current primary employee position/unit was copied when available and is marked `CURRENT_PRIMARY_ASSIGNMENT_USED_NO_HISTORICAL_ASSIGNMENT`.
- Effective date defaults to order date; rate defaults to 1.0; basis defaults to the bilingual personal application.
- The current default signatory is filled only when all signatory fields of a pilot draft are empty; the storage assumption is `CURRENT_DEFAULT_SIGNATORY_USED`.

## Bilingual template corrections

- Approved titles are selected by action type, including `О переводе` (not `О постоянном переводе`); see `personnel-order-titles-bilingual-dictionary.md`.
- The general renderer maps `медсестра` and `медицинская сестра` to `мейіргер` before rendering Kazakh. Proposed pilot position/unit values are listed in the existing bilingual dictionaries.
- Template limitations: the generic wording remains a reconstruction and must be checked against DOCX; no native imported text or editorial overrides are overwritten.

## Russian automatic wording

- If unused leave days are not confirmed, the accounting point is: `Бухгалтерии произвести расчёт за неиспользованные дни отпуска.` No dash, number, or `календарных дней` is rendered.
- In automated Russian hire, transfer, and concurrent-duty points, the target is rendered as `должность (подразделение)` and a confirmed source FIO is retained without declension. The added order-text dictionary form is `Приемное` → `приемное отделение` (PROPOSED).
- An unknown unit is only normalized to lower case in parentheses and remains subject to dictionary review; Kazakh wording, native imported text, and editorial overrides are not changed.

## Skipped rows

- Excel row 7: UNRESOLVABLE_SURNAME.
- Excel row 8: UNRESOLVABLE_SURNAME.
- Excel row 9: UNRESOLVABLE_SURNAME.
- Excel row 10: MISSING_OR_INVALID_2026_DATE.
- Excel row 11: MISSING_OR_INVALID_2026_DATE.
- Excel row 17: UNRESOLVABLE_SURNAME.
- Excel row 20: UNRESOLVABLE_SURNAME.
- Excel row 21: UNRESOLVABLE_SURNAME.
- Excel row 24: UNRESOLVABLE_SURNAME.
- Excel row 25: UNRESOLVABLE_SURNAME.
- Excel row 30: UNRESOLVABLE_SURNAME.
- Excel row 31: UNRESOLVABLE_SURNAME.
- Excel row 32: UNRESOLVABLE_SURNAME.
- Excel row 34: UNRESOLVABLE_SURNAME.
- Excel row 36: UNRESOLVABLE_SURNAME.
- Excel row 39: UNRESOLVABLE_SURNAME.
- Excel row 46: UNRESOLVABLE_SURNAME.
- Excel row 47: UNRESOLVABLE_SURNAME.
- Excel row 48: UNRESOLVABLE_SURNAME.
- Excel row 49: UNRESOLVABLE_SURNAME.
- Excel row 50: UNRESOLVABLE_SURNAME.
- Excel row 51: UNRESOLVABLE_SURNAME.
- Excel row 52: UNRESOLVABLE_SURNAME.
- Excel row 53: UNRESOLVABLE_SURNAME.
- Excel row 54: UNRESOLVABLE_SURNAME.
- Excel row 55: UNRESOLVABLE_SURNAME.
- Excel row 56: UNRESOLVABLE_SURNAME.
- Excel row 64: UNRESOLVABLE_SURNAME.
- Excel row 65: UNRESOLVABLE_SURNAME.
- Excel row 66: UNRESOLVABLE_SURNAME.
- Excel row 67: UNRESOLVABLE_SURNAME.
- Excel row 68: UNRESOLVABLE_SURNAME.
- Excel row 69: UNRESOLVABLE_SURNAME.
- Excel row 72: UNRESOLVABLE_SURNAME.
- Excel row 73: UNRESOLVABLE_SURNAME.
- Excel row 75: UNRESOLVABLE_SURNAME.
- Excel row 77: UNRESOLVABLE_SURNAME.
- Excel row 78: UNRESOLVABLE_SURNAME.
- Excel row 80: UNRESOLVABLE_SURNAME.
- Excel row 83: UNRESOLVABLE_SURNAME.
- Excel row 84: UNRESOLVABLE_SURNAME.
- Excel row 85: UNRESOLVABLE_SURNAME.
- Excel row 86: UNRESOLVABLE_SURNAME.
- Excel row 89: UNRESOLVABLE_SURNAME.
- Excel row 91: UNRESOLVABLE_SURNAME.
- Excel row 93: UNRESOLVABLE_SURNAME.
- Excel row 94: UNRESOLVABLE_SURNAME.
- Excel row 97: UNRESOLVABLE_SURNAME.
- Excel row 98: UNRESOLVABLE_SURNAME.
- Excel row 99: UNRESOLVABLE_SURNAME.
- Excel row 101: UNRESOLVABLE_SURNAME.
- Excel row 102: UNRESOLVABLE_SURNAME.
- Excel row 103: UNRESOLVABLE_SURNAME.
- Excel row 104: UNRESOLVABLE_SURNAME.
- Excel row 105: UNRESOLVABLE_SURNAME.
- Excel row 106: UNRESOLVABLE_SURNAME.
- Excel row 110: UNRESOLVABLE_SURNAME.
- Excel row 114: UNRESOLVABLE_SURNAME.
- Excel row 116: UNRESOLVABLE_SURNAME.
- Excel row 118: UNRESOLVABLE_SURNAME.
- Excel row 119: UNRESOLVABLE_SURNAME.
- Excel row 120: UNRESOLVABLE_SURNAME.
- Excel row 121: UNRESOLVABLE_SURNAME.
- Excel row 122: UNRESOLVABLE_SURNAME.
- Excel row 130: UNRESOLVABLE_SURNAME.
- Excel row 131: UNRESOLVABLE_SURNAME.
- Excel row 132: UNRESOLVABLE_SURNAME.
- Excel row 137: UNRESOLVABLE_SURNAME.
- Excel row 142: UNRESOLVABLE_SURNAME.
- Excel row 143: UNRESOLVABLE_SURNAME.
- Excel row 145: UNRESOLVABLE_SURNAME.
- Excel row 146: UNRESOLVABLE_SURNAME.
- Excel row 147: UNRESOLVABLE_SURNAME.
- Excel row 150: UNRESOLVABLE_SURNAME.
- Excel row 151: UNRESOLVABLE_SURNAME.
- Excel row 152: UNRESOLVABLE_SURNAME.
- Excel row 153: UNRESOLVABLE_SURNAME.
- Excel row 155: UNRESOLVABLE_SURNAME.
- Excel row 156: UNRESOLVABLE_SURNAME.
- Excel row 163: UNRESOLVABLE_SURNAME.
- Excel row 171: UNRESOLVABLE_SURNAME.
- Excel row 172: UNRESOLVABLE_SURNAME.
- Excel row 173: UNRESOLVABLE_SURNAME.
- Excel row 175: UNRESOLVABLE_SURNAME.
- Excel row 176: UNRESOLVABLE_SURNAME.
- Excel row 177: UNRESOLVABLE_SURNAME.
- Excel row 178: UNRESOLVABLE_SURNAME.
- Excel row 179: UNRESOLVABLE_SURNAME.
- Excel row 182: UNRESOLVABLE_SURNAME.
- Excel row 188: UNRESOLVABLE_SURNAME.
- Excel row 196: UNRESOLVABLE_SURNAME.
- Excel row 197: UNRESOLVABLE_SURNAME.
- Excel row 198: UNRESOLVABLE_SURNAME.
- Excel row 202: UNRESOLVABLE_SURNAME.
- Excel row 203: UNRESOLVABLE_SURNAME.
- Excel row 207: UNRESOLVABLE_SURNAME.
- Excel row 208: UNRESOLVABLE_SURNAME.
- Excel row 209: UNRESOLVABLE_SURNAME.
- Excel row 211: UNRESOLVABLE_SURNAME.
- Excel row 212: UNRESOLVABLE_SURNAME.
- Excel row 213: UNRESOLVABLE_SURNAME.
- Excel row 214: UNRESOLVABLE_SURNAME.
- Excel row 216: UNRESOLVABLE_SURNAME.
- Excel row 217: UNRESOLVABLE_SURNAME.
- Excel row 219: UNRESOLVABLE_SURNAME.
- Excel row 224: UNRESOLVABLE_SURNAME.
- Excel row 225: UNRESOLVABLE_SURNAME.
- Excel row 226: UNRESOLVABLE_SURNAME.
- Excel row 227: UNRESOLVABLE_SURNAME.
- Excel row 228: UNRESOLVABLE_SURNAME.
- Excel row 229: UNRESOLVABLE_SURNAME.
- Excel row 234: UNRESOLVABLE_SURNAME.
- Excel row 235: UNRESOLVABLE_SURNAME.
- Excel row 236: UNRESOLVABLE_SURNAME.
- Excel row 237: UNRESOLVABLE_SURNAME.
- Excel row 239: UNRESOLVABLE_SURNAME.
- Excel row 242: UNRESOLVABLE_SURNAME.
- Excel row 243: UNRESOLVABLE_SURNAME.
- Excel row 246: UNRESOLVABLE_SURNAME.
- Excel row 252: UNRESOLVABLE_SURNAME.
- Excel row 254: UNRESOLVABLE_SURNAME.
- Excel row 258: UNRESOLVABLE_SURNAME.
- Excel row 259: UNRESOLVABLE_SURNAME.
- Excel row 261: UNRESOLVABLE_SURNAME.
- Excel row 265: UNRESOLVABLE_SURNAME.
- Excel row 272: UNRESOLVABLE_SURNAME.
- Excel row 276: UNRESOLVABLE_SURNAME.
- Excel row 280: UNRESOLVABLE_SURNAME.
- Excel row 287: UNRESOLVABLE_SURNAME.
- Excel row 288: UNRESOLVABLE_SURNAME.
- Excel row 289: UNRESOLVABLE_SURNAME.
- Excel row 290: UNRESOLVABLE_SURNAME.
- Excel row 291: UNRESOLVABLE_SURNAME.
- Excel row 293: UNRESOLVABLE_SURNAME.
- Excel row 294: UNRESOLVABLE_SURNAME.
- Excel row 297: UNRESOLVABLE_SURNAME.
- Excel row 298: UNRESOLVABLE_SURNAME.
- Excel row 300: UNRESOLVABLE_SURNAME.
- Excel row 302: UNRESOLVABLE_SURNAME.
- Excel row 303: UNRESOLVABLE_SURNAME.
- Excel row 304: UNRESOLVABLE_SURNAME.
- Excel row 306: UNRESOLVABLE_SURNAME.
- Excel row 307: UNRESOLVABLE_SURNAME.
- Excel row 308: UNRESOLVABLE_SURNAME.
- Excel row 314: UNRESOLVABLE_SURNAME.
- Excel row 321: UNRESOLVABLE_SURNAME.
- Excel row 322: UNRESOLVABLE_SURNAME.
- Excel row 330: UNRESOLVABLE_SURNAME.
- Excel row 331: UNRESOLVABLE_SURNAME.
- Excel row 332: UNRESOLVABLE_SURNAME.
- Excel row 335: UNRESOLVABLE_SURNAME.
- Excel row 336: UNRESOLVABLE_SURNAME.
- Excel row 337: UNRESOLVABLE_SURNAME.
- Excel row 338: UNRESOLVABLE_SURNAME.
- Excel row 340: UNRESOLVABLE_SURNAME.
- Excel row 341: UNRESOLVABLE_SURNAME.
- Excel row 343: UNRESOLVABLE_SURNAME.
- Excel row 344: UNRESOLVABLE_SURNAME.
- Excel row 346: UNRESOLVABLE_SURNAME.
- Excel row 347: UNRESOLVABLE_SURNAME.
- Excel row 352: UNRESOLVABLE_SURNAME.
- Excel row 355: UNRESOLVABLE_SURNAME.
- Excel row 356: UNRESOLVABLE_SURNAME.
- Excel row 359: UNRESOLVABLE_SURNAME.
- Excel row 360: UNRESOLVABLE_SURNAME.
- Excel row 361: UNRESOLVABLE_SURNAME.
- Excel row 364: UNRESOLVABLE_SURNAME.
- Excel row 365: UNRESOLVABLE_SURNAME.
- Excel row 366: UNRESOLVABLE_SURNAME.
- Excel row 367: UNRESOLVABLE_SURNAME.
- Excel row 368: UNRESOLVABLE_SURNAME.
- Excel row 372: UNRESOLVABLE_SURNAME.
- Excel row 377: UNRESOLVABLE_SURNAME.
- Excel row 380: UNRESOLVABLE_SURNAME.
- Excel row 384: UNRESOLVABLE_SURNAME.
- Excel row 392: UNRESOLVABLE_SURNAME.
- Excel row 393: UNRESOLVABLE_SURNAME.
- Excel row 397: UNRESOLVABLE_SURNAME.
- Excel row 398: UNRESOLVABLE_SURNAME.
- Excel row 407: UNRESOLVABLE_SURNAME.
- Excel row 409: UNRESOLVABLE_SURNAME.
- Excel row 410: UNRESOLVABLE_SURNAME.
- Excel row 411: UNRESOLVABLE_SURNAME.
- Excel row 424: UNRESOLVABLE_SURNAME.
- Excel row 425: UNRESOLVABLE_SURNAME.
- Excel row 429: UNRESOLVABLE_SURNAME.
- Excel row 430: UNRESOLVABLE_SURNAME.
- Excel row 432: UNRESOLVABLE_SURNAME.
- Excel row 433: UNRESOLVABLE_SURNAME.
- Excel row 434: UNRESOLVABLE_SURNAME.
- Excel row 440: UNRESOLVABLE_SURNAME.
- Excel row 441: UNRESOLVABLE_SURNAME.
- Excel row 443: UNRESOLVABLE_SURNAME.
- Excel row 446: UNRESOLVABLE_SURNAME.
- Excel row 447: UNRESOLVABLE_SURNAME.
- Excel row 449: UNRESOLVABLE_SURNAME.
- Excel row 450: UNRESOLVABLE_SURNAME.
- Excel row 452: UNRESOLVABLE_SURNAME.
- Excel row 453: UNRESOLVABLE_SURNAME.
- Excel row 458: UNRESOLVABLE_SURNAME.
- Excel row 459: UNRESOLVABLE_SURNAME.
- Excel row 460: UNRESOLVABLE_SURNAME.
- Excel row 465: UNRESOLVABLE_SURNAME.
- Excel row 470: UNRESOLVABLE_SURNAME.
- Excel row 472: UNRESOLVABLE_SURNAME.
- Excel row 473: UNRESOLVABLE_SURNAME.
- Excel row 474: UNRESOLVABLE_SURNAME.
- Excel row 476: UNRESOLVABLE_SURNAME.
- Excel row 479: UNRESOLVABLE_SURNAME.
- Excel row 481: UNRESOLVABLE_SURNAME.
- Excel row 482: UNRESOLVABLE_SURNAME.
- Excel row 485: UNRESOLVABLE_SURNAME.
