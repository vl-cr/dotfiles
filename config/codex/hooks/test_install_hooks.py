from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
import unittest

import install_hooks as installer


class HookInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.codex_home = self.root / "Codex Home"
        self.guard_source = self.root / "source guard.py"
        self.guard_source.write_text("print('guard')\n", encoding="utf-8")
        self.python = Path(sys.executable).resolve()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def install(self, template: Path | None = None) -> Path:
        return installer.install_hooks(
            self.codex_home,
            self.guard_source,
            self.python,
            template,
        )

    def document(self) -> dict[str, object]:
        return json.loads((self.codex_home / "hooks.json").read_text())

    def owned_handlers(self) -> list[tuple[dict[str, object], dict[str, object]]]:
        result: list[tuple[dict[str, object], dict[str, object]]] = []
        hooks = self.document()["hooks"]
        for group in hooks["PreToolUse"]:  # type: ignore[index]
            for handler in group["hooks"]:
                if installer._is_owned_handler(  # noqa: SLF001
                    handler, group.get("matcher"), self.codex_home
                ):
                    result.append((group, handler))
        return result

    def test_empty_install_uses_absolute_content_addressed_handler(self) -> None:
        destination = self.install()

        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), self.guard_source.read_bytes())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertRegex(destination.name, r"^dotfiles_destructive_commands_[0-9a-f]{16}\.py$")

        owned = self.owned_handlers()
        self.assertEqual(len(owned), 1)
        group, handler = owned[0]
        self.assertEqual(group["matcher"], "^Bash$")
        self.assertEqual(handler["timeout"], 5)
        command = shlex.split(handler["command"])  # type: ignore[arg-type]
        self.assertEqual(command, [str(self.python), str(destination)])
        self.assertEqual(
            stat.S_IMODE((self.codex_home / "hooks.json").stat().st_mode), 0o600
        )

    def test_installs_the_canonical_reviewed_guard_bytes(self) -> None:
        canonical_guard = Path(__file__).with_name("destructive_commands.py")

        destination = installer.install_hooks(
            self.codex_home,
            canonical_guard,
            self.python,
        )

        self.assertEqual(destination.read_bytes(), canonical_guard.read_bytes())
        compile(destination.read_bytes(), str(destination), "exec")

    def test_preserves_unrelated_data_and_group_order(self) -> None:
        existing = {
            "description": "mine",
            "unknown": {"keep": True},
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup",
                        "hooks": [{"type": "command", "command": "first"}],
                    }
                ],
                "PreToolUse": [
                    {
                        "matcher": "Read",
                        "custom": "preserve",
                        "hooks": [{"type": "command", "command": "before"}],
                    },
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "command", "command": "after"}],
                    },
                ],
            },
        }
        self.codex_home.mkdir()
        hooks_path = self.codex_home / "hooks.json"
        hooks_path.write_text(json.dumps(existing), encoding="utf-8")
        hooks_path.chmod(0o640)

        self.install()

        merged = self.document()
        self.assertEqual(merged["description"], "mine")
        self.assertEqual(merged["unknown"], {"keep": True})
        self.assertEqual(merged["hooks"]["SessionStart"], existing["hooks"]["SessionStart"])  # type: ignore[index]
        groups = merged["hooks"]["PreToolUse"]  # type: ignore[index]
        self.assertEqual([group["matcher"] for group in groups], ["Read", "Write", "^Bash$"])
        self.assertEqual(groups[0]["custom"], "preserve")
        self.assertEqual(stat.S_IMODE(hooks_path.stat().st_mode), 0o640)

    def test_migrates_exact_legacy_handler_and_preserves_similar_commands(self) -> None:
        existing = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "groupMetadata": "keep",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.codex/hooks/destructive_commands.py",
                                "statusMessage": installer.STATUS_MESSAGE,
                            }
                        ],
                    },
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "unrelated"},
                            {
                                "type": "command",
                                "command": "python3 /tmp/destructive_commands.py",
                                "statusMessage": installer.STATUS_MESSAGE,
                            },
                        ],
                    },
                ]
            }
        }
        self.codex_home.mkdir()
        (self.codex_home / "hooks.json").write_text(json.dumps(existing))

        self.install()

        self.assertEqual(len(self.owned_handlers()), 1)
        groups = self.document()["hooks"]["PreToolUse"]  # type: ignore[index]
        self.assertEqual(groups[0]["matcher"], "^Bash$")
        self.assertEqual(groups[0]["groupMetadata"], "keep")
        self.assertEqual(
            groups[1]["hooks"],
            [
                {"type": "command", "command": "unrelated"},
                {
                    "type": "command",
                    "command": "python3 /tmp/destructive_commands.py",
                    "statusMessage": installer.STATUS_MESSAGE,
                },
            ],
        )

    def test_does_not_claim_a_similarly_named_unrelated_handler(self) -> None:
        unrelated = {
            "type": "command",
            "command": "echo /tmp/destructive_commands.py --not-owned",
            "statusMessage": installer.STATUS_MESSAGE,
        }
        existing = {
            "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [unrelated]}]
            }
        }
        self.codex_home.mkdir()
        (self.codex_home / "hooks.json").write_text(json.dumps(existing))

        self.install()

        groups = self.document()["hooks"]["PreToolUse"]  # type: ignore[index]
        self.assertEqual(groups[0]["hooks"], [unrelated])
        self.assertEqual(len(self.owned_handlers()), 1)

    def test_second_install_is_byte_for_byte_idempotent(self) -> None:
        first_destination = self.install()
        hooks_path = self.codex_home / "hooks.json"
        first_bytes = hooks_path.read_bytes()
        first_stat = hooks_path.stat()

        second_destination = self.install()

        self.assertEqual(second_destination, first_destination)
        self.assertEqual(hooks_path.read_bytes(), first_bytes)
        self.assertEqual(hooks_path.stat().st_mtime_ns, first_stat.st_mtime_ns)
        self.assertEqual(len(self.owned_handlers()), 1)

    def test_guard_change_changes_handler_definition(self) -> None:
        first_destination = self.install()
        first_command = self.owned_handlers()[0][1]["command"]
        self.guard_source.write_text("print('changed guard')\n", encoding="utf-8")

        second_destination = self.install()
        second_command = self.owned_handlers()[0][1]["command"]

        self.assertNotEqual(second_destination, first_destination)
        self.assertNotEqual(second_command, first_command)
        self.assertTrue(first_destination.exists())
        self.assertTrue(second_destination.exists())
        self.assertEqual(len(self.owned_handlers()), 1)

    def test_rejects_invalid_guard_before_writing(self) -> None:
        self.guard_source.write_text("def broken(:\n", encoding="utf-8")

        with self.assertRaises(installer.InstallError):
            self.install()

        self.assertFalse(self.codex_home.exists())

    def test_repairs_owned_guard_mode(self) -> None:
        destination = self.install()
        destination.chmod(0o644)

        self.install()

        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)

    def test_rejects_a_hard_linked_guard_destination(self) -> None:
        destination = self.install()
        other_link = self.root / "other guard link.py"
        os.link(destination, other_link)

        with self.assertRaises(installer.InstallError):
            self.install()

    def test_malformed_manifest_aborts_before_any_write(self) -> None:
        malformed_documents = (
            b"not json",
            b"[]",
            b'{"hooks": []}',
            b'{"hooks": {"PreToolUse": {}}}',
            b'{"hooks": {"PreToolUse": [{}]}}',
            b'{"hooks": {"PreToolUse": [{"hooks": {}}]}}',
        )
        for index, original in enumerate(malformed_documents):
            with self.subTest(index=index):
                home = self.root / f"bad-{index}"
                home.mkdir()
                hooks_path = home / "hooks.json"
                hooks_path.write_bytes(original)
                with self.assertRaises(installer.InstallError):
                    installer.install_hooks(
                        home, self.guard_source, self.python
                    )
                self.assertEqual(hooks_path.read_bytes(), original)
                self.assertFalse((home / "hooks").exists())

    def test_symlink_migration_does_not_modify_template_target(self) -> None:
        target = self.root / "repository hooks.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.codex/hooks/destructive_commands.py",
                                        "statusMessage": installer.STATUS_MESSAGE,
                                    }
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        original = target.read_bytes()
        self.codex_home.mkdir()
        hooks_path = self.codex_home / "hooks.json"
        hooks_path.symlink_to(target)

        self.install()

        self.assertFalse(hooks_path.is_symlink())
        self.assertTrue(hooks_path.is_file())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(len(self.owned_handlers()), 1)

    def test_missing_manifest_can_start_from_template(self) -> None:
        template = self.root / "template.json"
        template.write_text(
            json.dumps(
                {
                    "templateKey": "kept",
                    "hooks": {
                        "PostToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [{"type": "command", "command": "post"}],
                            }
                        ]
                    },
                }
            )
        )

        self.install(template)

        self.assertEqual(self.document()["templateKey"], "kept")
        self.assertIn("PostToolUse", self.document()["hooks"])


if __name__ == "__main__":
    unittest.main()
