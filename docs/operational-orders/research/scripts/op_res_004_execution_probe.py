#!/usr/bin/env python3
"""
OP-RES-004 — read-only execution/control corpus probe.
Writes anonymized aggregates to docs/operational-orders/research/data/.
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
OUT_STATS = Path(__file__).resolve().parents[1] / "data" / "OP-RES-004-corpus-probe-stats.txt"
OUT_MATRIX = Path(__file__).resolve().parents[1] / "data" / "OP-RES-004-control-execution-matrix.csv"

ITEM_RE = re.compile(r"^(\d+(?:\.\d+)*)([\.)])\s*(.+)", re.S)
SUBENUM_RE = re.compile(r"^\d+\)\s+")

CONTROL_PATTERNS = {
    "order_delegated": r"контрол[ья].*?(?:возлож|жүктел).*(?:приказ|бұйрық|настоящ)",
    "order_self": r"(?:оставляю|қалдырамын).*(?:за собой|өзіме).*(?:контрол|бақыла)",
    "item_embedded": r"(?:взять на контроль|бақылауға ал)",
    "responsibility_delegated": r"(?:ответственность|жауапкершілік).*(?:возлож|жүктел)",
    "ensure_control": r"(?:обеспечить|усилить).*(?:контрол|бақыла)",
    "report_progress": r"(?:представля|информир|долож).*(?:ход|исполнен)",
}

EXECUTOR_PATTERNS = {
    "dative_position": r"(?:Заведующему|Руководителю|Директору|Отделу|Службе|Начальнику|Главному|Исполняющему)",
    "dative_person": r"[А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z]\.[А-ЯЁA-Z]\.",
    "unit_subject": r"(?:Отдел|Служба|Бөлім).*(?:обеспеч|организ|провест)",
    "commission": r"комисси",
    "kk_mandate": r"жүктелсін|тағайындалсын|бекітілсін",
}

DEADLINE_PATTERNS = {
    "calendar_date": r"\d{1,2}[\.\-]\d{1,2}[\.\-]\d{2,4}|\d{4}\s*жыл",
    "period_range": r"\d{1,2}\s*[-–]\s*\d{1,2}\s+(?:марта|мая|наурыз|апрел)",
    "within_n_days": r"в течение\s+\d|ішінде\s+\d",
    "from_signature": r"(?:со дня|күннен бастап).*(?:подписан|қол қой)",
    "monthly": r"ежемесяч|ай сайын",
    "quarterly": r"ежекварт",
    "permanent": r"постоянн|на постоянной|мерзімсіз",
    "until_event": r"(?:до|по окончани|аяқталғаннан кейін)",
    "no_deadline": None,
}

RESULT_PATTERNS = {
    "create_object": r"(?:создать|құру|утвердить|бекіту).*(?:комисси|положени|график)",
    "conduct_action": r"(?:провести|организовать|өткізу|направить|жіберу)",
    "provide_report": r"(?:представить|предоставить|ұсын).*(?:отчет|отчёт|акт|документ)",
    "state_change": r"(?:ввести|установить|обеспечить|взять на контроль)",
    "acknowledgement": r"(?:ознакомить|таныстыр)",
    "maintain_regime": r"(?:обеспечивать|соблюдать|сақта)",
}

EVIDENCE_PATTERNS = {
    "report": r"отчет|отчёт|авансов",
    "act": r"\bакт\b",
    "protocol": r"протокол",
    "signed_doc": r"подтверждающ",
    "ack_list": r"ознаком|танысу парағы|таныстым",
    "payment": r"платеж|перечисл",
}

DEP_PATTERNS = {
    "per_item_ref": r"(?:согласно|в соответствии с)\s+пункт",
    "after_item": r"после\s+(?:выполнения|исполнения)\s+пункта",
    "per_attachment": r"(?:согласно|в соответствии с)\s+приложени",
    "upon_approval": r"после\s+утвержден",
    "supersede": r"утратил[аи]?\s+силу|күшін жою",
}


def extract_paras(path: Path) -> list[str]:
    if path.suffix.lower() != ".docx":
        return []
    try:
        with zipfile.ZipFile(path) as zf:
            root = ET.fromstring(zf.read("word/document.xml"))
        paras: list[str] = []
        for p in root.findall(f".//{W}p"):
            texts = [t.text or "" for t in p.findall(f".//{W}t")]
            line = "".join(texts).strip()
            if line:
                paras.append(line)
        return paras
    except Exception:
        return []


def parse_items(paras: list[str]) -> list[dict]:
    items: list[dict] = []
    current: dict | None = None
    for p in paras:
        m = ITEM_RE.match(p.strip())
        if m:
            if current:
                items.append(current)
            num, _, body = m.group(1), m.group(2), m.group(3).strip()
            current = {"number": num, "body": body, "subs": []}
        elif current and (p.strip().startswith("-") or SUBENUM_RE.match(p.strip()) or re.match(r"^[а-яa-z]\)", p.strip())):
            current["subs"].append(p.strip())
        elif current and len(p) < 200 and not ITEM_RE.match(p):
            # continuation line
            current["body"] += " " + p.strip()
    if current:
        items.append(current)
    return items


def analyze_item(body: str) -> dict:
    flags = {}
    for k, pat in EXECUTOR_PATTERNS.items():
        if pat and re.search(pat, body, re.I):
            flags[f"exec_{k}"] = True
    for k, pat in DEADLINE_PATTERNS.items():
        if pat and re.search(pat, body, re.I):
            flags[f"deadline_{k}"] = True
    for k, pat in RESULT_PATTERNS.items():
        if re.search(pat, body, re.I):
            flags[f"result_{k}"] = True
    for k, pat in EVIDENCE_PATTERNS.items():
        if re.search(pat, body, re.I):
            flags[f"evidence_{k}"] = True
    for k, pat in DEP_PATTERNS.items():
        if re.search(pat, body, re.I):
            flags[f"dep_{k}"] = True
    for k, pat in CONTROL_PATTERNS.items():
        if re.search(pat, body, re.I):
            flags[f"ctrl_{k}"] = True
    # multi-verb heuristic
    verbs = len(re.findall(r"\b(?:назнач|утверд|созда|обеспеч|организ|направ|провест|возлож|установ|обяза)", body, re.I))
    flags["verb_count"] = verbs
    flags["multi_obligation_candidate"] = verbs >= 2 or (";" in body and len(body) > 120)
    return flags


def load_taxonomy() -> dict[str, dict]:
    m: dict[str, dict] = {}
    for r in csv.DictReader(TAX.open(encoding="utf-8-sig")):
        if r.get("relative_path") and r.get("scenario"):
            m[r["relative_path"]] = r
    return m


def main() -> None:
    tax = load_taxonomy()
    stats: Counter = Counter()
    scenario_stats: dict[str, Counter] = defaultdict(Counter)
    item_counts: list[int] = []
    multi_obligation_items = 0
    total_items = 0

    for rel, meta in tax.items():
        path = ROOT / rel
        paras = extract_paras(path)
        if not paras:
            continue
        full = "\n".join(paras)
        items = parse_items(paras)
        item_counts.append(len(items))
        total_items += len(items)

        # order-level control
        for k, pat in CONTROL_PATTERNS.items():
            if re.search(pat, full, re.I):
                stats[f"doc_ctrl_{k}"] += 1
                scenario_stats[meta.get("scenario", "S_OTHER")][f"ctrl_{k}"] += 1

        if not any(re.search(p, full, re.I) for p in CONTROL_PATTERNS.values() if p):
            stats["doc_no_explicit_control"] += 1

        # attachments
        if re.search(r"приложени|қосымша", full, re.I):
            stats["doc_with_attachment_ref"] += 1

        # commission
        if re.search(r"комисси", full, re.I):
            stats["doc_with_commission"] += 1
            if re.search(r"председател", full, re.I):
                stats["commission_with_chair"] += 1
            if re.search(r"секретар", full, re.I):
                stats["commission_with_secretary"] += 1

        for it in items:
            flags = analyze_item(it["body"])
            if flags.get("multi_obligation_candidate"):
                multi_obligation_items += 1
            for fk, fv in flags.items():
                if fk == "verb_count":
                    continue
                if fv:
                    stats[f"item_{fk}"] += 1

        # control position: last items often control
        if items:
            tail = items[-1]["body"] + (items[-2]["body"] if len(items) > 1 else "")
            if re.search(r"контрол|бақыла|оставляю за собой|қалдырамын", tail, re.I):
                stats["control_in_final_items"] += 1

    stats["docs_analyzed"] = len([r for r in tax if (ROOT / r).suffix.lower() == ".docx"])
    stats["total_items"] = total_items
    stats["multi_obligation_items"] = multi_obligation_items
    stats["avg_items_per_doc"] = round(total_items / max(stats["docs_analyzed"], 1), 1)

    lines = [f"{k}={v}" for k, v in stats.most_common()]
    lines.append("---scenario---")
    for sc, c in sorted(scenario_stats.items()):
        lines.append(f"{sc}:" + str(dict(c.most_common(8))))
    OUT_STATS.write_text("\n".join(lines), encoding="utf-8")

    # Build scenario matrix (aggregated, no PII)
    scenario_docs = defaultdict(list)
    for rel, meta in tax.items():
        scenario_docs[meta.get("scenario", "S_OTHER")].append(meta)

    SCENARIO_META = {
        "S_TRAVEL": ("OPERATIONS", "business_travel", "направить", "сотрудники", "order_item", "role_head_hr", "none", "director_self", "period_range", "travel_dates", "none", "travel_completed", "memo_application", "parallel_items", "no", "no", "order", "Standard 5-item travel template"),
        "S_COMMISSION": ("ORGANIZATION", "commission_create", "создать", "комиссии", "order_item+inline_roster", "role_position", "commission_members", "role_chief_accountant", "none", "none", "none", "commission_constituted", "ack_signatures", "item1_then_control", "yes", "sometimes", "order", "Roster inline or attachment"),
        "S_CLINICAL": ("CLINICAL", "clinical_operations", "организовать", "процессы", "order_item", "role_head_of_unit", "co_units", "role_deputy_director", "calendar_date", "event_period", "none", "service_organized", "implicit", "parallel_items", "no", "rare", "item_or_order", "Multiple unit directives"),
        "S_ACCOUNTING": ("FINANCE", "accounting_procedure", "утвердить", "имущество", "order_item", "role_chief_accountant", "commission", "role_chief_accountant", "none", "none", "none", "act_inventory", "act_report", "commission_then_control", "yes", "sometimes", "order", "Asset commission pattern"),
        "S_EPID": ("SAFETY", "infection_control", "утвердить", "процессы", "order_item", "role_infection_control", "units", "role_deputy_director", "permanent", "ongoing_regime", "none", "regime_maintained", "implicit", "parallel", "no", "no", "order", "Long regulatory items"),
        "S_TRAINING": ("DEVELOPMENT", "training_assignment", "направить", "сотрудники", "order_item", "named_or_role", "none", "director_self", "calendar_date", "training_dates", "none", "attendance", "list_training", "parallel", "no", "no", "order", "List in attachment sometimes"),
        "S_PAID_SERVICES": ("FINANCE", "paid_services", "утвердить", "услуги", "order_item", "role_finance", "units", "role_finance_head", "monthly", "billing_period", "monthly", "tariff_applied", "accounting_doc", "sequential", "no", "sometimes", "order", "Periodic billing cycle"),
        "S_PROCUREMENT": ("GOVERNANCE", "procurement_procedure", "утвердить", "закупки", "order_item", "role_procurement", "commission", "role_economy_deputy", "until_event", "procedure_timeline", "none", "procurement_conducted", "protocol", "legal_basis_first", "sometimes", "yes", "order", "Legal refs drive steps"),
        "S_DISCIPLINE": ("HR_OPERATIONS", "disciplinary_action", "назначить", "сотрудники", "order_item", "named_employee", "managers", "multi_controller", "within_n_days", "3_working_days", "none", "sanction_applied", "ack_list", "sequential_awareness", "no", "no", "item", "Awareness items depend on sanction"),
        "S_PHARMA": ("CLINICAL", "pharmaceutical_control", "установить", "процессы", "order_item", "role_pharmacy", "units", "role_deputy_director", "permanent", "ongoing", "none", "regime_maintained", "inventory_records", "cascade", "sometimes", "inline_tables", "order", "Mega-order multi-item"),
        "S_RESPONSIBILITY": ("ORGANIZATION", "responsibility_assignment", "назначить", "процессы", "order_item", "role_or_named", "none", "role_supervisor", "permanent", "ongoing_duty", "none", "duty_assigned", "implicit", "parallel", "no", "no", "item", ""),
        "S_REGULATION": ("GOVERNANCE", "document_approval", "утвердить", "документы", "order_item", "role_owner", "none", "role_director", "from_signature", "effective_on_sign", "none", "document_approved", "signed_order", "preamble_law", "no", "yes_attachment", "order", ""),
        "S_FUNDS": ("FINANCE", "funds_allocation", "обеспечить", "финансы", "order_item", "named_or_role", "finance_unit", "director_self", "until_event", "after_event_report", "none", "funds_transferred", "advance_report", "item1_then_report", "no", "no", "item", ""),
        "S_EVENT": ("ORGANIZATION", "institutional_event", "организовать", "мероприятия", "order_item", "role_heads", "co_units", "role_deputy", "calendar_date", "event_date", "none", "event_held", "implicit", "parallel", "no", "no", "item", ""),
        "S_CONFERENCE": ("ORGANIZATION", "conference_support", "организовать", "мероприятия", "order_item", "role_organizer", "co_units", "director_self", "calendar_date", "conference_dates", "none", "participation_arranged", "financial_report", "parallel", "no", "no", "order", ""),
        "S_TRANSPORT": ("SAFETY", "transport_access", "установить", "оборудование", "order_item", "role_ahc", "drivers", "role_ahc_head", "permanent", "ongoing", "none", "access_regime", "log_book", "hierarchical_subitems", "no", "no", "order", "Nested 1.1. numbering"),
        "S_DRILL": ("SAFETY", "emergency_drill", "провести", "мероприятия", "order_item", "role_ahc", "units", "role_deputy", "calendar_date", "drill_date", "none", "drill_completed", "act_protocol", "parallel", "no", "no", "order", ""),
        "S_PLAN": ("FINANCE", "economic_plan", "утвердить", "планы", "order_item", "role_economy", "units", "role_economy_deputy", "annual", "plan_year", "yearly", "plan_approved", "signed_plan", "legal_basis", "no", "yes", "order", ""),
        "S_RADIATION": ("SAFETY", "radiation_safety", "создать", "комиссии", "order_item", "role_vcро", "commission", "role_vcro_head", "permanent", "ongoing", "none", "inspection_act", "act", "commission_items", "yes", "no", "order", ""),
        "S_COMPLIANCE": ("GOVERNANCE", "compliance_program", "утвердить", "процессы", "order_item", "role_compliance", "units", "director_self", "permanent", "ongoing", "none", "program_active", "implicit", "cascade", "no", "no", "order", ""),
        "S_GENERAL": ("ADMINISTRATIVE", "operational_directive", "делегировать", "процессы", "order_item", "unknown", "none", "unknown", "no_deadline", "none", "none", "unknown", "unknown", "unknown", "unknown", "unknown", "unknown", "DOC only"),
    }

    fields = [
        "scenario_code", "domain", "order_type", "business_intent", "managed_object",
        "execution_unit", "primary_responsible_party", "co_executors", "controller",
        "deadline_type", "deadline_expression", "recurrence", "expected_result",
        "execution_evidence", "dependencies", "commission_involved", "attachment_driven",
        "control_scope", "docs_in_corpus", "notes",
    ]
    with OUT_MATRIX.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for sc in sorted(scenario_docs.keys()):
            meta = SCENARIO_META.get(sc, SCENARIO_META["S_GENERAL"])
            row = {"scenario_code": sc}
            for i, f in enumerate(fields[1:19], start=0):
                row[f] = meta[i] if i < len(meta) else ""
            row["docs_in_corpus"] = str(len(scenario_docs[sc]))
            row["notes"] = meta[18] if len(meta) > 18 else ""
            w.writerow(row)

    print("wrote", OUT_STATS, OUT_MATRIX)
    print("docs", stats["docs_analyzed"], "items", total_items, "multi_obl", multi_obligation_items)


if __name__ == "__main__":
    main()
