from __future__ import annotations

import argparse

from app.services.personnel_order_template_manifest import ManifestError, export_drafts, export_published
from app.services.personnel_order_template_specs import PERSONNEL_ORDER_TEMPLATE_SPECS


def main() -> int:
    parser = argparse.ArgumentParser(description="Export local personnel-order templates to canonical Git manifests.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", dest="item_type_code")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--from-published", action="store_true", help="Export one explicitly identified immutable PUBLISHED version.")
    parser.add_argument("--template-version-id", type=int, help="Required with --from-published.")
    args = parser.parse_args()
    if args.from_published and args.all:
        parser.error("--from-published requires --type, not --all")
    if args.from_published and args.template_version_id is None:
        parser.error("--template-version-id is required with --from-published")
    if not args.from_published and args.template_version_id is not None:
        parser.error("--template-version-id requires --from-published")
    types = sorted(PERSONNEL_ORDER_TEMPLATE_SPECS) if args.all else [args.item_type_code]
    try:
        results = (
            export_published(types[0], expected_template_version_id=args.template_version_id)
            if args.from_published
            else export_drafts(types)
        )
    except (ManifestError, ValueError) as error:
        parser.error(str(error))
    for item_type_code, result in results.items():
        print(f"{item_type_code} {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
