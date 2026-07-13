# Getting Started with Comic Studio

This guide takes you from a fresh clone to your first rendered comic page. It assumes basic comfort with a terminal. Expect the install to take a few minutes; the creative loop from there is conversational.

---

## 1. Prerequisites

- **Python 3.12 or newer.** Check with `python3 --version`.
- **[uv](https://docs.astral.sh/uv/)** — the project's package/environment manager. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  (There is no `requirements.txt`; dependencies are pinned in `pyproject.toml` + `uv.lock` and installed by uv.)
- **An OpenAI API key** with access to `gpt-5.2` (text/vision) and `gpt-image-1.5` (image generation). Rendering images costs money — see [Cost](#7-cost-what-youll-spend).

---

## 2. Install

```bash
git clone <repo-url>
cd comics

# Create the virtualenv and install everything (runtime + dev deps) from the lockfile
uv sync
```

`uv sync` reads `pyproject.toml` and `uv.lock` and builds a `.venv/` in the project directory. You don't need to create or activate a virtualenv yourself — prefixing commands with `uv run` uses it automatically. (If you prefer, `source .venv/bin/activate` once and drop the `uv run` prefix.)

---

## 3. Configure your API key

The app loads `OPENAI_API_KEY` from a `.env` file in the project root:

```bash
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

That's the only required setting. `.env` is git-ignored.

---

## 4. Run the app

```bash
uv run python main.py
```

The studio starts a local web server and prints the URL. Open:

**http://localhost:8080**

To use a different port:

```bash
COMIC_STUDIO_PORT=9000 uv run python main.py
```

> **Note:** the server runs with hot-reload disabled on purpose — a reload would restart mid-render and interrupt image generation. If you edit the source, stop (`Ctrl-C`) and restart.

---

## 5. Found a publisher (your first workspace)

Comic Studio has **no database.** Your creative work lives outside the app repo, and **every publisher is its own git repository** — a self-contained "house" holding that publisher's styles, characters, settings, and issues. You add a project by **linking its repo in**: the app keeps a small machine-local registry (`~/.comic-studio/publishers.json`) of the houses it knows about and points a `data` symlink at whichever one is currently open, so it only ever works on one publisher at a time. This keeps user data cleanly separate from the app code, and hands all project and file management — history, backup, sharing, collaboration — to git and GitHub instead of a bespoke storage layer.

On a fresh clone there's no house yet. From the **Publishers** room in the app:

1. Choose **found a house** (the founder flow).
2. Give it a name and a folder location.
3. The app scaffolds the repo — default styles, prompts, and reference material are copied in, a `Publisher` record is written, a house `.gitignore` is added, and `git init` + a founding commit run automatically.

From then on, opening that publisher repoints `data` at it. You can found multiple houses and switch between them; the app never mixes them.

> **Reusing an existing house:** if you already have a publisher repo (for example, one shared by a collaborator), you can point the app at it from the Publishers room rather than founding a new one.

---

## 6. Now make a comic

The studio is running and your house is founded — that's the setup done. Everything from here happens through conversation with the coauthor (the right-hand panel); you never fill out a form, you talk.

For a warm, step-by-step first session — founding an imprint, casting a character, staging a panel on the light table, laying out pages, and printing the finished book — read the walkthrough:

**→ [Making Your First Comic](users-guide.md)**

---

## 7. Cost (what you'll spend)

Text and planning are cheap; **image generation is where cost accrues.** Rough per-image estimates the studio uses:

| Quality | Est. per image |
|---------|:--------------:|
| low     | ~$0.02 |
| medium  | ~$0.07 |
| high    | ~$0.19 |

The header carries a **running spend estimate** for the day (renders × quality), tallied in a `.spend.json` ledger inside your publisher repo. These are estimates for your own awareness, not a bill — check your OpenAI dashboard for actual charges.

---

## 8. Nothing is truly deleted (by default)

Deletes are **moves, not destruction.** Anything you remove — a panel, a scene, a render — goes into a `.trash` folder inside the publisher repo, and the header **wastebasket** lets you restore it. Nothing you paid to render is ever hard-deleted. The only true delete is a **30-day purge**, and it asks for confirmation first.

---

## 9. Running the tests

The suite is **128 tests across 27 modules** (binder, compositor, stitcher, layout tilings, storage isolation, trash, render queue, and more). Tests run against a temporary copy of the data, so your creative work is never touched.

```bash
# Fast run — skip tests that hit the real OpenAI API
uv run pytest -m "not api"

# Everything, including live API tests (costs money, needs a valid key)
uv run pytest

# A single module
uv run pytest tests/test_binder.py
```

Tests marked `api` make real OpenAI calls; deselect them with `-m "not api"` for the normal fast run.

---

## Troubleshooting

- **`OPENAI_API_KEY` not found / auth errors** — confirm `.env` exists in the project root and contains the key. It's loaded at startup.
- **Port already in use** — set `COMIC_STUDIO_PORT` to a free port.
- **App starts but there's no content / no publisher** — you haven't founded a house yet. Go to the **Publishers** room and found one (Section 5).
- **A render says a reference is missing** — the setting's master background or a character's styled sheet hasn't been generated yet. Render it, then re-render the panel.
- **Edits to the source don't take effect** — hot reload is off by design; stop and restart (`uv run python main.py`).

---

## Where things live

| Path | What it is |
|------|-----------|
| `main.py` | Entry point + app layout and launch (`ui.run`, port 8080) |
| `agentic/` | Agent personas (`instructions.py`), toolkits (`toolkits.py`), and the 148 function tools (`tools/`) |
| `schema/` | Pydantic models for every entity (Publisher → Panel, styles, assets) |
| `gui/` | NiceGUI views — the light table, open book, palette, wastebasket, coauthor panel |
| `helpers/` | The production pipeline — compositor, stitcher, binder (PDF/CBZ), tilings, render queue, ledgers |
| `storage/` | Local JSON storage, the publisher-repo registry, and the trash |
| `tests/` | The test suite |
| `data` | A **symlink** to the currently-open publisher repo (created when you found/open a house) |
| `~/.comic-studio/publishers.json` | Machine-local registry of your publisher houses |
