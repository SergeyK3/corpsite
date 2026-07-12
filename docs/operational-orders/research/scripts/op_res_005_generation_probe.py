#!/usr/bin/env python3
"""
OP-RES-005 — read-only generation pattern probe.
Extracts verb stems, clause component order, preamble patterns, item counts per scenario.
Writes anonymized aggregates only to docs/operational-orders/research/data/.
Does not modify source documents. No PII in output.
"""

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(r"d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы")
TAX = Path(__file__).resolve().parents[1] / "data" / "OP-RES-003-order-taxonomy-summary.csv"
OUT = Path(__file__).resolve().parents[1] / "data" / "OP-RES-005-corpus-probe-stats.txt"

ITEM_RE = re.compile(r"^(\d+(?:\.\d+)*)([\.)])\s*(.+)", re.S)

VERB_STEMS = {
    "DIRECT": r"^(?:Направить|Жібер|Направля)",
    "ASSIGN": r"^(?:Назначить|Тағайында|Назначить ответственн)",
    "APPROVE": r"^(?:Утвердить|Бекіт|Утвердить состав|Утвердить положение)",
    "CREATE_COMMISSION": r"^(?:Создать|Құру).*комисси",
    "DEFINE_COMPOSITION": r"(?:Председатель|Члены комиссии|Төраға|Мүшелері)",
    "AUTHORIZE": r"^(?:Разрешить|Запретить|Рұқсат|Тыйым)",
    "ORGANIZE": r"^(?:Организовать|Ұйымдастыр)",
    "ENSURE": r"^(?:Обеспечить|Қамтамасыз|Обеспечивать)",
    "SUBMIT_REPORT": r"(?:представить|предоставить|ұсын).*(?:отчет|отчёт|акт|документ|информац)",
    "PROVIDE_INFORMATION": r"(?:довести до сведения|предоставить информац)",
    "FUND": r"(?:Расходы|за счёт|перечисл|выделить|денежн)",
    "ACKNOWLEDGE": r"(?:ознакомить|таныстыр|Ознакомить)",
    "AMEND": r"(?:внести изменения|изложить в новой редакции)",
    "REPEAL": r"(?:признать утратившим|күшін жою|отменить)",
    "CONTROL": r"(?:Контроль|Бақылау|оставляю за собой|возложить.*контрол)",
    "ESTABLISH": r"^(?:Установить|Ввести|Енгізу|Установить порядок)",
    "DELEGATE": r"^(?:Возложить|Жүкте)",
    "EFFECTIVE": r"(?:вступает в силу|күшіне енеді)",
}

CLAUSE_ORDER = {
    "action_first": r"^(?:Направить|Создать|Утвердить|Обеспечить|Организовать|Назначить|Возложить|Контроль|Провести|Установить|Ввести|Разрешить|Запретить|Перечисл)",
    "party_first": r"^(?:Заведующему|Руководителю|Директору|Отделу|Службе|Начальнику|Главному|Исполняющему|Ответственному)",
    "kk_mandate": r"(?:жүктелсін|тағайындалсын|бекітілсін)",
}

PREAMBLE_PATTERNS = {
    "legal_chain": r"(?:В соответствии|Согласно|Закон|Кодекс|Норматив)",
    "purpose": r"(?:В целях|Мақсатында|в связи с)",
    "memo": r"(?:служебн|жұмыс|записк)",
    "application": r"(?:заявлен|өтініш)",
    "protocol": r"(?:протокол|хаттама)",
    "production_need": r"(?:производственн|қажеттілік|необходимост)",
    "external_order": r"(?:приказ.*министр|ведомств)",
    "no_formal_basis": r"^ПРИКАЗЫВАЮ|^БҰЙЫРАМЫН",
}

DEADLINE_RENDER = {
    "exact_date": r"\d{1,2}[\.\-]\d{1,2}[\.\-]\d{2,4}",
    "period_range": r"\d{1,2}\s*[-–]\s*\d{1,2}",
    "within_duration": r"в течение\s+\d|ішінде\s+\d",
    "from_signature": r"(?:со дня|күннен бастап).*(?:подписан|қол қой)",
    "until_event": r"(?:по окончани|аяқталғаннан|после)",
    "permanent": r"постоянн|на постоянной|мерзімсіз",
    "monthly": r"ежемесяч|ай сайын",
    "immediately": r"незамедлительн|дереу",
    "as_needed": r"по мере необходимости|қажет болған",
}


def extract_paragraphs(docx_path: Path) -> list[str]:
    texts: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        for p in root.iter(f"{W}p"):
            parts = [t.text for t in p.iter(f"{W}t") if t.text]
            if parts:
                texts.append("".join(parts).strip())
    except Exception:
        pass
    return texts


def load_taxonomy() -> tuple[dict[str, str], dict[str, str]]:
    by_rel: dict[str, str] = {}
    by_name: dict[str, str] = {}
    if not TAX.exists():
        return by_rel, by_name
    with TAX.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("section") == "aggregate":
                continue
            scenario = row.get("scenario", "S_GENERAL")
            rel = row.get("relative_path", "")
            name = row.get("filename", "")
            if rel:
                by_rel[rel] = scenario
            if name:
                by_name[name] = scenario
    return by_rel, by_name


def main() -> None:
    tax_by_rel, tax_by_name = load_taxonomy()
    verb_counts: Counter[str] = Counter()
    clause_order: Counter[str] = Counter()
    preamble_counts: Counter[str] = Counter()
    scenario_items: dict[str, list[int]] = defaultdict(list)
    scenario_item_kinds: dict[str, Counter[str]] = defaultdict(Counter)
    multi_obligation = 0
    total_items = 0
    kk_docs = 0
    ru_only = 0
    bilingual_mirror = 0

    for docx in sorted(ROOT.rglob("*.docx")):
        rel = str(docx.relative_to(ROOT)).replace("\\", "/")
        scenario = tax_by_rel.get(rel) or tax_by_name.get(docx.name, "S_GENERAL")
        paras = extract_paragraphs(docx)
        if not paras:
            continue

        full_text = "\n".join(paras)
        if re.search(r"БҰЙЫРАМЫН|жүктелсін|тағайындалсын", full_text):
            kk_docs += 1
        if re.search(r"ПРИКАЗЫВАЮ", full_text) and not re.search(r"БҰЙЫРАМЫН", full_text):
            ru_only += 1
        if re.search(r"ПРИКАЗЫВАЮ", full_text) and re.search(r"БҰЙЫРАМЫН", full_text):
            bilingual_mirror += 1

        preamble_text = ""
        in_order = False
        item_count = 0
        for p in paras:
            if re.search(r"ПРИКАЗЫВАЮ|БҰЙЫРАМЫН", p, re.I):
                in_order = True
                continue
            if not in_order:
                preamble_text += " " + p
            m = ITEM_RE.match(p)
            if m and in_order:
                item_count += 1
                body = m.group(3).strip()
                total_items += 1
                matched_verbs = 0
                for kind, pat in VERB_STEMS.items():
                    if re.search(pat, body, re.I):
                        verb_counts[kind] += 1
                        scenario_item_kinds[scenario][kind] += 1
                        matched_verbs += 1
                if matched_verbs > 1:
                    multi_obligation += 1
                for order_type, pat in CLAUSE_ORDER.items():
                    if re.search(pat, body, re.I):
                        clause_order[order_type] += 1

        scenario_items[scenario].append(item_count)
        for pk, pat in PREAMBLE_PATTERNS.items():
            if re.search(pat, preamble_text, re.I):
                preamble_counts[pk] += 1

    lines = [
        f"total_items={total_items}",
        f"multi_obligation_items={multi_obligation}",
        f"kk_or_bilingual_docs={kk_docs}",
        f"ru_only_docs={ru_only}",
        f"bilingual_mirror_docs={bilingual_mirror}",
        "---verb_stems---",
    ]
    for k, v in verb_counts.most_common():
        lines.append(f"{k}={v}")
    lines.append("---clause_order---")
    for k, v in clause_order.most_common():
        lines.append(f"{k}={v}")
    lines.append("---preamble---")
    for k, v in preamble_counts.most_common():
        lines.append(f"{k}={v}")
    lines.append("---scenario_item_counts---")
    for sc, counts in sorted(scenario_items.items()):
        if counts:
            avg = sum(counts) / len(counts)
            lines.append(f"{sc}:n={len(counts)},min={min(counts)},max={max(counts)},avg={avg:.1f}")
    lines.append("---scenario_top_verbs---")
    for sc, ctr in sorted(scenario_item_kinds.items()):
        top = ctr.most_common(5)
        lines.append(f"{sc}:{','.join(f'{k}={v}' for k,v in top)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
