"""Idempotently add four unpublished hire-path cards to the training DB.

The existing published hire lesson, its guide, criteria, assignments and
attempts are preserved. Only short route context is appended to its task and
instruction. Existing draft edits are preserved; an obsolete generated
technical blocker is removed from draft instructions when present.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.learning.hire_path import COURSE_CODE, DRAFTS, FIRST_ROLE, FIRST_TITLE, HANDOFF_BLOCKERS, ROUTE_TITLE  # noqa: E402

TASK_CONTEXT = "Занятие 1 из 5 в маршруте «Приём нового сотрудника на работу»."
INSTRUCTION_CONTEXT = (
    "Маршрут: сохраните номер и статус этого учебного заявления. Во всех следующих "
    "занятиях используйте то же заявление и того же вымышленного кандидата; "
    "пересдача первого занятия создаёт отдельную попытку."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write to the training DB")
    args = parser.parse_args()
    if os.getenv("TRAINING_MODE") != "1":
        raise SystemExit("TRAINING_MODE=1 is required")
    url = make_url(os.environ["DATABASE_URL"])
    if url.host not in {"127.0.0.1", "localhost", "::1"} or not (
        url.database == "corpsite_learn" or (url.database or "").startswith("corpsite_learn_rehearsal_")
    ):
        raise SystemExit("Refusing to seed a non-training database")
    engine = create_engine(url)
    with engine.begin() as conn:
        revision = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
        if revision != "learning008":
            raise SystemExit(f"Expected learning008, found {revision}")
        first = conn.execute(text("""
            SELECT code, task, instruction, guide_url, created_by, state
            FROM public.learning_lessons
            WHERE course_code=:course AND title=:title AND target_role=:role
        """), {"course": COURSE_CODE, "title": FIRST_TITLE, "role": FIRST_ROLE}).mappings().all()
        if len(first) != 1 or first[0]["state"] != "published":
            raise SystemExit("Expected one published first hire lesson")
        first = first[0]
        current = {row["code"]: row for row in conn.execute(text("""
            SELECT code, state, instruction FROM public.learning_lessons
            WHERE code = ANY(:codes)
        """), {"codes": [item["code"] for item in DRAFTS]}).mappings()}
        if any(row["state"] != "draft" for row in current.values()):
            raise SystemExit("A hire-path draft was already published; refusing to overwrite it")
        print(f"{ROUTE_TITLE}: first={first['code']}, existing_drafts={len(current)}, new_drafts={4-len(current)}")
        if not args.apply:
            print("Dry run; pass --apply to save")
            return
        task = first["task"] or ""
        instruction = first["instruction"] or ""
        if TASK_CONTEXT not in task or INSTRUCTION_CONTEXT not in instruction:
            conn.execute(text("""
                UPDATE public.learning_lessons SET task=:task, instruction=:instruction, updated_at=now()
                WHERE code=:code
            """), {
                "code": first["code"],
                "task": task if TASK_CONTEXT in task else f"{task.rstrip()}\n\n{TASK_CONTEXT}",
                "instruction": instruction if INSTRUCTION_CONTEXT in instruction else f"{instruction.rstrip()}\n\n{INSTRUCTION_CONTEXT}",
            })
        for item in DRAFTS:
            if item["code"] in current:
                old_instruction = current[item["code"]]["instruction"] or ""
                blocker = HANDOFF_BLOCKERS[item["code"]]
                if old_instruction.rstrip().endswith(blocker):
                    conn.execute(text("""
                        UPDATE public.learning_lessons
                        SET instruction=:instruction, updated_at=now()
                        WHERE code=:code AND state='draft'
                    """), {"code": item["code"],
                           "instruction": old_instruction.rstrip()[:-len(blocker)].rstrip()})
                continue
            conn.execute(text("""
                INSERT INTO public.learning_lessons
                    (code,course_code,title,target_role,minutes,task,instruction,guide_url,
                     criteria_json,required_index,screenshots_json,state,created_by)
                VALUES (:code,:course,:title,:role,:minutes,:task,:instruction,'',
                        :criteria,:required_index,:screenshots,'draft',:created_by)
            """), {
                "code": item["code"], "course": COURSE_CODE, "title": item["title"],
                "role": FIRST_ROLE, "minutes": item["minutes"], "task": item["task"],
                "instruction": item["instruction"],
                "criteria": json.dumps(item["criteria"], ensure_ascii=False),
                "required_index": item["required_index"],
                "screenshots": json.dumps(item["screenshots"], ensure_ascii=False),
                "created_by": first["created_by"],
            })
    print("Saved; published=1, drafts=4. Assignments, attempts and grades were untouched.")


if __name__ == "__main__":
    main()
