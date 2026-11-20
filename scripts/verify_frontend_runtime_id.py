"""Verify that a Next build and its runtime environment use the same deployment ID."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def verify(frontend_build: Path, runtime_env: Path) -> str:
    metadata = json.loads((frontend_build / "required-server-files.json").read_text(encoding="utf-8"))
    built_id = metadata["config"].get("deploymentId")
    if not isinstance(built_id, str) or not re.fullmatch(r"[0-9a-f]{40}", built_id):
        raise ValueError("Next build has no valid deploymentId")

    values = [line.partition("=")[2].strip().strip('"\'')
              for line in runtime_env.read_text(encoding="utf-8").splitlines()
              if line.startswith("NEXT_DEPLOYMENT_ID=")]
    if len(values) != 1 or values[0] != built_id:
        raise ValueError("NEXT_DEPLOYMENT_ID differs from the Next build deploymentId")
    return built_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-build", type=Path, required=True, help="Path to corpsite-ui/.next")
    parser.add_argument("--runtime-env", type=Path, required=True, help="EnvironmentFile used by frontend service")
    args = parser.parse_args()
    print("frontend_deployment_id=" + verify(args.frontend_build, args.runtime_env))


if __name__ == "__main__":
    main()
