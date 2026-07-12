#!/usr/bin/env python3
"""Refine OP-RES-005A separate-file translation pair candidates."""
from __future__ import annotations

import csv
from pathlib import Path

CSV = Path(__file__).resolve().parents[1] / "data" / "OP-RES-005A-language-pair-summary.csv"
OUT = Path(__file__).resolve().parents[1] / "data" / "OP-RES-005A-refined-pair-counts.txt"


def main() -> None:
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    sep = [r for r in rows if r["pair_type"] == "separate_files"]
    intra = [r for r in rows if r["pair_type"] == "intra_document_bilingual"]

    # True cross-file translation: complementary layout/lang + same scenario + stem
    true = [
        r
        for r in sep
        if r["scenario_a"] == r["scenario_b"]
        and r["items_a"] == r["items_b"]
        and float(r["stem_similarity"]) >= 0.4
        and (
            (r["layout_a"] == "ru_only_content" and r["layout_b"] == "kk_only_content")
            or (r["layout_b"] == "ru_only_content" and r["layout_a"] == "kk_only_content")
            or (
                {r["filename_lang_a"], r["filename_lang_b"]} >= {"ru", "kk"}
                and "bilingual" not in r["layout_a"]
                and "bilingual" not in r["layout_b"]
            )
        )
    ]

    # Version siblings: both bilingual same scenario high stem - likely revisions not translation pairs
    revisions = [
        r
        for r in sep
        if r["confidence"] in {"high", "probable"}
        and r["scenario_a"] == r["scenario_b"]
        and "bilingual" in r["layout_a"]
        and "bilingual" in r["layout_b"]
        and float(r["stem_similarity"]) >= 0.5
    ]

    lines = [
        f"separate_file_pairs_total={len(sep)}",
        f"true_cross_file_translation_candidates={len(true)}",
        f"bilingual_revision_siblings={len(revisions)}",
        f"intra_document_bilingual={len(intra)}",
        f"intra_kk_after_ru={sum(1 for r in intra if r.get('kk_after_ru') == 'True')}",
        f"intra_ru_after_kk={sum(1 for r in intra if r.get('kk_after_ru') == 'False')}",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
