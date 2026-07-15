# Comic Studio

**An experiment in collaborative AI workflows for comic book creation.**

Comic Studio explores what happens when AI isn't a tool you operate but a peer you co-create with. There are no "generate" buttons wired to rigid templates. Instead, every interaction happens through natural conversation with context-aware AI agents that understand where you are in the creative process and what tools are relevant.

The AI is another voice in the room — not a sycophant that agrees with everything, not a steamroller that takes over. It's a collaborator that can brainstorm story ideas, draft dialogue, generate character art, and push back on creative choices when something isn't working. The creator stays in control, but the AI has a real seat at the table.

<p align="center">
  <img src="docs/screenshots/cover-witchlight.jpg" width="300" alt="Wonders of the Witchlight - AI-generated comic cover" />
  <img src="docs/screenshots/cover-example.png" width="300" alt="Joey: Triumphs and Tumbles - AI-generated comic cover" />
</p>
<p align="center"><em>Fully AI-generated comic covers, created through conversation — not forms.</em></p>

---

## Why This Exists

Most creative tools treat AI as a feature bolted onto a traditional interface: click a button, get an output, copy-paste it somewhere. The creator tosses a request over the wall and hopes something useful comes back. That's not collaboration — that's a vending machine.

Comic Studio is an experiment in a different model. The AI is a co-creator with its own perspective:

- **No wired buttons.** Creation, editing, and rendering all flow through natural language. There's no "Generate" button — you talk to the AI the way you'd talk to a collaborator sitting next to you.
- **Co-creation, not handoff.** The AI doesn't generate assets for you to drag into a separate editor. You work together in a shared workspace where story structure, character data, style references, and generated art all live side by side.
- **A peer, not a servant.** The AI can push back, suggest alternatives, and challenge choices that aren't working. No sycophancy, no steamrolling — just another voice in the room with useful skills.
- **Context-aware agents.** The system fields a studio of specialized agents, and the one who answers is chosen by whatever you've drilled into. Editing a panel? The agent already knows the scene, the characters in frame, the art style, and the dialogue. It doesn't ask you to re-explain.

---

## What It Produces

Comic Studio manages the full creative hierarchy — from series bible to individual panel — and generates imagery that maintains visual consistency across an entire issue.

### Style System

Define an art style once and apply it everywhere. The system supports separate style definitions for art, characters, and dialogue elements (speech bubbles, thought bubbles, sound effects, narration boxes). Generate style examples as visual anchors before committing to a look.

<p align="center">
  <img src="docs/screenshots/style-vintage.jpg" width="220" alt="Vintage four-color style" />
  <img src="docs/screenshots/style-watercolor.jpg" width="220" alt="Watercolor style" />
  <img src="docs/screenshots/style-anime.jpg" width="220" alt="Modern anime style" />
</p>
<p align="center"><em>The same scene prompt rendered across three different art styles.</em></p>

### Character Consistency

Characters are defined with structured appearance, attire, and behavior descriptions. Each character can have multiple variants (costumes, ages, disguises), and every variant can be rendered as a style reference sheet with turnarounds and expression studies.

<p align="center">
  <img src="docs/screenshots/character-vintage.jpg" width="220" alt="Character in vintage style" />
  <img src="docs/screenshots/character-watercolor.jpg" width="220" alt="Character in watercolor style" />
  <img src="docs/screenshots/character-anime.jpg" width="220" alt="Character in anime style" />
</p>
<p align="center"><em>The same character variant — "Brassic in gnome disguise" — rendered consistently across three art styles with turnaround poses and expression studies.</em></p>

### Dialog Styles

Each comic style includes distinct visual treatments for different dialog types — normal speech, whispers, shouts, thoughts, narration, and sound effects — generated as reference examples to lock in the visual language.

<p align="center">
  <img src="docs/screenshots/dialog-chat.jpg" width="220" alt="Chat bubble style" />
  <img src="docs/screenshots/dialog-thought.jpg" width="220" alt="Thought bubble style" />
  <img src="docs/screenshots/dialog-shout.jpg" width="220" alt="Shout bubble style" />
</p>
<p align="center"><em>Dialog style examples: chat, thought, and shout bubbles in vintage four-color.</em></p>

---

## Architecture

### AI-First Design

The application is built on the **OpenAI Agents SDK** with function-calling tools, not a simple chat wrapper. The coauthor is a **studio staff** — a fleet of context-specialized agents surfaced through named roles: the Editor on series and issues, the Layout Artist on scenes, the Penciller on panels, the Background Artist on settings, the Character Designer on the cast, the Cover Artist on covers, the Production Artist on inserts, the Librarian in the asset catalog, and the Art Director and Inker in the image editor. Under the hood that's **24 distinct agents presented as 10 studio roles**, each with:

- A **custom persona** with system instructions tailored to its role (story editor, character designer, cover artist, etc.)
- A **filtered toolkit** — only the tools relevant to the current context are available, preventing hallucinated actions
- **Full object context** — the agent receives the selected object's data, its place in the hierarchy, and the tail of the parent object's conversation, so a thread started upstairs continues downstairs

The agent who answers is picked by the **most-specific object in your current selection**. So you can say *"make the dialogue punchier"* while viewing a panel, and the Penciller knows exactly which panel, which scene it belongs to, what characters are in frame, and what the art style is — without you specifying any of it.

### 148 Function Tools

Tools cover the full CRUD lifecycle plus specialized creative operations. The agents share **148 function tools**, allotted per role:

| Category | Tools | Examples |
|----------|:----:|----------|
| **Read** | 24 | `read_scene`, `read_panel`, `read_series_bible`, `read_all_characters`, `read_board_table` |
| **Update** | 49 | `update_panel_dialogue`, `update_scene_cast`, `update_scene_blocking`, `move_panel`, `update_cover_letters` |
| **Imaging** | 28 | `generate_panel_image`, `generate_cover_image`, `generate_setting_background`, `inpaint_image_region`, `outpaint_image_region`, `split_layer`, `render_missing_panels`, `layout_issue_pages`, `export_issue_pdf`, `export_issue_cbz` |
| **Create** | 15 | `create_comic_series`, `create_issue`, `create_scene`, `create_scene_panels`, `create_character`, `create_variant`, `create_cover`, `create_insert`, `create_story` |
| **Delete** | 13 | `delete_panel`, `delete_scene`, `delete_character_variant`, `undo_last_delete` (all soft-delete to the wastebasket) |
| **Assets** | 11 | `create_prop`, `create_outfit`, `read_all_props`, `compose_character_variant`, `extract_outfit_from_variant`, `dedupe_props` |
| **Library** | 5 | `list_library_assets`, `import_character`, `import_setting`, `import_prop`, `import_outfit` |
| **Navigation** | 3 | `select_publisher`, `select_series`, `select_comic_style` |

### Studio Workspace UI

Built with **NiceGUI** (Python web framework), the interface follows a studio layout — one persistent room, structured editing on the left, the coauthor on the right:

- **Split view** — structured data editing on the left, AI conversation on the right, on a splitter you can drag
- **Splitting breadcrumb** through the creative hierarchy (Series › Issue › Scene › Panel); the first crumb is a split control that jumps to any of the four root rooms — Publishers, Series, Styles, Library
- **Command palette** (`Cmd`/`Ctrl-K`) that jump-searches every object in the studio; anything it can't match becomes a message to the current coauthor
- **The light table** — compose panels by laying character figures, backgrounds, props, and styles onto an acetate board
- **The layout swatch book** — bind an issue's panels to print-page layouts chosen from **354 exact-fill page tilings**, one hover away
- **The open book** — the issue view *is* the comic: side-by-side spreads that reflow continuously as you edit, read front-to-back in a dedicated reading room, and export to a print-trim **PDF or CBZ**
- **The wastebasket** — deletes are moves, not destruction; nothing paid-for burns, and the only true delete (a 30-day purge) asks first
- **Persistent per-object conversations** — every object keeps its own chat thread; leave a scene, come back, and the thread is where you left it
- **Reference image uploads** to guide AI generation with visual context
- **Voice input/output** — dictate instructions and hear AI responses
- **A running spend estimate** in the header, tallied per render, so you always know today's cost
- **Dark mode** with consistent theming

<p align="center">
  <img src="docs/screenshots/workspace.png" alt="Comic Studio workspace — split view with details panel and AI conversation" />
</p>
<p align="center"><em>The studio workspace: structured editing on the left, AI conversation on the right.</em></p>

---

## Data Model

Every entity is a Pydantic model with full validation. The hierarchy is navigable in the UI and understood by the AI agents. Records reference each other by id rather than by nesting, so reusable assets — settings, props, outfits, styles — can be shared across an entire series.

```
Publisher (brand, logo)
  └─ Series (premise, description, title masthead art)
       ├─ Characters
       │    └─ Variants (appearance, attire, behavior, age, race, worn outfit + props)
       │         └─ StyledVariant (one rendered reference sheet per comic style)
       ├─ Settings (reusable place; a master background rendered once per style)
       ├─ Props & Outfits (reusable wardrobe and dressing, each with reference art)
       ├─ Issues (story, metadata, credits)
       │    ├─ Stories (the script — one or more features/backups per issue)
       │    ├─ Scenes (narrative, setting, style, cast, props, blocking, mood)
       │    │    └─ Panels (beat, description, dialogue, narration, aspect, images)
       │    ├─ Pages (print layout — panels bound into a 6×10 grid of frames)
       │    ├─ Inserts (full-page non-story pages: posters, ads, pin-ups, mailbag)
       │    └─ Covers (front, back, inside-front, inside-back)
       └─ Comic Styles
            ├─ Art Style (linework, inking, color palette)
            ├─ Character Style (form, proportions, signature motifs)
            └─ Dialog Styles (six bubble types: chat, whisper, shout, thought,
                              sound-effect, narration)
```

A few things worth calling out, because they're what makes the art hang together:

- **Setting** is a reusable place — a saloon, a tent — described in enough detail that any renderer draws the same location, and rendered once per style into a **master background** that every panel in the scene composites over.
- **Panels compose on a light table.** A panel isn't a single prompt; it's a master background plus posed character *acetates* (figure cut-outs placed by percentage blocking) plus lettering — the same compositor drives the on-screen board, the merged render, and the final art.
- **Pages** are a separate layer from the story: scenes and panels are the *narrative*; a Page binds specific panels into a print layout on a 6-wide × 10-tall unit grid.
- **Inserts** are full-page interludes (a pin-up, an in-world ad, a letters page) anchored after a given scene.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12+ |
| **Package / Env** | uv (`pyproject.toml` + `uv.lock`) |
| **UI Framework** | NiceGUI 2.19+ |
| **AI Orchestration** | OpenAI Agents SDK (`openai-agents`) |
| **LLM** | GPT-5.2 (text generation, function calling, vision) |
| **Image Generation** | gpt-image-1.5 (generation, inpainting, outpainting) |
| **Data Validation** | Pydantic 2.11+ |
| **Image Processing** | Pillow 11.2+ |
| **Storage** | Local JSON + image files; each Publisher is its own git repo |
| **Logging** | Loguru |

---

## Creative Workflow

1. **Define your style** — Create a comic style with art, character, and dialog parameters. Generate visual examples to lock in the look.
2. **Build your cast** — Create characters with variants (costumes, ages, forms), composed from reusable outfits and props. Generate styled reference sheets for visual consistency.
3. **Build your sets** — Create settings for recurring places and render each one's master background per style, so the tent in panel 3 is the same tent in panel 9.
4. **Write your story** — Create a series and issue, and paste or develop the script with the Editor.
5. **Break it down** — Divide the story into scenes with narrative summaries, cast, and blocking. The AI can suggest scene breaks from your story.
6. **Panel by panel** — Define each panel's beat, visual description, dialogue, and narration. The AI drafts from scene context.
7. **Generate art** — Render panel images and covers. The system composites from structured data: the setting's master background, character reference sheets, posed figure acetates, style parameters, and any uploaded references. Renders run in a background queue that posts each finished panel into the chat while you keep working.
8. **Refine** — Use conversational image editing (inpainting/outpainting) to adjust generated art. Select finals from the image grid.
9. **Lay out and bind** — Bind panels to page layouts from the swatch book (splash pages, 2-up rows — pacing at the page turn), read the issue front-to-back in the built-in reader, and export a print-trim PDF or CBZ.

Every step is conversational. You're never filling out a form — you're talking to a collaborator who happens to have a structured understanding of your entire project.

---

## Getting Started

```bash
# Clone the repository
git clone <repo-url>
cd comics

# Install dependencies (uv creates and manages the virtualenv)
uv sync

# Set your OpenAI API key
echo "OPENAI_API_KEY=your-key-here" > .env

# Run the application
uv run python main.py
```

The app launches a local web server at **http://localhost:8080** (override with the `COMIC_STUDIO_PORT` environment variable). On first launch you'll be prompted to **found a publisher** — a self-contained git repo that holds your styles, characters, and issues.

See **[docs/getting-started.md](docs/getting-started.md)** for install and setup, then **[docs/users-guide.md](docs/users-guide.md)** — *Making Your First Comic* — for a step-by-step walkthrough from the empty studio to a printed book.

---

## Key Design Decisions

- **Conversation over configuration.** Every creative action flows through the chat. This isn't laziness — it's a deliberate choice to keep the creator in a flow state rather than switching between forms and menus.
- **Agents over endpoints.** Instead of REST APIs behind buttons, the system uses function-calling agents that reason about which tools to invoke based on natural language input and current context.
- **Style as a first-class entity.** Styles aren't filters applied after the fact. They're structured definitions (art, character, dialog) that propagate through every generation call, ensuring visual coherence across an entire series.
- **Reference images as creative guardrails.** Uploaded references and generated style examples are fed into every image generation call, giving the AI visual context alongside textual descriptions.
- **Composition all the way down.** A panel is composed from its setting's *master background* plus the cast's reference sheets — build the set once, reuse it across every panel so the tent in panel 3 is the same tent in panel 9. Variants are composed the same way: base character + outfit + props, never re-described. Every render reports exactly which references it's missing.
- **The coauthor remembers and speaks first.** Conversations persist per object (leave a scene, come back — the thread is where you left it; child agents inherit the parent discussion). Each view opens with a production-aware line and suggestion chips ("5 panels unrendered — want me to work through them?"), computed from cheap reads with no model call until you speak.
- **A studio, not a chatbot.** Assets — characters, looks, wardrobes, settings, props, styles — lay onto the light table from the bench's own pickers (each with a 'Borrow from another series…' door), the Library browses every house, and Cmd-K jumps anywhere. Batch renders run in the background, filing receipts in the daybook while you keep talking, with a running spend estimate in the header.
- **One wastebasket.** Deletes are moves, not destruction — everything goes to a `.trash` folder you can restore from. Nothing you paid to render is ever hard-deleted; the only true delete is a 30-day purge, and it asks first.
- **No database — every house its own repo.** A Publisher isn't a row in a shared database; there is no database at all. It's a self-contained git repository with its own styles, cast, and issues, and **you add a project by linking its repo in**. The app keeps a machine-local registry of your houses and repoints the `data` symlink at whichever one is open, so it only ever sees one publisher at a time. Your creative work lives entirely separate from the app code, and all project and file management — history, backup, sharing, collaboration — is handled through git and GitHub rather than a bespoke storage layer.
- **Every view is a URL.** Hierarchical routes (`/series/…/issue/…/scene/…/panel/…`) make every object deep-linkable, reload-safe, and multi-window friendly. Breadcrumbs, reloads, and command-palette jumps all walk the identical ancestry.

---

## Project Status

This is an active experiment in AI-first application design and collaborative creative workflows. The full loop — paste a story into an issue, get a script breakdown (settings, cast, blocking), panelize, render composited artwork, lay out pages, and export the bound PDF or CBZ — is functional and producing real output, with **128 tests across 27 modules** covering the pipeline (binder, compositor, stitcher, layout tilings, storage isolation, trash, the render queue, and more). It's not production software; it's a working exploration of what co-creation with AI can look like when the AI is treated as a peer rather than a tool.

---

## License

All rights reserved.
