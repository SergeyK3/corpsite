from __future__ import annotations

import argparse

from app.services.personnel_order_template_manifest import ManifestError, sync_manifests


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Git-managed personnel-order DRAFT manifests.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument("--type", dest="item_type_code", help="Limit synchronization to one template type.")
    args = parser.parse_args()
    try:
        results = sync_manifests(apply=args.apply, item_type_code=args.item_type_code)
    except (ManifestError, ValueError) as error:
        parser.error(str(error))
    for item_type_code, result in results.items():
        print(f"{item_type_code} {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
