"""Capture installed versions → run the Brew task once → expose review candidates."""

import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess


def atomic_json(path: Path, value: dict) -> None:
    """Replace a JSON checkpoint atomically."""
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def normalise(info: dict, versions: dict, brew_version: str) -> dict:
    """
    Cross-check both inventories and retain installed versions and upstream metadata.

    Args:
        > info (dict): Installed Homebrew metadata.
        > versions (dict): Installed, linked and opt-linked versions.
        > brew_version (str): Homebrew's version output.

    Returns:
        - dict: An observation compatible with the existing reviewed baseline.

    Raises:
        - ValueError: The inventories disagree or contain invalid versions.
    """
    packages = {}
    for kind in ("formulae", "casks"):
        key = "name" if kind == "formulae" else "token"
        if not isinstance(info[kind], list) or not isinstance(versions[kind], list):
            raise ValueError(f"Invalid {kind} inventory")
        listed = {item[key]: item for item in versions[kind]}
        if (len(listed) != len(versions[kind]) or len(info[kind]) != len(listed)
                or {item[key] for item in info[kind]} != set(listed)):
            raise ValueError(f"{kind}: package sets differ")
        for item in info[kind]:
            name, row = item[key], listed[item[key]]
            installed = ([entry["version"] for entry in item["installed"]]
                         if kind == "formulae" else item["installed"])
            installed = [installed] if isinstance(installed, str) else installed
            if not installed or not all(isinstance(version, str) and version for version in installed):
                raise ValueError(f"{name}: invalid installed versions")
            if set(installed) != set(row["versions"]):
                raise ValueError(f"{name}: installed versions differ")
            linked, optlinked = row.get("linked_version"), row.get("optlinked_version")
            if kind == "formulae" and ((item.get("linked_keg") or None) != (linked or None)
                                      or any(value and value not in installed for value in (linked, optlinked))):
                raise ValueError(f"{name}: linked versions differ")
            package_id = ("formula:" if kind == "formulae" else "cask:") + item.get("full_name", item.get("full_token", name))
            packages[package_id] = {
                "kind": kind, "name": name, "installed_versions": sorted(installed),
                "linked_version": linked, "optlinked_version": optlinked,
                "active_version": linked or optlinked or (installed[0] if len(installed) == 1 else None),
                "homepage": item.get("homepage"), "source_urls": item.get("urls", {"url": item.get("url")}),
                "dependencies": item.get("dependencies", []),
                "runtime_dependencies": ([entry.get("runtime_dependencies", []) for entry in item["installed"]]
                                         if kind == "formulae" else []),
            }
    if not brew_version.strip().startswith("Homebrew "):
        raise ValueError("Invalid Homebrew version")
    return {"homebrew": brew_version.strip(), "packages": packages}


def capture(run_path: Path, phase: str, env: dict) -> dict:
    """Save raw installed inventories and validate them before returning an observation."""
    brew = shutil.which("brew", path=env["PATH"])
    commands = (("info.json", ["info", "--json=v2", "--installed"]),
                ("list-versions.json", ["list", "--versions", "--json"]),
                ("brew-version.txt", ["--version"]))
    errors = []
    for suffix, arguments in commands:
        with (run_path / f"{phase}-{suffix}").open("w") as output:
            result = subprocess.run([brew, *arguments], env={**env, "HOMEBREW_NO_AUTO_UPDATE": "1"},
                                    stdout=output, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode:
            errors.append(f"brew {' '.join(arguments)}: {result.stderr.strip()}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return normalise(json.loads((run_path / f"{phase}-info.json").read_text()),
                     json.loads((run_path / f"{phase}-list-versions.json").read_text()),
                     (run_path / f"{phase}-brew-version.txt").read_text())


def classify(old: dict | None, new: dict | None) -> str | None:
    """Classify observable changes without guessing unfamiliar version precedence."""
    if old is None or new is None:
        return "installed" if old is None else "removed"
    before, after = set(old["installed_versions"]), set(new["installed_versions"])
    links = ("linked_version", "optlinked_version")
    same_links = all(old.get(key) == new.get(key) for key in links)
    if before == after:
        return None if same_links else "link_changed"
    if after < before and same_links and (old.get("active_version") in after or old.get("active_version") is None):
        return "cleanup"
    return "version_changed"


def differences(before: dict, after: dict) -> list[dict]:
    """Compare installed versions and linkage, excluding source metadata and timestamps."""
    changes = []
    fields = ("installed_versions", "active_version", "linked_version", "optlinked_version")
    for package in sorted(before["packages"].keys() | after["packages"].keys()):
        old, new = before["packages"].get(package), after["packages"].get(package)
        kind = classify(old, new)
        if kind:
            changes.append({"package": package, "kind": kind,
                            "before": {key: old.get(key) for key in fields} if old else None,
                            "after": {key: new.get(key) for key in fields} if new else None})
    old_brew, new_brew = before["homebrew"], after["homebrew"]
    old_brew = old_brew["version"] if isinstance(old_brew, dict) else old_brew
    new_brew = new_brew["version"] if isinstance(new_brew, dict) else new_brew
    if old_brew != new_brew:
        changes.append({"package": "homebrew", "kind": "version_changed",
                        "before": old_brew, "after": new_brew})
    return changes


def summary(state: Path, current: dict) -> dict:
    """Return concise review candidates and paths to the complete state."""
    run_path = Path(current["run_path"])
    observations = {phase: current.get(phase) or json.loads((run_path / f"{phase}-normalised.json").read_text())
                    for phase in ("before", "after")}
    baseline = json.loads((state / "baseline.json").read_text())
    return {"phase": current["phase"], "run_id": current["run_id"],
            "update_exit_code": current["update_exit_code"],
            "update_steps": current.get("update_steps", []),
            "counts": {kind: sum(item["kind"] == kind for item in observations["after"]["packages"].values())
                       for kind in ("formulae", "casks")},
            "changes": differences(observations["before"], observations["after"]),
            "pending_review": differences(baseline, observations["after"]),
            "state_path": str(state / "current.json"), "baseline_path": str(state / "baseline.json"),
            "update_log": str(run_path / "update.log")}


def run(root: Path, resume: bool = False) -> dict:
    """
    Capture versions → update once → checkpoint observations for Codex to review.

    Args:
        > root (Path): The dotfiles checkout.
        > resume (bool): Recover an interrupted checkpoint without repeating an update.

    Returns:
        - dict: Counts, changes, outstanding version ranges and state paths.

    Raises:
        - RuntimeError: Another run is active or an interrupted update has an unknown result.
    """
    state = root / ".automation-state/homebrew-daily"
    state.mkdir(parents=True, exist_ok=True)
    with (state / "run.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another Homebrew review command is running") from error
        checkpoint = state / "current.json"
        current = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        if current:
            current.setdefault("update_exit_code", None)
        if current.get("phase") == "research_pending" or (resume and current.get("phase") == "complete"):
            return summary(state, current)
        if resume and not current:
            raise RuntimeError("There is no saved run to resume")
        incomplete = current and current.get("phase") != "complete"
        if incomplete and not resume:
            raise RuntimeError("An unfinished run exists; inspect current.json and use --resume")
        if incomplete and current.get("update_started"):
            steps = current.get("update_steps")
            if ((steps is None and current.get("update_exit_code") is None)
                    or any(step.get("exit_code") is None and not step.get("error") for step in steps or [])):
                raise RuntimeError("The previous update's exit status is unknown; inspect its process/log before recovery")
            if steps and (len(steps) == 3 or any(step.get("exit_code") or step.get("error") for step in steps)):
                current["update_exit_code"] = next((step.get("exit_code") or 1 for step in steps
                                                   if step.get("exit_code") or step.get("error")), 0)
        if (Path.home() / "Taskfile.yaml").resolve() != (root / "Taskfile.yaml").resolve():
            raise RuntimeError("~/Taskfile.yaml must resolve to this checkout's Taskfile.yaml")
        brew, task = shutil.which("brew"), shutil.which("task")
        if not brew or not task:
            raise RuntimeError("brew and task must be installed and available on PATH")
        env = {**os.environ, "DOTFILES_DIR": str(root), "NONINTERACTIVE": "1",
               # Homebrew uses sudo -A when set; false fails instead of displaying a password prompt.
               "SUDO_ASKPASS": "/usr/bin/false",
               "PATH": str(Path(brew).parent) + os.pathsep + os.environ.get("PATH", "")}
        env.pop("HOMEBREW_NO_AUTO_UPDATE", None)
        if not incomplete:
            run_id = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
            run_path = state / "runs" / run_id
            run_path.mkdir(parents=True)
            current = {"run_id": run_id, "run_path": str(run_path), "phase": "before_inventory",
                       "update_started": False, "update_exit_code": None}
            atomic_json(checkpoint, current)
        run_path = Path(current["run_path"])
        if not current.get("update_started"):
            current["before"] = capture(run_path, "before", env)
            if not (state / "baseline.json").exists():
                reviewed_at = datetime.datetime.now(datetime.UTC).isoformat()
                atomic_json(state / "baseline.json", {
                    "schema_version": 1, "run_id": current["run_id"], "reviewed_at": reviewed_at,
                    "homebrew": {"version": current["before"]["homebrew"], "reviewed_at": reviewed_at,
                                 "basis": "initial before inventory"},
                    "packages": {key: {**item, "reviewed_at": reviewed_at,
                                       "reviewed_run_id": current["run_id"], "review_basis": "initial before inventory"}
                                 for key, item in current["before"]["packages"].items()},
                })
            current.update(phase="updating", update_started=True, update_steps=[])
            atomic_json(checkpoint, current)
        steps = current.get("update_steps")
        if steps is not None and len(steps) < 3 and not (steps and (steps[0].get("exit_code") or steps[0].get("error"))):
            commands = (("brew", [task, "-g", "brew"], root),
                        ("casks", [brew, "bundle", "install", "--file=Brewfile-casks"], root / "setup"),
                        ("cleanup", [brew, "cleanup"], root / "setup"))
            with (run_path / "update.log").open("a") as output:
                for name, argv, cwd in commands[len(current["update_steps"]):]:
                    step_env = {**env, "HOMEBREW_NO_UPGRADE_QUIT_CASKS": "1"} if name == "casks" else env
                    step = {"name": name, "argv": argv, "exit_code": None}
                    current["update_steps"].append(step)
                    atomic_json(checkpoint, current)
                    output.write(f"\n{name}: {' '.join(argv)}\n")
                    output.flush()
                    try:
                        result = subprocess.run(argv, cwd=cwd, env=step_env, stdin=subprocess.DEVNULL,
                                                stdout=output, stderr=subprocess.STDOUT, check=False,
                                                start_new_session=True)
                        step["exit_code"] = result.returncode
                    except OSError as error:
                        step["error"] = str(error)
                        output.write(f"Could not start {name}: {error}\n")
                    failure = step.get("exit_code") or (1 if step.get("error") else 0)
                    if failure or name == "cleanup":
                        current["update_exit_code"] = current.get("update_exit_code") or failure
                    atomic_json(checkpoint, current)
                    if failure and name == "brew":
                        break
            current["phase"] = "after_inventory"
            atomic_json(checkpoint, current)
        current["after"] = capture(run_path, "after", env)
        current["phase"] = "research_pending"
        atomic_json(checkpoint, current)
        return summary(state, current)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="Recover an interrupted checkpoint; never repeat an unknown update")
    arguments = parser.parse_args()
    try:
        print(json.dumps(run(Path(__file__).resolve().parents[3], arguments.resume), indent=2))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(1, f"Homebrew review: {error}\n")
