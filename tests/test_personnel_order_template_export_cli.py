from __future__ import annotations

import sys

import pytest

from app.scripts import export_personnel_order_templates as cli


def test_from_published_requires_explicit_id_and_routes_only_to_published_export(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(cli, "export_published", lambda item_type_code, *, expected_template_version_id: calls.append((item_type_code, expected_template_version_id)) or {item_type_code: "EXPORT"})
    monkeypatch.setattr(cli, "export_drafts", lambda _: pytest.fail("DRAFT export must not run"))
    monkeypatch.setattr(sys, "argv", ["export", "--type", "TERMINATION", "--from-published", "--template-version-id", "9"])

    assert cli.main() == 0
    assert calls == [("TERMINATION", 9)]
    assert capsys.readouterr().out == "TERMINATION EXPORT\n"


@pytest.mark.parametrize(
    "argv",
    (
        ["export", "--type", "TERMINATION", "--from-published"],
        ["export", "--all", "--from-published", "--template-version-id", "9"],
        ["export", "--type", "TERMINATION", "--template-version-id", "9"],
    ),
)
def test_from_published_cli_rejects_ambiguous_or_incomplete_arguments(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exit_code:
        cli.main()
    assert exit_code.value.code == 2


def test_draft_cli_mode_is_unchanged(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "export_drafts", lambda item_types: calls.append(item_types) or {"TERMINATION": "NO_OP"})
    monkeypatch.setattr(cli, "export_published", lambda *_args, **_kwargs: pytest.fail("PUBLISHED export must be opt-in"))
    monkeypatch.setattr(sys, "argv", ["export", "--type", "TERMINATION"])

    assert cli.main() == 0
    assert calls == [["TERMINATION"]]
    assert capsys.readouterr().out == "TERMINATION NO_OP\n"
