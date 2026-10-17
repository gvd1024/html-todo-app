# HTML-ToDo-App

A personal task app. Every task is one Markdown file with YAML frontmatter, and people and Claude both edit the same files — on a PC and an Android phone, through OneDrive.

| Folder | What it is |
|---|---|
| `app/` | The app (`index.html`), **v0.2.0-dev** — the MVP build in progress. Phone-first list view; tasks live in a OneDrive folder (or a local folder, or demo data). |
| `poc/` | OneDrive proof of concept (spec item R1-10, step 1). See `poc/SETUP.md`. |
| `tests/` | Automated tests (Playwright + a simulated OneDrive): `python tests/run_tests.py`. |
| `docs/specs/` | Feedback-round specs and the storage spec. |
| `CLAUDE.md`, `HANDOFF.md` | Context and working rules for Claude Code. |

Live (GitHub Pages): `https://gvd1024.github.io/html-todo-app/app/` (the app) and `https://gvd1024.github.io/html-todo-app/poc/` (the proof of concept). The last released version, v0.1.1, is tagged `v0.1.1` in git.
