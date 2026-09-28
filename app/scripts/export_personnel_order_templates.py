from __future__ import annotations

import argparse

from app.services.personnel_order_template_manifest import ManifestError, export_drafts
from app.services.personnel_order_template_specs import PERSONNEL_ORDER_TEMPLATE_SPECS


def main() -> int:
    parser = argparse.ArgumentParser(description="Export local personnel-order DRAFTs to canonical Git manifests.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", dest="item_type_code")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    types = sorted(PERSONNEL_ORDER_TEMPLATE_SPECS) if args.all else [args.item_type_code]
    try:
        results = export_drafts(types)
    except (ManifestError, ValueError) as error:
        parser.error(str(error))
    for item_type_code, result in results.items():
        print(f"{item_type_code} {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
