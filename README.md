# Comic Studio

A local-first application for making comic books in collaboration with an AI
coauthor. You write and organize the book — script, scenes, panels, covers,
full-page inserts — and compose artwork on a light table of layered acetates;
the AI (a single agent called the Editor, with the full studio toolkit) drafts,
critiques, renders, and answers questions about production state. Everything is
stored as plain JSON and image files inside git repositories, one repository
per publishing house, so collaboration is ordinary git.

<p align="center">
  <img src="docs/screenshots/cover-example.png" width="300" alt="Joey: Triumphs and Tumbles - AI-generated comic cover" />
</p>
<p align="center"><em>A cover produced in the studio.</em></p>

## What it does

- **The open book** — an issue is edited as the comic it will become: spreads,
  a detail dial from script down to inked panels, an exact-fill page layout
  engine on a 6×10 grid, and a production dashboard that tracks every stage
  from script to bound book.
- **The light table** — panels, covers, and mastheads compose from layered
  acetates: posed figures, props, a setting plate, and lettering, each
  draggable and re-renderable. Finished renders ("takes") hang on a wall;
  featuring one locks the table to it.
- **Reusable assets** — characters with wardrobe variants, settings with
  per-style master backgrounds, props, outfits, and comic styles with
  reference exemplars that keep renders on-model.
- **The Editor** — one agent, built on the OpenAI Agents SDK, holding every
  studio tool. It reads the same ledger the UI does, so answers about what
  remains before press come from the data, not from memory. Renders cost real
  money; batches are quoted and confirmed before they run.
- **Publishing** — a reader view of the bound book, and PDF/CBZ export with
  covers, indicia, and inserts in print order.

## Getting started

```bash
git clone <repo-url>
cd comics
uv sync
echo "OPENAI_API_KEY=sk-..." > .env
uv run python main.py
```

Open `http://localhost:8080`. An empty studio offers a demo publishing house
to explore. The full walkthrough — first run through binding a finished issue
and collaborating over git — is in **[the user's guide](docs/users-guide.md)**.

## Documentation

- **[The user's guide](docs/users-guide.md)** — how to use the studio, start
  to finish, including two-author collaboration via git.
- **[Architecture](docs/architecture.md)** — how it works, for engineers: the
  data model, the agentic stack, the layout engine, the render pipeline, and
  the design rules the codebase enforces.

## Status

A working personal studio under active development. Tests run with `pytest`
(file-fixture based; no live data or API calls). Renders require an OpenAI
API key and are billed per image.

## License

MIT
