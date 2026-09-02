# Instructions

## Global

- Only use British English spelling.
- Only use Codex's built-in browser for browser-related work unless the user explicitly asks to use Chrome via the extension.

## Maintaining these instructions

- Keep small, self-contained instructions directly in `AGENTS.md`.
- Put more complex guidance and multi-line logic explanations in separate Markdown files under `instructions/`, such as `git.md` or `python.md`, then link them under **Topic guides**.

## Documentation

Use the `→` symbol when documenting any sequence of steps, including software algorithms, workflows, procedures, or everyday examples.

For example:

> Prepare the ingredients → Make the batter → Pre-heat the oven → Pour the batter into the cake tin → Bake for 45 minutes

## External actions

Under no circumstances perform non-read actions that affect anything outside the scope of the environment you are working in.

For example, when working with GitHub pull requests:

- It's OK to read pull request contents, comments, and diffs.
- Don't post comments on the user's behalf, push changes, or take any other action outside the scope of reviewing code and writing code locally.

## Topic guides

The topic guides live under `$CODEX_HOME/instructions` (normally `~/.codex/instructions`), which this dotfiles setup installs as a symlink to `config/codex/instructions`. Resolve the links below from `$CODEX_HOME`, not from the active project checkout.

Before working in any of the following areas, read and follow the relevant guide. Read only the guides needed for the current task.

- [Python](instructions/python.md) — Python version, type hints, and docstrings.
- [Git](instructions/git.md) — Git-operation restrictions and commit-message conventions.
- [Diagrams](instructions/diagrams.md) — Diagram selection, D2 authoring, rendering, visual verification, animation, and presentation export.
