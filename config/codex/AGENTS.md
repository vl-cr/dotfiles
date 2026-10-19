# Instructions

## Global

- Only use British English spelling.
- Report any given **Command issue** in the final response when an unresolved command failure requires action from the user (me). State the command, cause, impact and action needed. Omit flaky failures resolved by a retry. Don't omit the failures fixed by workarounds unless the user agreed that it's an acceptable workaround.
- When using **Windows Codex with WSL**, use WSL shell commands to read local files, including SKILL.md. Avoid node_repl for these reads.
- Only use Codex's **built-in browser** for browser-related work unless the user explicitly asks to use Chrome via the extension.
- Use "**ASD-STE100** Simplified Technical English (STE)" standard for technical language and documentation.
- Under no circumstances perform **non-read actions** that affect the state of the external resources (e.g. it's OK to read the contents of the linked Github PR, but don't post PR comments on user's behalf). These non-read actions should only ever be perform if the user explicitely asks for it to be done by Codex.
- Use the **simplicity-first principle**: only write the code needed for the task, state success critearia and verifiable results that will be used to set the right boundaries.

## Documentation

Use the `→` symbol when documenting any sequence of steps, including software algorithms, workflows, procedures, or everyday examples.

For example:

> Prepare the ingredients → Make the batter → Pre-heat the oven → Pour the batter into the cake tin → Bake for 45 minutes

## Maintaining these instructions

- Keep small, self-contained instructions directly in `AGENTS.md`.
- Put more complex guidance and multi-line logic explanations in separate Markdown files under `instructions/`, such as `git.md` or `coding.md`, then link them under **Topic guides**.
- If you can't read these separate instructions or if something critical is lacking there, it's very important that you raise it in the output so that I can fix the issue(s).

## Topic guides

The topic guides live under `$CODEX_HOME/instructions` (normally `~/.codex/instructions`), which this dotfiles setup installs from `config/codex/instructions`. Resolve the links below from `$CODEX_HOME`, not from the active project checkout.

Before working in any of the following areas, read and follow the relevant guide. Read only the guides needed for the current task.

- [Coding](instructions/coding.md) — Read when writing, reviewing or changing code. Apply the Python section only to Python work.
- [Git](instructions/git.md) — Git-operation restrictions and commit-message conventions.
- [Diagrams](instructions/diagrams.md) — Diagram selection, D2 authoring, rendering, visual verification, animation, and presentation export.
