# Comic Studio: The User's Guide

This guide walks you through a full working session: installing the studio, founding a publishing house, writing a script, breaking it into scenes and panels, drawing on the light table, binding the finished issue, and sharing the whole house with a co-author over git. Follow along in your own studio; every step here is something the app actually does.

Two facts to hold onto from the start:

- **Renders cost real money.** Image generation goes through OpenAI's gpt-image-1.5 model and every image is tallied in a spend ledger at `~/.comic-studio/spend.json`, with per-image estimates of $0.02 (low quality), $0.07 (medium), $0.19 (high). This guide marks which actions bill and which are free.
- **Deletes go to a wastebasket, not the void.** Almost everything you remove can be put back. The exceptions: burning the wastebasket pile (which asks you to confirm first) and striking a setting shot — both are called out where they appear. Even the purge of wastebasket entries older than 30 days is a manual, confirmed action: the wastebasket dialog offers an *Empty N 30-day-old entries* button that asks first. Nothing in the studio deletes on its own.

Comic Studio is local-first and single-machine: it runs on your computer, stores your work in ordinary folders and git repositories on your disk, and talks to OpenAI only when you ask it to think or draw.

## Contents

- [Installation and first run](#installation-and-first-run)
- [The lobby](#the-lobby)
- [Founding a house](#founding-a-house)
- [The wall](#the-wall)
- [A series and an issue](#a-series-and-an-issue)
- [The script](#the-script)
- [The open book and the detail dial](#the-open-book-and-the-detail-dial)
- [Panel shapes and the page flow](#panel-shapes-and-the-page-flow)
- [The series room: cast, settings, props, wardrobe](#the-series-room-cast-settings-props-wardrobe)
- [The light table](#the-light-table)
- [Covers](#covers)
- [Marks: the masthead and the logo](#marks-the-masthead-and-the-logo)
- [Full pages: turns, inserts, inside covers](#full-pages-turns-inserts-inside-covers)
- [Reading and binding](#reading-and-binding)
- [The wastebasket and the ways back](#the-wastebasket-and-the-ways-back)
- [The Editor](#the-editor)
- [Collaboration via git](#collaboration-via-git)
- [Limits](#limits)

---

## Installation and first run

You need Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd comics

# Install dependencies (uv creates and manages the virtualenv)
uv sync

# Set your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env

# Run the application
uv run python main.py
```

The app serves a local web page at `http://localhost:8080` (set `COMIC_STUDIO_PORT` to change the port). The `.env` file sits beside the app and is never committed — the studio's `.gitignore` excludes it.

If the key is missing, the studio still opens, but an amber banner above the input reads:

> The studio needs its OpenAI key before the coauthors can speak or draw — put OPENAI_API_KEY=sk-… in a .env file beside the app and restart.

Everything file-based still works without a key; anything that needs the model to speak or draw does not.

---

## The lobby

On first run, with no publishing house anywhere, the lobby shows a single line — *"Every comic starts with a conversation."* — and two buttons:

- **Found your publishing house** — opens the founding dialog (next section).
- **Adopt the demo house** — builds a small, complete example house you can explore.

### The demo house

Adopting the demo founds **Foglamp Press** at `~/git/foglamp-press-comics` — a real git repository with the studio's default styles copied in — then writes a publisher description and logo brief, a series called *the-lighthouse-post*, and an issue, *the-fog-edition* (issue #1, in the vintage-four-color style, with a full story script already written and no publication date).

Adopting the demo bills nothing. It is entirely file and git operations; no image is rendered and no model is called. After adoption the wall repaints in place — nothing redirects you anywhere. If `~/git/foglamp-press-comics/publishers` already exists, adoption refuses with a notice that the house already stands, and does nothing.

The demo issue arrives with a script but no scenes, panels, or art — deliberately. It is the raw material for exactly the walkthrough in this guide.

---

## Founding a house

A **publishing house** is where your work lives: one self-contained git repository holding a publisher record, series, issues, styles, prompts, and references. The registry of houses on your machine lives at `~/.comic-studio/publishers.json`; the repositories themselves live wherever you put them.

**Found your publishing house** opens a dialog titled *A NEW PUBLISHING HOUSE*. It asks for a name and a folder:

- On macOS, **Choose a folder…** opens the native folder chooser.
- On other platforms (or if the native chooser is unavailable), a manual **Folder path** input appears. A path that does not exist yet is accepted — it will be created when you found the house.

What happens to the folder depends on what is in it:

- **Empty or not yet existing** — the house is founded directly in it.
- **Occupied, but not a house** — a child repository named `<slugified-name>-comics` is created inside it.
- **Already a house** (it has `publishers/` plus `series/` or `styles/`, with a readable publisher record) — the button changes to **Adopt this house**, and clicking it only registers the existing repository. No git init, no style copying; the house joins the rack as-is. This is also how you join a house a co-author cloned for you — see [Collaboration via git](#collaboration-via-git).

Founding copies **styles, prompts, and references** into the new house from the first available source: your own template at `~/.comic-studio/templates/house`, else the first registered sister house, else the app's bundled templates. If no source exists at all, founding refuses with an error — *"cannot found a house without its styles"* — before anything is registered.

The new repository gets:

- A `.gitignore` keeping working scratch out of history: `.trash/`, `.queue/`, `.spend.json`, `**/exports/`, `**/.trash--*`, `.DS_Store`.
- `git init -b main` (only if no `.git` exists already), then a founding commit: *"FOUNDING THE HOUSE: \<name\> — the studio's default styles, prompts and references, ready for its first series"*. If you have no git identity configured, it commits as `Comic Studio <studio@comic-studio.local>`. A failed founding commit only logs a warning — the house registers regardless and can be committed later.

Behind the scenes the studio mounts each registered house as a symlink `data/<slug>` pointing at the repository (the slug is the folder's basename). Registration is deduplicated by path; a house whose folder is moved or deleted silently vanishes from the wall rather than erroring. Removing a house from the rack (**retiring** it, from the publisher room's delete button) only unregisters it — the repository on disk is never touched, and it can rejoin any time through the found dialog.

---

## The wall

The home view is **the wall**: one row per house.

- **The house card** (with its logo, or its name if there is no logo) opens the publisher room, which holds the series wall and the style rack. A house without a logo shows a small brush button — *"No logo yet — describe one and the house gets its mark"* — which creates a square logo board and takes you to it. Creating the board is free; nothing renders until you ask.
- **Series cards** show the series masthead art if any exists, or the series name with a brush button that creates a masthead board.
- **Issue tiles** are sorted by issue number and show the front cover (falling back through inside-front, inside-back, back), or a `№ n` label if no cover exists yet. An issue with a publication date wears a **PUBLISHED** ribbon. The issue you touched most recently is where the studio picks up when you return; its tooltip shows what you were last working on.
- **Ghost doors**: each series row ends in a `+` tile that prefills the chat input with *"Create the next issue of \<series\>: "* — it writes nothing itself; you finish the sentence and send. Each house column ends in **+ new series**, and the wall closes with **+ found a house**.
- **The sync glyph**: houses that are git repositories get a small sync button on the house card, with an orange badge counting uncommitted changes plus commits to push and pull. This is the collaboration door; it is covered in full at the end of this guide.

Nothing on the wall bills OpenAI. Founding, adopting, syncing, navigation, and brush-button board creation are all file and git operations.

### The style rack

Every render, setting master, and reference sheet in the studio is keyed by a **style**, so the rack matters even though you may rarely visit it. It holds the house's own copies of the default styles, plus any you mint. The rack's `+` opens a New style dialog with two paths:

- **Describe it** — the style is created from your written description.
- **From art** — drop a piece of previous art; the studio reads the style off the picture and keeps the image as the style's **exemplar** (the reference its future art is held to).

Neither path renders anything — nothing bills until you ask for renders in that style.

### The command palette

From anywhere, **Cmd/Ctrl-K** opens the command palette: type a few letters and jump to any object across every mounted house — publishers, series, issues, scenes, characters, settings, styles. A query the palette cannot match is handed to the Editor as an ordinary message.

---

## A series and an issue

You create series and issues by asking your coauthor — **the Editor**, the conversational partner that lives in the input box at the bottom of the screen. (The Editor gets its own chapter later; for now, know that it is one agent that carries the studio's full toolset, and its instructions are rebuilt each turn to name the room you are standing in.)

Click a ghost door — **+ first series** on your new house — and the input fills with *"Create a new series for \<house\>: "*. Finish the sentence with a name and a premise, press Enter, and the Editor creates the series record. Then the series row's `+` tile prefills *"Create the next issue of \<series\>: "* the same way.

An issue can hold one story or several. An **issue** with multiple **stories** is an anthology; each story carries its own writer, artist, and letterer credits.

Click an issue tile and you are in **the open book** — the issue view, which is the comic itself, laid out as pages. Everything from script to press happens here or one click away from here.

---

## The script

At the top of the open book is the masthead: the issue title, a style swatch, a row of dial chips, a tune button, **Read**, and a delete button. The dial is covered in the next section; start at its first stop, **SCRIPTS**.

The book shows a manuscript sheet titled **THE SCRIPT**, backed by the issue's own script text (an issue with multiple stories shows one sheet per story). Under the title is the byline — *"by — · art — · letters —"* until credits are set; clicking it asks the Editor to set them.

To write, click the sheet's edit control. Editing in this studio does not open a modal editor — **the conversation box is the editor**. The box fills with the current text behind a `Title:` prefix, and a notice explains the contract: *Enter saves; Shift+Enter for a new line; clear the line to change the subject.* If you send with the prefix intact, the text saves directly — no Editor turn, no model call, no cost. If you erase the prefix, whatever you type goes to the Editor as an ordinary message instead. This same mechanism edits beats, scene text, story text, insert notes, poses, and briefs throughout the studio.

Scripts longer than 200 words never scroll on the sheet — they clamp with a fade and a *"continues — open to read"* chip that opens the full text.

Each story sheet ends in a foot chip that matches where the story stands:

- Under 80 words: **develop it with me** — an Editor interview to grow the idea.
- Text but no scenes yet: **break into scenes** — the Editor breaks the script into scene records.
- Text and existing scenes: **re-break: update the scenes** — the Editor merges changes into the existing scenes in place, never duplicating them.
- No text: **write it with me**.

The last sheet carries **+ story** and **+ insert** chips. Stories reorder with `‹ ›` (single steps); tearing a story out is a request to the Editor, not a silent delete.

Every mutation in the book leaves a **receipt** — a brief notice in the corner of the screen naming what changed and where. Receipts persist in the conversation's record but are not shown in the chat pane, which stays a conversation; the Editor's own tool work does appear there, as the receipt rows described in [The Editor](#the-editor). Receipts are the studio's paper trail; recovery is through the wastebasket, not receipt-level undo.

---

## The open book and the detail dial

The book has five dial stops, rendered as chips in the masthead:

| Stop | What each panel or scene shows |
|---|---|
| **SCRIPTS** | Manuscript sheets — one per story |
| **SCENES** | One manuscript page per scene, with its production strip |
| **BEATS** | Panel tiles showing each panel's written beat |
| **ROUGHS** | Panel tiles showing the rough — the composed layer stack — with a ROUGH tag |
| **PROOFS** | Panel tiles showing the finished rendered image, or a "no proof yet" placeholder — never the rough |

A **beat** is the written description of what one panel shows. A **rough** is the panel's working composition — layers arranged on the light table. A **proof** is a finished render you have chosen to feature.

The dial position and your reading spot are remembered in memory only — both reset when the app restarts. Flipping the dial reopens the book at the top unless a door (from the dashboard, a chip, a tile) set a destination first.

Pages use a real comic trim of 6.625 × 10.1875 inches with a 6 × 10 unit live area; the difference breathes as margins. Only content sheets carry a folio (page number), so the numbers on screen match the numbers in print.

The book renders in imposition order: front cover, inside-front, the stories, the interior pages, any orphaned inserts, inside-back, back cover, and the colophon. The closing pair always holds together; an odd interior leaves one blank slot rather than shifting the covers.

### Scenes

At the **SCENES** stop, each scene is a manuscript page: its text (clamped past 200 words), move and edit controls, and a **production strip**:

- A **setting chip** (amber while unset) opens a picker of the series' settings; choosing writes the scene's setting.
- A **cast chip** opens a character-and-look picker (a **look** is a character's dressed variant — outfit and props; the series room chapter covers them); choosing adds that cast member to the scene. Existing setting and cast render as removable chips — the `×` writes the scene, the chip itself visits the asset.
- An orange **panels** chip appears while the scene has no panels; clicking asks the Editor to break the scene into panels.

A scene's `‹ ›` arrows move it a single step; deleting a scene is always a request to the Editor.

### Beats and slips

At **BEATS**, scenes that have panels show their panel tiles; scenes that do not show **manuscript slips** — two or three scene texts per sheet. A slip with 25 or more words offers **break into panels**; a thinner one offers **develop it with me**.

Each panel tile carries:

- The beat text (or *"unwritten panel"*).
- A **scene cap** on the first tile of each scene's run — `<n> · <NAME>` — carrying the scene menu (open, move, add a panel, delete).
- A pencil: **Rough it** while the panel has no layers; the moment a rough exists the button becomes **Proof it** (a brush). A click can never clobber a rough. The pencil does not render in the book — it opens the panel's light table and starts that table's own flow there: rough-building if the panel has no layers, proofing if a rough exists. Costs are quoted on the table itself.
- A tile menu with the shape picker, `◂ ▸` move within the scene, **Edit the script…** (the intercept editor on the beat), **Re-rough** (only when a rough exists, behind a confirm dialog — rebuilding re-poses the cast and redraws hand-arranged layers), and **Tear this panel out…** (an Editor request).

Clicking anywhere else on a tile opens the panel's light table.

---

## Panel shapes and the page flow

The book lays out pages automatically. Panels flow continuously into gapless pages on the 6 × 10 grid; the layout engine tries an **exact fill** first, and when that is impossible it falls back to band packing and shows a non-blocking amber banner naming the reason — *"Couldn't make an exact-fill layout — \<reason\> … release a lock or move a panel to fix it."* The note is transient and clears itself on the next clean flow.

### Hold and auto

Every panel has a shape: an aspect (square, landscape, portrait) and a size. The **shape picker** (in the tile menu and on the light table) offers seven boxes, generated from the layout engine's own law: square at 2×2, 4×4, and 6×6 (full-width square), landscape at 3×2 and 6×4, portrait at 2×3 and 4×6. No 6×10 panel shape exists — the page is 6 × 10, and the biggest boxes are 6×6, 6×4, and 4×6.

- Picking a box **holds** the shape: the flow must honor it.
- **Auto — let the flow shape it** releases the hold: the flow may flex the panel to make the page fill exactly.

The picker header tells you both truths: *"held at \<aspect\> \<size\>"* when locked; *"auto · laid X (asked Y)"* when the flow flexed an unlocked panel. The lit box is the shape actually on the page.

Reshaping has one consequence to know about: if a reflow changes a panel's laid orientation so it no longer matches its featured proof's drawn orientation, the proof is quietly unselected. The **take** — any render the panel has produced; takes collect on a wall below the light table, covered in that chapter — stays put; nothing paid-for is lost. A receipt names each one: *"🫙 \<name\> lost its proof — re-proof it or feature another take."*

### The swatch book and pins

The page tools include a **swatch book**: every exact 6 × 10 tiling with exactly this page's panel count (354 canonical tilings exist; exact fills exist for 4 to 15 panels). Picking a swatch **pins** the page — each panel takes its piece's shape, and the page holds that layout verbatim until you release the pin with the push-pin button. A pin whose panel is deleted dissolves on its own.

### Layout feel

The masthead's tune button opens a per-issue dialog: a **Layout by scene** switch (start each scene on a fresh page run) and four sliders — density, verticality, irregularity, variety — that bias the flow. Individual scenes can carry their own feel override.

All layout work — shapes, holds, pins, swatches, feel — is free. It is pure computation and storage writes.

---

## The series room: cast, settings, props, wardrobe

Before panels can be drawn, the series needs its assets. The series room is one mosaic holding only what the series owns: a description, the masthead tile, and four walls — **characters**, **settings**, **props**, and **outfits**.

Each wall's caption carries a `+` opening the shared create dialog, with three tabs:

- **Describe it** — posts one instruction to the Editor to create the asset *and render its reference art* (a character base sheet, a setting master, a prop or outfit reference). This path leads to a billed render.
- **From an image** — the dropped image is saved into the house first, then the Editor is asked to create the asset from it, keeping the image as its **exemplar** (the reference every future sheet is held to). Reading the image uses a text/vision model call; *nothing renders yet* — style art inks on demand.
- **Copy an existing one** — derives a new asset from a source plus a "what's different" note.

Every wall also has a drop card — *"Drop an image to create a …"* — that does the from-an-image path in one gesture.

**Characters** have **looks** (variants): the base look plus any combination of outfit and props, composed in the **Compose a look** dialog on the character page. Composing is free; the reference sheet render that follows is billed. The character page also lists everywhere the character appears, and its delete button is usage-aware: a character cast in any scene routes deletion through the Editor; an unused one strikes straight to the wastebasket.

**Settings** hold **master backgrounds** — the empty set, rendered once per style and orientation (a billed high-quality render) — and **shots**, named reframings (angle, time of day) rendered from the master. Two useful distinctions:

- **Reframe to \<orientation\>** is free: a live pan-and-zoom crop of an existing master, no model call.
- **Ink a \<orientation\> master** is a new billed render.

One caution: striking a shot is *not* wastebasket-backed — it is the rare removal with no way back.

**Props** are never stamped into scenes; a prop reaches a panel only when you lay its art on that panel's light table. **Outfits** describe attire; editing an outfit's description re-dresses only the looks that still wear it verbatim — hand-tuned attire is never overwritten.

Assets can also be **imported** from another series by asking the Editor: imports copy the asset with provenance stamped on it, carry a character's wardrobe along, and never render anything.

---

## The light table

Click any panel tile and you are at **the light table** — the drawing bench. Covers, inserts, and marks (mastheads and logos) all use this same bench; what follows applies to all of them unless noted.

The board's working image is built from **acetates** — transparent layers stacked like sheets of film on a light table: the setting plate at the bottom, figures and props above it, letters on top. The stack column beside the canvas lists every acetate in z-order.

### The setting plate

The background is never stamped automatically. The **Lay the background** control writes the scene's setting and lays its master as the bottom plate. If the setting has no master in the board's style yet, a high-quality master render is queued and the plate lays itself when it lands. The background row in the stack offers: swap the setting, **Dress the setting** (light, weather, angle — one billed medium-quality edit), split the plate into elements, the healing bench, and removal.

### Casting and posing

The figure picker lists the scene's cast and their looks; laying a figure adds it to the board and immediately queues a **pose** — one billed medium-quality render that draws the figure in the described attitude. Unposed figures show as dashed silhouettes on the rough; click one to pose it. Posing uses the conversation-box intercept: the box fills with a pose prefix, Enter sends the direction, an empty direction means *let the script decide*. One pose per figure runs at a time; a second ask while one is pending is refused.

A figure's thumbnail click swaps its wardrobe among the character's looks; the swap changes only the art — the figure keeps its position, grouping, and blocking under the new look. A brush button appears when a look has no reference sheet in the board's style — clicking asks the Editor to ink one (billed).

### Arranging acetates

Direct manipulation on the canvas, all free:

- **Drag** to move — the grab works through transparent pixels, and a ~3-pixel threshold means clicks never displace anything. Positions snap to thirds, center, and baseline (hold Shift to skip snapping).
- **Ctrl/Cmd + wheel** resizes the selected acetate (15–140% of the canvas; letters resize their font instead).
- **Alt + wheel** or **[ ]** tilts in small steps (Shift for larger); letters never tilt.
- **Arrow keys** nudge 1% (Shift: 5%). A plain wheel always scrolls the page.
- **Cmd/Ctrl + Z** walks back through the last 60 moves. **Esc** deselects.

The first time you select an acetate, a placard shows this cheat sheet for eight seconds.

Every gesture persists to the board as it ends; if the connection to the server drops, the table freezes rather than letting you make edits that cannot save, and reloads when the line comes back.

Each stack row offers an **eye** (show/hide), a **padlock** (pinned acetates refuse drags, wheel, and nudges), and a **mirror** (flip horizontally — the renderer often gets facing wrong, and the flip is free). Rows drag to reorder the z-stack; dropping one *onto* another forms a **group**, which can be renamed, hidden, pinned, or **flattened** into a single acetate — note that flattening discards hidden members.

**Elements** — props and cut-out pieces — can be renamed, posed, duplicated, split into their own sub-elements, linked to a cast member (*"Who is this?"* turns a cut-out into a proper figure acetate), or sent to the healing bench. An element with an opaque backdrop shows an orange cut-out button: one billed medium-quality edit that produces a transparent cut-out, leaving the original file untouched.

### Letters

Any board with dialogue gets **letters**: balloons, captions, and (on mailbag inserts) text blocks, each a draggable acetate. Balloon tails are draggable; thought balloons trail three circles, sound effects have no tail. The rough shows up to 4 balloons, 2 top captions, and 1 bottom caption.

Double-click a letter to edit it in place; Enter commits straight to the panel's dialogue. New balloons and narration come from the letters dialog; a balloon can be handed to another speaker or switched in emphasis from its menu. Removing a balloon backs the board up to the wastebasket first. All lettering work is free.

### Trade dress

**Trade dress** is the publication furniture: credits, issue number, price. Front and back covers wear all three, panels wear credits only, inside covers and inserts wear none. The text prints from the issue record — toggling dress on stamps the issue's current metadata, and each repaint refreshes it. If the metadata is unset, the studio tells you to fill it on the issue's colophon first. Double-clicking a dress stamp never edits in place; it prefills the conversation with an update request, because the dress belongs to the issue, not the board.

### The brief

Below the rough sits **the brief** — the board's written instruction to the renderer. The pencil beside it fills the conversation box with `The brief: <current text>`; Enter saves directly (the old brief is backed up first), no Editor turn, no cost. On marks the label reads *"The lettering brief."*

### Roughing: building the table from the brief

The **build the table** button reads the brief (the beat plus the description) and lays the table for you:

1. An empty brief refuses with a warning — there is nothing to build from.
2. A **brief gate** (a text-model call) assesses whether the brief is thin. It fails open — if the check itself errors, work proceeds. A thin brief offers three doors: *Flesh it out together* (a billed Editor turn), *rough it anyway*, or *Not now*.
3. A breakdown call produces a checkbox plan: the setting (or a new one, created with its master queued), each figure with a pose line, elements conjured as props, the masthead on covers. Wardrobe comes from the scene's cast; a figure with several looks and no casting choice gets a mandatory picker and is skipped if you choose none.

Confirming the plan lays the acetates and queues the renders it needs.

### Proofing and takes

**Ink this rough** sends the composed board to the renderer — one billed high-quality render through the render queue. A bare board with a written brief proofs directly from the brief; a bare board with no brief refuses.

Every render that lands becomes a **take** on the **takes wall** below the board — every image the board has ever produced, each framed by its own measured orientation. Clicking a take **features** it: it becomes the board's proof, wears a green ✓, and the table locks (so a stray drag cannot desynchronize the layers from the print). Each take offers four buttons: tear up, rework on the table, explode, and heal.

- **Tear up** moves the file to the board's torn-up pile — recoverable.
- **Rework on the table** lays the take down as the background plate and unlocks the table, so you can draw over your own print.
- **Explode** lays the take as a plate and opens the **split flow**: a vision call (about ten seconds) reads the image against the series cast; recognized members land as proper figure acetates, anything else can be named by hand. Confirming queues the cut-out renders, and the count — *"N+1 renders"* — is announced the moment they queue: your checked boxes plus one repaint of the source layer, each medium quality.
- **Heal** opens the healing bench (below).

While a proof is featured the table is locked: the stack dims, drags are refused, and the lock row offers **Edit in layers** (lay the print down and unlock, one click) or **Unlock** (clear the featured proof; the take stays on the wall).

**Clear the board** (available only unlocked) backs the whole record up to the wastebasket, then empties every layer, letter, and cast reference; only the featured print survives.

The **flatten** dialog composites the visible acetates (letters last, in comic-craft order) into a single image and saves it as a new take, a reference on the board, or — when the board has a setting and style — the setting's master background.

You can also **drop or paste an image anywhere**: on a board, a dialog offers three destinations — a take (features immediately), the background layer, or a pinned reference. Off-board, the image files as a reference and a note goes to the Editor (a billed turn).

### The style swatch

A swatch taped beside the rough shows the board's style; clicking opens a picker of every style in the house. For panels the style belongs to the scene — the swatch says so: *the whole scene wears it*. Swapping is free and affects only renders made afterwards; existing art is untouched.

### References

Reference images pinned to the board (up to four show on the rough) steer its renders. One known defect in the current tree: the *"…or drop a reference image"* row on the table does not actually save the file — use the paste/drop dialog's "reference pinned to the table" destination instead until it is fixed.

### The healing bench

The heal button on any take or acetate opens the **healing bench**: the image on a dark stage. Drag a marquee over the flaw, then:

- **Heal the patch** — inpaints the marked region. No marquee means the whole image is fair game.
- **Extend the paper** — outpaints, growing the image about 256 pixels on every side (the marquee is ignored).

The bench works through the conversation: pressing either button sends your instruction to the Editor (one Editor turn), whose tool makes a single image call returning **four high-quality takes** at once — billed as four high renders, ~$0.76. They open in the **choices sheet**: the original is pinned first and keeping it is a first-class pick. **Paste it down** backs the original up to the wastebasket first, then overwrites it in place — on transparent acetates the original's transparency survives outside the healed patch. Whether you apply or cancel, the unpicked takes go to the wastebasket, not the fire: nothing paid-for burns. If the app crashes with choices unclaimed, a recovery chip on the bench reopens the sheet.

### Costs on the table

| Action | Cost |
|---|---|
| Drag, resize, tilt, nudge, eye, pin, mirror, reorder, group, flatten, duplicate, rename, letters, dress, tear up, restore, clear, feature/unlock, lay existing art, drop/paste | Free |
| Pose a figure or prop; dress the setting; make a cut-out | 1 medium render (~$0.07) each |
| Split a layer into N elements | N+1 medium renders — your picks plus one repaint of the source layer; the count is announced as they queue |
| Proof a panel, cover, insert, or mark; ink a setting master | 1 high render (~$0.19) |
| Heal or extend | 1 call returning 4 takes, billed as 4 high renders (~$0.76), plus 1 Editor turn |

The generated images come in three sizes only — 1024×1024, 1536×1024, and 1024×1536; the studio picks the one matching the board's orientation.

### The render queue

Renders run in background batches. Jobs within one batch run one at a time, in order, and the batch gets a queue line showing progress per piece with two controls: **HOLD** finishes the piece in hand and then waits; **STOP** sets the rest aside. Batches started separately — a pose queued while a proof batch runs — run alongside each other, each with its own line, HOLD, and STOP. Each queued render writes a docket slip (under `~/.comic-studio/queue`) so a restart can report work that died. A failed render is reported with its reason. If OpenAI reports you are out of credit, the studio says so once — in plain language, pointing at your billing page — and stops the rest of the batch rather than failing them one by one.

---

## Covers

An issue has four cover slots: front, inside-front, inside-back, back. In the book, a cover with art prints it full-bleed; a cover object with no art yet shows as a ghost — *"bare board — open its light table."* Either way, clicking opens the cover's light table, where everything above applies, plus:

- A **title** button lays the series masthead art as an element (if the series has no masthead art yet, the studio tells you to letter it first).
- A **publisher mark** button lays the house logo the same way.
- Front and back covers wear full trade dress.
- Covers get a simple landscape/portrait frame toggle rather than the panel shape picker.

With no cover object at all, the front and back slots show **+ front cover** doors that ask the Editor to create one; the inside slots offer a choice of cover art or an insert placed there. Note that an insert located at an inside cover prints *in place of* any cover art in that slot.

---

## Marks: the masthead and the logo

A **mark** is a piece of standing art — the series masthead (its logo-type) or the publisher's logo — composed on an art board on the same light table. Marks use the lettering brief, offer a square frame, wear no trade dress, and their takes wall shows the mark's whole history: takes from every style's board plus older art, each labeled with its style or *"earlier work."*

Featuring a mark **writes it home**: a masthead take lands on the series record (keyed by style), a logo take becomes the publisher's image — the receipt reads *"the mark is featured — it now hangs where it belongs."* The wall, covers, and title button all read from those homes.

---

## Full pages: turns, inserts, inside covers

Between story pages you can bind in full-page material — **inserts**. Six kinds exist: **poster**, **ad**, **pin-up**, **mailbag**, **title-page**, and plain **page**. The book's own chips offer the four named kinds, and the page-turn bar lays a plain page; a title-page is created by asking the Editor.

- A transparent **page-turn bar** rides the bottom edge of every content sheet. Clicking it lays a bare insert page at that spot — a free, local write; nothing renders and no Editor turn is spent.
- The **+ insert** chip and the inside-cover menus offer the four named kinds.

An insert sheet shows its rendered art if it has any; else its description, styled as manuscript; else a ghost with its kind's icon. You can:

- **Drop an image file anywhere on the sheet** — it becomes the insert's art directly.
- **Ink it** — the brush appears only while the insert is unrendered, and it is the book's only direct render button: one billed high-quality render through the render queue.
- Edit the notes (intercept editor), move it with `‹ ›` (the stride matches the dial: whole stories at SCRIPTS, single scenes elsewhere), open its light table, or strike it with `✕` — inserts are the one thing the book deletes directly, straight to the wastebasket.

Inserts placed at an inside cover get a release button that returns them to the page flow. An insert whose anchor scene no longer exists is never lost — it renders at the back of the book, before the inside-back cover, until you re-place it.

---

## Reading and binding

**Read**, in the masthead, opens the bound reading room in a new browser tab — real spreads, as a reader would see them. The PROOFS dial stop shows per-panel tiles, not the bound spreads; Read is where the book becomes a book.

**Binding** exports the issue. The **bind it** chip on the colophon asks the Editor to export a PDF (an Editor turn, not a silent button); CBZ export works the same way by asking. Finished files land in the issue's `exports/` folder, and the colophon shows a chip for the newest PDF and CBZ. Each chip reports its age: a file bound before your latest changes reads **· stale**, and one whose bind metadata is missing reads **· old bind**. The bind chip's tooltip also warns you when the book is not press-ready: unproofed panels bind as roughs or named boards, and placeholder lettering stays off the page.

Exports are per-machine — the house `.gitignore` keeps `exports/` out of git, so each author binds their own copy.

### The colophon and the production dashboard

The last page of the book is the **colophon**: the credits, publication date, and price (each reading *"unset — pencil it in"* until set; clicking a line asks the Editor to edit it), the download chips, and the **production dashboard** — the issue's production ledger made visible.

The **production ledger** is the running account of what stands between the issue and press; its one-line summary (*"press-ready"* or *"N things before press"*) also rides the wall tooltip. The dashboard breaks it into eight stages in production order: stories scripted, scenes created, beats created, layout completed, panels roughed, panels inked, covers roughed, covers inked — each with counts and a bar. An empty stage is *not started*, never complete. A stage that is started but unfinished is a door: click it and the book opens at the right dial stop, scrolled to the first thing that needs you. Below the stages, a story-by-story breakdown and any loose ends — letters unplaced, script drift (the script changed after its breakdown, so the scenes still follow the old text until you re-break), insert gaps — are doors too.

---

## The wastebasket and the ways back

Most removals in the studio are recoverable. The mechanisms, and the exceptions, in one place:

- **Soft deletes.** Deleting an object moves it into the house's `.trash/` with a manifest. The Editor's `undo_last_delete` restores the most recent entry, but recovery is not limited to that: a header control opens **the wastebasket dialog**, listing every entry across every mounted house with day captions and a name filter (once the pile passes eight entries). Any entry can be put back from there. When entries older than 30 days exist, the dialog offers an *Empty N 30-day-old entries* button — the studio's only true delete, behind a confirm (*"GONE FOR GOOD?"*); everything younger stays, and nothing purges without you.
- **The torn-up pile.** Takes, acetates, and references torn up on a light table are renamed in place with a trash prefix. The board's wastebasket chip lists them; **Put it back** restores. An acetate restoring into an occupied spot swaps with the current occupant, which is counter-wastebasketed; a take or reference restores beside the occupant under a fresh name. Either way nothing is clobbered. **Empty the pile** demands a confirm (*"Burn them"*) and has no way back.
- **Snapshot insurance.** Before every destructive edit — clearing the board, dropping a balloon, uncasting a figure, removing an element, dissolving or flattening a group, rewriting the brief — the board's record is backed up to the wastebasket first.
- **The choices sheet** backs the original up before pasting a heal down, and soft-deletes the takes you did not pick.
- **Restore discipline.** Restores refuse to land outside their own house.

Two exceptions, stated plainly: striking a setting **shot** is not wastebasket-backed, and the page-layout records the book rewrites on every paint are derived data, hard-deleted by design (your panels and pins are not — only the computed flow).

---

## The Editor

The conversation box at the bottom of every room talks to **the Editor** — one agent, carrying all 157 of the studio's tools, wearing a different hat depending on where you stand. Its instructions are rebuilt every turn from: the room's persona, the studio's standing rules, your position (the selection trail — the ids that "this" and "here" refer to), the full roster of every house, series, and issue on your wall, and the object in your hand.

Its standing instructions, rebuilt into every turn, are worth knowing — they are instructions to the model, not code-enforced guarantees:

- **It is told to speak only done work** — to claim a change only when a tool call that turn made it. The receipts are how you check: a claimed change with no receipt is a violation.
- **The production ledger is the truth** — status questions are answered by reading, not remembering.
- **It stays where you stand** — it never navigates you unless you ask.
- **A bare "yes" with nothing pending gets a question, not action.**

The Editor's memory is one thread that persists across rooms and restarts (trimmed to recent turns; when you walk between rooms, a note of the walk goes into the thread so it knows where you went).

### Receipts and the work line

Every tool the Editor uses posts a receipt row — a verb emoji, the tool, and up to three of its arguments; reads are gray and quiet, mutations are not. The turn's receipts collapse into one work line: *"worked — N steps · M pieces inked."* A tool answer that includes an image shows a thumbnail. While the Editor works, a ticker cycles hand-lettered verbs (*penciling… inking… lettering…*), pinned to the truth of whatever tool is actually running.

### The STOP door

You can stop the Editor mid-turn, three ways: the stop button in the header (visible only during a turn), the stop icon riding the live work bubble, or typing a stop word — `stop`, `cancel`, `halt`, `abort` and their variants. The stop note states the limit plainly: *"🛑 Stopped at your word — a render already on the wire may still land on the board."* A stopped turn leaves a memo of what got done, so *"go on"* resumes without re-billing finished work. Likewise a failed turn: *"That turn failed — … Say try again,"* and a turn that runs out of steam invites *"go on."*

While a turn runs, a new message queues (*"Queued — I'll take that up the moment this reply lands"*) and sends itself when the turn ends — without clobbering anything you were drafting.

### Costs and quotes

What an Editor turn costs:

- **The turn itself** is a text-model call (gpt-5.2) — billed API usage, but not an image render.
- **Image renders** the Editor performs are billed like any other: $0.02 / $0.07 / $0.19 estimated per image at low/medium/high quality, tallied per day per quality in the spend ledger at `~/.comic-studio/spend.json`.
- **The header carries a spend meter** — today's render count and estimated dollars (🎨 N · ~$X.XX), refreshed every fifteen seconds. Clicking it opens a receipts dialog breaking today's spend down per quality, with the caveat the dialog itself states: estimates at published image rates — the invoice is the truth.
- **Larger jobs are announced** — the build-the-table plan lists its renders before you confirm, the split flow announces its render count as it queues, the brief gate offers a way out, and the queue reports each outcome.
- **What never costs a turn:** intercept saves (the prefix-intact edits described throughout this guide), all direct manipulation, moves, pins, casting, insert creation, drop-art, strikes, and restores.
- **What does cost a turn:** chips that fill and send the chat box — breaks, deletes, credits, covers, bind, develop — and the healing bench's two buttons, which send your instruction to the Editor. One Editor turn each.

If your OpenAI account runs dry, the studio reports it once in plain language and stops the batch.

---

## Collaboration via git

A house is a normal git repository, so two authors collaborate the way two developers do — except the studio does the git for you, through the **sync glyph**.

### Author A: the first push

Your house has been a git repository since founding, with a founding commit already made. Give it a remote once, in a terminal:

```bash
cd ~/git/foglamp-press-comics
git remote add origin git@github.com:you/foglamp-press-comics.git
```

Then click the sync glyph on the house card. Until a remote exists, sync commits your work and says so: *"🏠 no remote — the work is safe in the house repo (add one with `git remote add origin …` to sync it out)."* With the remote set, the same click pushes everything up.

### Author B: clone and adopt

Your co-author, on their own machine with their own studio installed:

```bash
git clone git@github.com:you/foglamp-press-comics.git ~/git/foglamp-press-comics
```

Then, in their studio: **Found your publishing house** → choose the cloned folder. The dialog recognizes it as an existing house and the button becomes **Adopt this house** — clicking it only registers the repository on their rack. No re-initialization, no style copying; they see the same wall, series, and issues you do.

### Working and syncing

Both of you work normally. The sync glyph appears on every house that is a git repository, with an orange badge totalling changed files, commits to push, and commits to pull. Its tooltip says exactly what a click will do: *"Sync the house — commit, pull & push (N changed, N to push, N to pull),"* or *"everything is committed and pushed."*

One click runs three steps in order, each reported as a receipt tagged with the house name:

1. **Commit** any dirty work. The commit message is written by the studio in the studio's nouns — *"STUDIO SYNC: 3 panels, 1 cover, 2 characters — The Lighthouse Post"*, with a dated body — by folding changed files into the objects they belong to. If no git identity is configured, it commits as `Comic Studio <studio@comic-studio.local>`.
2. **Pull** with `git pull --rebase --autostash`.
3. **Push.** Success ends *"☁ pushed — the house is synced."*

Each step stops the chain if it fails, and says so: a pull failure reports *"⚠ pull hit trouble: … — the repo is untouched beyond the commit; resolve and sync again"* and never pushes over a problem.

### What merges and what conflicts

Every object in a house is one JSON file in its own directory — one file per publisher, series, issue, scene, panel, cover, page, story, insert, character, look, setting, prop, outfit, style, and art board, with each panel's images beside it. So:

- **Two authors touching different things merge cleanly.** You letter scene three while your co-author inks the cover: distinct objects are distinct files, and the rebase merges them without conflict.
- **Two authors editing the same board conflict.** Same panel, same cover, same mark: you have both rewritten the same JSON file (and rendered images are binary). The rebase stops, and sync reports *pull hit trouble*.

There is no in-app merge tool; resolution is plain git in a terminal — resolve the conflict (for a binary image, choose a side), continue the rebase, and click sync again. The practical protocol is the obvious one: partition the work — you take the story pages, your co-author takes the covers — and sync often.

Two timing notes, stated plainly: the sync badge can lag reality by up to eight seconds (its git status is cached), and the "to pull" count only updates after a fetch or pull — checking status never touches the network, so run `git fetch` (or just sync) to learn about your co-author's pushes.

### What never syncs

Machine-local, by design, and never in the house repository:

- **Your registry** (`~/.comic-studio/publishers.json`) — which houses are on *your* rack.
- **Your spend ledger** (`~/.comic-studio/spend.json`) — each author pays for and tracks their own renders.
- **Your API key** (`.env` beside the app) — each author supplies their own.
- **Your session** (`state.json` — selection, conversation thread, dark mode).
- **Inside each house**, the `.gitignore` written at founding keeps out the wastebasket (`.trash/`, `.trash--*` files) and `exports/`. It also lists `.queue/` and `.spend.json`, but nothing currently writes either inside a house — the render docket lives at `~/.comic-studio/queue` and the only spend ledger is `~/.comic-studio/spend.json`, both machine-local anyway; those two entries are belt-and-suspenders.

Two consequences worth spelling out: bound PDFs and CBZs do not travel — each author binds their own from the synced source; and the wastebasket is local — the safety copy of something you deleted lives only on the machine where the delete happened, so only you can restore it.

---

## Limits

Collected from the chapters above, in one place:

- Renders cost real money; larger jobs are announced before or as they queue; the spend ledger at `~/.comic-studio/spend.json` holds daily estimates, not invoices.
- The image model produces exactly three sizes: 1024×1024, 1536×1024, 1024×1536.
- The app is local-first and single-machine; collaboration is through git, and same-object edits conflict with no in-app merge tool.
- The detail dial and your reading spot reset on restart; panel, scene, and story reordering is single-step (no drag-reorder).
- Scene, story, panel, and series deletion route through the Editor by design; only inserts and unused assets strike directly.
- Striking a setting shot has no wastebasket entry; emptying a torn-up pile burns permanently after a confirm; the 30-day wastebasket purge is a manual, confirmed button in the wastebasket dialog — nothing in the studio deletes on its own.
- The table's "drop a reference image" row currently fails to save the file — use the paste/drop dialog instead.
- The native folder chooser is macOS-only; elsewhere, type the path.
- The sync badge lags up to eight seconds, and behind-counts require a fetch.
- An insert located at an inside cover prints in place of that cover's art.
- The Editor can be stopped mid-turn, but a render already on the wire may still land.

That is the whole studio. Adopt the demo house, open *the-fog-edition*, and start at the SCRIPTS stop — the script is already waiting to be broken into scenes.
