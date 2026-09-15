"""Check inventory validation and update recovery without running Homebrew."""

import copy
import fcntl
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import homebrew_update as runner


def inventory(version: str = "1.0") -> tuple[dict, dict]:
    """Return matching formula and cask inventories with tapped identities."""
    info = {
        "formulae": [{
            "name": "example", "full_name": "vendor/tools/example",
            "installed": [{"version": version}], "linked_keg": version,
        }],
        "casks": [{
            "token": "example-app", "full_token": "vendor/apps/example-app",
            "installed": "2.0,100",
        }],
    }
    versions = {
        "formulae": [{
            "name": "example", "versions": [version],
            "linked_version": version, "optlinked_version": version,
        }],
        "casks": [{"token": "example-app", "versions": ["2.0,100"]}],
    }
    return info, versions


def snapshot(version: str = "1.0") -> dict:
    """Build a validated snapshot for runner tests."""
    return runner.normalise(*inventory(version), "Homebrew 7.0.1")


class InventoryTests(unittest.TestCase):
    def test_formula_names_cask_tokens_and_tap_identities(self) -> None:
        result = snapshot()
        self.assertEqual(
            set(result["packages"]),
            {"formula:vendor/tools/example", "cask:vendor/apps/example-app"},
        )
        self.assertEqual(
            result["packages"]["cask:vendor/apps/example-app"]["installed_versions"],
            ["2.0,100"],
        )

    def test_mismatched_or_missing_versions_are_rejected(self) -> None:
        for bad_versions in (["9.0"], []):
            with self.subTest(versions=bad_versions):
                info, versions = inventory()
                versions["formulae"][0]["versions"] = bad_versions
                with self.assertRaises((ValueError, RuntimeError, AssertionError)):
                    runner.normalise(info, versions, "Homebrew 7.0.1")

    def test_comparison_ignores_metadata_but_detects_installed_changes(self) -> None:
        before = snapshot()
        before["homebrew"] = {"version": "Homebrew 7.0.1", "reviewed_at": "earlier"}
        after = copy.deepcopy(before)
        after["homebrew"] = "Homebrew 7.0.1"
        after["captured_at"] = "later"
        after["packages"]["formula:vendor/tools/example"]["homepage"] = "https://example.test"
        self.assertEqual(runner.differences(before, after), [])
        self.assertTrue(runner.differences(before, snapshot("1.1")))
        after["homebrew"] = "Homebrew 7.0.2"
        self.assertTrue(runner.differences(before, after))

    def test_old_keg_cleanup_is_not_an_upstream_upgrade(self) -> None:
        before = snapshot()
        before["packages"]["formula:vendor/tools/example"]["installed_versions"] = ["0.9", "1.0"]
        changes = runner.differences(before, snapshot())
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "cleanup")


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        (self.root / "setup").mkdir()
        (self.root / "Taskfile.yaml").write_text("version: '3'\n")
        (self.home / "Taskfile.yaml").symlink_to(self.root / "Taskfile.yaml")
        self.state = self.root / ".automation-state" / "homebrew-daily"
        self.capture = self.enterContext(patch.object(runner, "capture", return_value=snapshot()))
        self.command = self.enterContext(patch.object(
            runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0),
        ))
        self.enterContext(patch.object(runner.shutil, "which", side_effect=lambda name: f"/opt/homebrew/bin/{name}"))
        self.enterContext(patch.object(Path, "home", return_value=self.home))

    def test_invalid_before_snapshot_prevents_update(self) -> None:
        self.capture.side_effect = ValueError("incomplete inventory")
        with self.assertRaises((ValueError, RuntimeError)):
            runner.run(self.root)
        self.command.assert_not_called()

    def test_wrong_global_taskfile_prevents_update(self) -> None:
        (self.home / "Taskfile.yaml").unlink()
        (self.home / "Taskfile.yaml").write_text("version: '3'\n")
        with self.assertRaises(RuntimeError):
            runner.run(self.root)
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_overlapping_run_is_rejected_before_brew_commands(self) -> None:
        self.state.mkdir(parents=True)
        with (self.state / "run.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "Another"):
                runner.run(self.root)
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_no_changes_runs_task_once_and_captures_after(self) -> None:
        with patch.dict(runner.os.environ, {"SUDO_ASKPASS": "/interactive/password-helper"}):
            summary = runner.run(self.root)
        self.assertEqual(self.command.call_count, 3)
        calls = self.command.call_args_list
        self.assertEqual([call.args[0] for call in calls], [
            ["/opt/homebrew/bin/task", "-g", "brew"],
            ["/opt/homebrew/bin/brew", "bundle", "install", "--file=Brewfile-casks"],
            ["/opt/homebrew/bin/brew", "cleanup"],
        ])
        self.assertEqual(calls[0].kwargs["cwd"], self.root)
        self.assertTrue(all(call.kwargs["cwd"] == self.root / "setup" for call in calls[1:]))
        self.assertEqual(calls[1].kwargs["env"]["HOMEBREW_NO_UPGRADE_QUIT_CASKS"], "1")
        for call in calls:
            self.assertEqual(call.kwargs["env"]["NONINTERACTIVE"], "1")
            self.assertEqual(call.kwargs["env"]["SUDO_ASKPASS"], "/usr/bin/false")
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
            self.assertTrue(call.kwargs["start_new_session"])
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["before", "after"])
        checkpoint = json.loads((self.state / "current.json").read_text())
        self.assertEqual(checkpoint["phase"], "research_pending")
        self.assertEqual(checkpoint["update_exit_code"], 0)
        self.assertEqual(checkpoint["update_steps"], summary["update_steps"])
        self.assertEqual(
            [(step["name"], step["exit_code"]) for step in summary["update_steps"]],
            [("brew", 0), ("casks", 0), ("cleanup", 0)],
        )

    def test_existing_reviewed_baseline_is_not_advanced(self) -> None:
        self.state.mkdir(parents=True)
        baseline = snapshot("0.9")
        baseline["homebrew"] = {"version": "Homebrew 7.0.1", "reviewed_at": "earlier"}
        (self.state / "baseline.json").write_text(json.dumps(baseline))
        self.capture.side_effect = [snapshot("1.0"), snapshot("1.1")]
        summary = runner.run(self.root)
        self.assertEqual(json.loads((self.state / "baseline.json").read_text()), baseline)
        self.assertEqual(len(summary["pending_review"]), 1)
        pending = summary["pending_review"][0]
        self.assertEqual(pending["before"]["active_version"], "0.9")
        self.assertEqual(pending["after"]["active_version"], "1.1")
        self.assertEqual(summary["changes"][0]["before"]["active_version"], "1.0")

    def test_failed_task_still_captures_after(self) -> None:
        self.command.return_value = subprocess.CompletedProcess([], 1)
        runner.run(self.root)
        self.command.assert_called_once()
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["before", "after"])
        checkpoint = json.loads((self.state / "current.json").read_text())
        self.assertEqual(checkpoint["update_exit_code"], 1)

    def test_failed_casks_still_run_cleanup_and_capture_after(self) -> None:
        self.command.side_effect = [
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 1),
            subprocess.CompletedProcess([], 0),
        ]
        summary = runner.run(self.root)
        self.assertEqual(self.command.call_count, 3)
        self.assertEqual(self.command.call_args.args[0][-1], "cleanup")
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["before", "after"])
        self.assertEqual(summary["update_exit_code"], 1)
        self.assertEqual(
            [(step["name"], step["exit_code"]) for step in summary["update_steps"]
             if step["exit_code"] is not None],
            [("brew", 0), ("casks", 1), ("cleanup", 0)],
        )
        checkpoint = json.loads((self.state / "current.json").read_text())
        self.assertEqual(checkpoint["update_steps"], summary["update_steps"])

    def test_failed_cleanup_still_captures_after(self) -> None:
        self.command.side_effect = [
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 2),
        ]
        summary = runner.run(self.root)
        self.assertEqual(self.command.call_count, 3)
        self.assertEqual(summary["update_exit_code"], 2)
        self.assertEqual(summary["update_steps"][-1]["name"], "cleanup")
        self.assertEqual(summary["update_steps"][-1]["exit_code"], 2)
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["before", "after"])

    def test_cask_launch_error_still_runs_cleanup_and_captures_after(self) -> None:
        self.command.side_effect = [
            subprocess.CompletedProcess([], 0),
            OSError("launch failed"),
            subprocess.CompletedProcess([], 0),
        ]
        summary = runner.run(self.root)
        self.assertEqual(self.command.call_count, 3)
        self.assertEqual(summary["update_exit_code"], 1)
        self.assertEqual(summary["update_steps"][1]["name"], "casks")
        self.assertIsNone(summary["update_steps"][1]["exit_code"])
        self.assertIn("launch failed", summary["update_steps"][1]["error"])
        self.assertEqual(summary["update_steps"][-1]["name"], "cleanup")
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["before", "after"])

    def test_cleanup_failure_preserves_original_cask_failure(self) -> None:
        for cleanup_result in (subprocess.CompletedProcess([], 7), OSError("cleanup launch failed")):
            with self.subTest(cleanup_result=cleanup_result):
                self.command.side_effect = [
                    subprocess.CompletedProcess([], 0),
                    subprocess.CompletedProcess([], 3),
                    cleanup_result,
                ]
                summary = runner.run(self.root)
                self.assertEqual(summary["update_exit_code"], 3)
                self.assertEqual(summary["update_steps"][-1]["name"], "cleanup")
                checkpoint = json.loads((self.state / "current.json").read_text())
                checkpoint["phase"] = "complete"
                (self.state / "current.json").write_text(json.dumps(checkpoint))

    def test_existing_cask_skip_environment_is_preserved(self) -> None:
        existing = "already-skipped vendor/apps/example-app"
        with patch.dict(runner.os.environ, {"HOMEBREW_BUNDLE_CASK_SKIP": existing}):
            runner.run(self.root)
        for call in self.command.call_args_list:
            self.assertEqual(call.kwargs["env"]["HOMEBREW_BUNDLE_CASK_SKIP"], existing)

    def test_no_cask_skip_environment_is_added(self) -> None:
        with patch.dict(runner.os.environ):
            runner.os.environ.pop("HOMEBREW_BUNDLE_CASK_SKIP", None)
            runner.run(self.root)
        for call in self.command.call_args_list:
            self.assertNotIn("HOMEBREW_BUNDLE_CASK_SKIP", call.kwargs["env"])

    def test_research_pending_returns_checkpoint_without_updating(self) -> None:
        first = runner.run(self.root)
        self.capture.reset_mock()
        self.command.reset_mock()
        self.assertEqual(runner.run(self.root), first)
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_resume_completed_checkpoint_does_not_start_a_new_run(self) -> None:
        first = runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "complete"
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        resumed = runner.run(self.root, resume=True)
        self.assertEqual(resumed["run_id"], first["run_id"])
        self.assertEqual(resumed["phase"], "complete")
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_resume_without_checkpoint_does_not_start_a_run(self) -> None:
        with self.assertRaises(RuntimeError):
            runner.run(self.root, resume=True)
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_resume_known_exit_recaptures_after_without_updating(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "updating"
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        runner.run(self.root, resume=True)
        self.command.assert_not_called()
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["after"])

    def test_resume_infers_success_from_completed_steps(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "updating"
        checkpoint.pop("update_exit_code")
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        summary = runner.run(self.root, resume=True)
        self.command.assert_not_called()
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["after"])
        self.assertEqual(summary["update_exit_code"], 0)

    def test_resume_after_formulae_runs_only_unfinished_steps(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "updating"
        checkpoint["update_exit_code"] = None
        checkpoint["update_steps"] = checkpoint["update_steps"][:1]
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        summary = runner.run(self.root, resume=True)
        self.assertEqual([call.args[0] for call in self.command.call_args_list], [
            ["/opt/homebrew/bin/brew", "bundle", "install", "--file=Brewfile-casks"],
            ["/opt/homebrew/bin/brew", "cleanup"],
        ])
        self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["after"])
        self.assertEqual(summary["update_exit_code"], 0)
        self.assertEqual([step["name"] for step in summary["update_steps"]], ["brew", "casks", "cleanup"])

    def test_resume_known_cask_failure_runs_only_unfinished_cleanup(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        completed = json.loads(checkpoint_path.read_text())
        for exit_code, overall_code, launch_error in ((5, 5, False), (5, None, False), (None, 1, True)):
            with self.subTest(exit_code=exit_code, overall_code=overall_code, launch_error=launch_error):
                checkpoint = copy.deepcopy(completed)
                checkpoint["phase"] = "updating"
                checkpoint["update_exit_code"] = overall_code
                checkpoint["update_steps"] = checkpoint["update_steps"][:2]
                checkpoint["update_steps"][1]["exit_code"] = exit_code
                if launch_error:
                    checkpoint["update_steps"][1]["error"] = "launch failed"
                checkpoint_path.write_text(json.dumps(checkpoint))
                self.capture.reset_mock()
                self.command.reset_mock()
                summary = runner.run(self.root, resume=True)
                self.command.assert_called_once()
                self.assertEqual(self.command.call_args.args[0], ["/opt/homebrew/bin/brew", "cleanup"])
                self.assertEqual([call.args[1] for call in self.capture.call_args_list], ["after"])
                self.assertEqual(summary["update_exit_code"], 1 if launch_error else 5)

    def test_resume_unknown_cleanup_refuses_even_with_known_cask_failure(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "updating"
        checkpoint["update_exit_code"] = 3
        checkpoint["update_steps"][1]["exit_code"] = 3
        checkpoint["update_steps"][2]["exit_code"] = None
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        with self.assertRaises(RuntimeError):
            runner.run(self.root, resume=True)
        self.capture.assert_not_called()
        self.command.assert_not_called()

    def test_resume_unknown_exit_refuses_another_update(self) -> None:
        runner.run(self.root)
        checkpoint_path = self.state / "current.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        checkpoint["phase"] = "updating"
        checkpoint["update_exit_code"] = None
        checkpoint["update_steps"] = checkpoint["update_steps"][:1]
        checkpoint["update_steps"][0]["exit_code"] = None
        checkpoint_path.write_text(json.dumps(checkpoint))
        self.capture.reset_mock()
        self.command.reset_mock()
        with self.assertRaises(RuntimeError):
            runner.run(self.root, resume=True)
        self.capture.assert_not_called()
        self.command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
