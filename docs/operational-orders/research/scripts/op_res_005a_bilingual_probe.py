#!/usr/bin/env python3
"""
OP-RES-005A — read-only bilingual / translation workflow probe.
Finds RU/KK pairs (separate files + intra-document bilingual blocks).
Writes anonymized outputs only. No PII in Git-tracked CSVs.
Does not modify source documents.
"""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(r"d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы")
OUT_DIR = Path(__file__).resolve().parents[1] / "data"
TAX = OUT_DIR / "OP-RES-003-order-taxonomy-summary.csv"

ITEM_RE = re.compile(r"^(\d+(?:\.\d+)*)([\.)])\s*(.+)", re.S)
DATE_RE = re.compile(r"\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}|\d{4}\s*ж(?:ыл|.)")
AMOUNT_RE = re.compile(r"\d[\d\s]{2,}\s*(?:тенге|тг|₸|KZT)?", re.I)
ORDER_NUM_RE = re.compile(r"№\s*[_\d]+|№\s*[A-Za-zА-Яа-я0-9\-]+")
FIO_RE = re.compile(r"[А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z]\.[А-ЯЁA-Z]\.")

KK_MARKERS = re.compile(
    r"БҰЙЫРАМЫН|бұйрық|жүктелсін|тағайындалсын|бекітілсін|қосымша|Негіздеме|Келісілді|Танысу",
    re.I,
)
RU_MARKERS = re.compile(
    r"ПРИКАЗЫВАЮ|приказ|возложить|Контроль|Приложение|Основание|Келісілді",
    re.I,
)
TRANSLATION_FN = re.compile(r"перевод|translate|kk|kz|қаз|каз\.?|kaz", re.I)

LANG_SUFFIX_RE = re.compile(
    r"[\s_\-]+(ru|kk|kz|rus|kaz|рус|каз|қаз)[\s_\-]*(\.|$|\)|\d)",
    re.I,
)


def doc_id(rel: str) -> str:
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]


def folder_code(rel: str) -> str:
    top = rel.split("/")[0].split("\\")[0] if rel else "root"
    return hashlib.sha256(top.encode("utf-8")).hexdigest()[:8]


def normalize_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"\(\d+\)", "", stem)
    stem = re.sub(r"\s*[-–—]\s*копия.*", "", stem, flags=re.I)
    stem = re.sub(r"\s*(испр|новая|последняя|final|draft|проект).*", "", stem, flags=re.I)
    stem = LANG_SUFFIX_RE.sub("", stem)
    stem = re.sub(r"[^a-z0-9а-яёқғңұүіөһ]+", " ", stem, flags=re.I)
    return " ".join(stem.split())


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


def anonymize_text(text: str) -> str:
    t = FIO_RE.sub("[PERSON]", text)
    return t


@dataclass
class DocProfile:
    rel: str
    doc_id: str
    folder_code: str
    ext: str
    size: int
    mtime: float
    ctime: float
    filename_lang: str
    has_ru: bool
    has_kk: bool
    layout: str
    item_numbers: list[str] = field(default_factory=list)
    ru_item_count: int = 0
    kk_item_count: int = 0
    shared_item_count: int = 0
    dates: list[str] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    order_nums: list[str] = field(default_factory=list)
    attachment_refs: int = 0
    has_control_ru: bool = False
    has_control_kk: bool = False
    kk_after_ru: bool | None = None
    scenario: str = "S_GENERAL"


def classify_layout(paras: list[str], full: str) -> tuple[str, bool, bool, bool | None]:
    has_ru = bool(RU_MARKERS.search(full))
    has_kk = bool(KK_MARKERS.search(full))
    prikaz_idx = [i for i, p in enumerate(paras) if re.search(r"ПРИКАЗЫВАЮ", p, re.I)]
    buyryk_idx = [i for i, p in enumerate(paras) if re.search(r"БҰЙЫРАМЫН", p, re.I)]

    kk_after_ru: bool | None = None
    if prikaz_idx and buyryk_idx:
        kk_after_ru = min(buyryk_idx) > min(prikaz_idx)

    if has_ru and has_kk:
        if prikaz_idx and buyryk_idx:
            if kk_after_ru:
                layout = "bilingual_kk_after_ru"
            else:
                layout = "bilingual_ru_after_kk"
        else:
            layout = "bilingual_interleaved"
    elif has_kk:
        layout = "kk_only_content"
    elif has_ru:
        layout = "ru_only_content"
    else:
        layout = "unknown_content"

    return layout, has_ru, has_kk, kk_after_ru


def extract_items(paras: list[str]) -> tuple[list[str], int, int]:
    all_nums: list[str] = []
    ru_items = 0
    kk_items = 0
    in_ru = False
    in_kk = False
    for p in paras:
        if re.search(r"ПРИКАЗЫВАЮ", p, re.I):
            in_ru, in_kk = True, False
        if re.search(r"БҰЙЫРАМЫН", p, re.I):
            in_kk, in_ru = True, False
        m = ITEM_RE.match(p)
        if m:
            num = m.group(1)
            all_nums.append(num)
            body = m.group(3)
            if in_kk or (KK_MARKERS.search(body) and not RU_MARKERS.search(body)):
                kk_items += 1
            elif in_ru or RU_MARKERS.search(body):
                ru_items += 1
            else:
                ru_items += 1
    return all_nums, ru_items, kk_items


def filename_lang(name: str) -> str:
    n = name.lower()
    if re.search(r"[қғңұүіөһ]", n):
        return "kk"
    if TRANSLATION_FN.search(n):
        return "translation_marker"
    if re.search(r"\.(kk|kz)\.", n) or re.search(r"[\s_](kk|kz)[\s_.]", n):
        return "kk"
    if re.search(r"[\s_](ru|rus)[\s_.]", n):
        return "ru"
    return "ru"


def load_taxonomy() -> dict[str, str]:
    by_name: dict[str, str] = {}
    if not TAX.exists():
        return by_name
    with TAX.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("filename", "")
            if name:
                by_name[name] = row.get("scenario", "S_GENERAL")
    return by_name


def profile_doc(path: Path, tax: dict[str, str]) -> DocProfile | None:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        st = path.stat()
    except OSError:
        return None
    paras = extract_paragraphs(path) if path.suffix.lower() == ".docx" else []
    full = "\n".join(paras)
    layout, has_ru, has_kk, kk_after_ru = classify_layout(paras, full)
    nums, ru_ic, kk_ic = extract_items(paras)
    dates = list(set(DATE_RE.findall(full)))[:10]
    amounts = [re.sub(r"\s+", " ", a.strip()) for a in AMOUNT_RE.findall(full)][:5]
    order_nums = ORDER_NUM_RE.findall(full)[:3]
    attach = len(re.findall(r"Приложение|қосымша|1-қосымша", full, re.I))

    return DocProfile(
        rel=rel,
        doc_id=doc_id(rel),
        folder_code=folder_code(rel),
        ext=path.suffix.lower(),
        size=st.st_size,
        mtime=st.st_mtime,
        ctime=st.st_ctime,
        filename_lang=filename_lang(path.name),
        has_ru=has_ru,
        has_kk=has_kk,
        layout=layout,
        item_numbers=nums,
        ru_item_count=ru_ic,
        kk_item_count=kk_ic,
        shared_item_count=len(nums),
        dates=dates,
        amounts=amounts,
        order_nums=order_nums,
        attachment_refs=attach,
        has_control_ru=bool(re.search(r"Контроль", full)),
        has_control_kk=bool(re.search(r"Бақылау|бақылау", full)),
        kk_after_ru=kk_after_ru,
        scenario=tax.get(path.name, "S_GENERAL"),
    )


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def pair_score(a: DocProfile, b: DocProfile) -> tuple[float, dict[str, float]]:
    signals: dict[str, float] = {}
    stem_a = normalize_stem(Path(a.rel).name)
    stem_b = normalize_stem(Path(b.rel).name)
    signals["stem_similarity"] = jaccard(set(stem_a.split()), set(stem_b.split()))
    signals["same_folder"] = 1.0 if a.folder_code == b.folder_code else 0.0
    signals["size_ratio"] = min(a.size, b.size) / max(a.size, b.size) if max(a.size, b.size) else 0
    signals["item_count_match"] = (
        1.0 if a.shared_item_count == b.shared_item_count and a.shared_item_count > 0 else 0.0
    )
    signals["date_overlap"] = jaccard(set(a.dates), set(b.dates))
    signals["amount_overlap"] = jaccard(set(a.amounts), set(b.amounts))
    dt = abs(a.mtime - b.mtime)
    signals["mtime_proximity"] = max(0.0, 1.0 - dt / (86400 * 30)) if dt else 1.0
    # complementary language filenames
    langs = {a.filename_lang, b.filename_lang}
    signals["complementary_filename_lang"] = (
        1.0 if ("kk" in langs or "translation_marker" in langs) and a.filename_lang != b.filename_lang else 0.0
    )
    weights = {
        "stem_similarity": 0.25,
        "same_folder": 0.15,
        "size_ratio": 0.1,
        "item_count_match": 0.2,
        "date_overlap": 0.15,
        "amount_overlap": 0.05,
        "mtime_proximity": 0.05,
        "complementary_filename_lang": 0.05,
    }
    score = sum(signals[k] * weights[k] for k in weights)
    return score, signals


def confidence_level(score: float, signals: dict[str, float]) -> str:
    if score >= 0.72 and signals.get("item_count_match", 0) >= 0.5:
        return "high"
    if score >= 0.55:
        return "probable"
    if score >= 0.38:
        return "weak"
    return "no_match"


def compare_intra_bilingual(d: DocProfile) -> dict[str, object]:
    """Compare RU vs KK blocks inside same document."""
    if not (d.has_ru and d.has_kk):
        return {"relation": "not_bilingual", "drift_score": None}
    item_ratio = (
        min(d.ru_item_count, d.kk_item_count) / max(d.ru_item_count, d.kk_item_count)
        if max(d.ru_item_count, d.kk_item_count)
        else 0
    )
    control_match = d.has_control_ru == d.has_control_kk
    relation = "adapted_translation"
    if item_ratio >= 0.9 and control_match:
        relation = "direct_translation"
    elif item_ratio < 0.7:
        relation = "abbreviated_or_expanded"
    elif not control_match:
        relation = "partial_translation"
    drift = 1.0 - item_ratio
    return {
        "relation": relation,
        "drift_score": round(drift, 3),
        "ru_items": d.ru_item_count,
        "kk_items": d.kk_item_count,
        "kk_after_ru": d.kk_after_ru,
    }


def main() -> None:
    tax = load_taxonomy()
    profiles: list[DocProfile] = []
    for p in sorted(ROOT.rglob("*")):
        if p.suffix.lower() in {".docx", ".doc", ".pdf"} and p.is_file():
            prof = profile_doc(p, tax)
            if prof:
                profiles.append(prof)

    # Separate-file pair search (docx only, different files)
    docx_profiles = [p for p in profiles if p.ext == ".docx"]
    pairs: list[dict] = []
    seen_pair: set[frozenset[str]] = set()
    for i, a in enumerate(docx_profiles):
        for b in docx_profiles[i + 1 :]:
            if a.doc_id == b.doc_id:
                continue
            score, signals = pair_score(a, b)
            conf = confidence_level(score, signals)
            if conf == "no_match":
                continue
            key = frozenset({a.doc_id, b.doc_id})
            if key in seen_pair:
                continue
            seen_pair.add(key)
            earlier = "a" if a.mtime <= b.mtime else "b"
            mtime_delta_h = abs(a.mtime - b.mtime) / 3600
            pairs.append(
                {
                    "pair_id": f"P{len(pairs)+1:03d}",
                    "doc_a_id": a.doc_id,
                    "doc_b_id": b.doc_id,
                    "folder_code": a.folder_code if a.folder_code == b.folder_code else "mixed",
                    "confidence": conf,
                    "score": round(score, 3),
                    "pair_type": "separate_files",
                    "scenario_a": a.scenario,
                    "scenario_b": b.scenario,
                    "layout_a": a.layout,
                    "layout_b": b.layout,
                    "items_a": a.shared_item_count,
                    "items_b": b.shared_item_count,
                    "mtime_delta_hours": round(mtime_delta_h, 1),
                    "earlier_mtime_doc": a.doc_id if earlier == "a" else b.doc_id,
                    "filename_lang_a": a.filename_lang,
                    "filename_lang_b": b.filename_lang,
                    "date_overlap": round(signals["date_overlap"], 2),
                    "stem_similarity": round(signals["stem_similarity"], 2),
                    "source_language_hint": (
                        "ru_first"
                        if a.filename_lang == "ru" and b.filename_lang in {"kk", "translation_marker"}
                        else (
                            "kk_first"
                            if b.filename_lang == "ru" and a.filename_lang in {"kk", "translation_marker"}
                            else "unknown"
                        )
                    ),
                }
            )

    # Intra-document bilingual records
    intra: list[dict] = []
    for d in docx_profiles:
        if d.has_ru and d.has_kk:
            cmp = compare_intra_bilingual(d)
            intra.append(
                {
                    "pair_id": f"I{d.doc_id[:6]}",
                    "doc_id": d.doc_id,
                    "folder_code": d.folder_code,
                    "confidence": "high",
                    "pair_type": "intra_document_bilingual",
                    "scenario": d.scenario,
                    "layout": d.layout,
                    "kk_after_ru": d.kk_after_ru,
                    "ru_items": cmp["ru_items"],
                    "kk_items": cmp["kk_items"],
                    "relation": cmp["relation"],
                    "drift_score": cmp["drift_score"],
                    "source_language_hint": (
                        "ru_first" if d.kk_after_ru else "kk_first" if d.kk_after_ru is False else "unknown"
                    ),
                }
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pair_csv = OUT_DIR / "OP-RES-005A-language-pair-summary.csv"
    with pair_csv.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "pair_id",
            "pair_type",
            "confidence",
            "doc_a_id",
            "doc_b_id",
            "doc_id",
            "folder_code",
            "score",
            "scenario_a",
            "scenario_b",
            "scenario",
            "layout_a",
            "layout_b",
            "layout",
            "items_a",
            "items_b",
            "ru_items",
            "kk_items",
            "mtime_delta_hours",
            "earlier_mtime_doc",
            "filename_lang_a",
            "filename_lang_b",
            "date_overlap",
            "stem_similarity",
            "kk_after_ru",
            "relation",
            "drift_score",
            "source_language_hint",
        ]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in pairs:
            w.writerow(row)
        for row in intra:
            w.writerow(row)

    # Workflow evidence summary
    layout_ctr = Counter(p.layout for p in docx_profiles)
    fn_lang_ctr = Counter(p.filename_lang for p in profiles)
    ru_only = sum(1 for p in docx_profiles if p.layout == "ru_only_content")
    kk_only = sum(1 for p in docx_profiles if p.layout == "kk_only_content")
    bilingual = sum(1 for p in docx_profiles if "bilingual" in p.layout)
    kk_after_ru_count = sum(1 for p in docx_profiles if p.kk_after_ru is True)
    kk_before_ru = sum(1 for p in docx_profiles if p.kk_after_ru is False)

    high_pairs = sum(1 for p in pairs if p["confidence"] == "high")
    prob_pairs = sum(1 for p in pairs if p["confidence"] == "probable")
    weak_pairs = sum(1 for p in pairs if p["confidence"] == "weak")

    evidence_rows = [
        ("corpus_total_files", len(profiles), "confirmed"),
        ("docx_analyzed", len(docx_profiles), "confirmed"),
        ("filename_ru_primary", fn_lang_ctr.get("ru", 0), "confirmed"),
        ("filename_kk_primary", fn_lang_ctr.get("kk", 0), "confirmed"),
        ("content_ru_only", ru_only, "confirmed"),
        ("content_kk_only", kk_only, "confirmed"),
        ("content_bilingual_same_file", bilingual, "confirmed"),
        ("bilingual_kk_after_ru", kk_after_ru_count, "confirmed"),
        ("bilingual_ru_after_kk", kk_before_ru, "confirmed"),
        ("separate_file_high_pairs", high_pairs, "confirmed"),
        ("separate_file_probable_pairs", prob_pairs, "confirmed"),
        ("separate_file_weak_pairs", weak_pairs, "confirmed"),
        ("intra_document_bilingual", len(intra), "confirmed"),
        ("translation_filename_markers", fn_lang_ctr.get("translation_marker", 0), "confirmed"),
    ]
    for layout, n in layout_ctr.most_common():
        evidence_rows.append((f"layout_{layout}", n, "confirmed"))

    ev_csv = OUT_DIR / "OP-RES-005A-workflow-evidence-summary.csv"
    with ev_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "value", "evidence_level"])
        w.writeheader()
        for metric, value, level in evidence_rows:
            w.writerow({"metric": metric, "value": value, "evidence_level": level})

    stats = OUT_DIR / "OP-RES-005A-corpus-probe-stats.txt"
    lines = [
        f"pairs_separate_high={high_pairs}",
        f"pairs_separate_probable={prob_pairs}",
        f"pairs_separate_weak={weak_pairs}",
        f"intra_bilingual={len(intra)}",
        f"ru_only_content={ru_only}",
        f"kk_only_content={kk_only}",
        f"kk_after_ru={kk_after_ru_count}",
        f"ru_after_kk={kk_before_ru}",
    ]
    rel_ctr = Counter(r["relation"] for r in intra)
    for k, v in rel_ctr.most_common():
        lines.append(f"intra_relation_{k}={v}")
    stats.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {pair_csv}, {ev_csv}, {stats}")


if __name__ == "__main__":
    main()
