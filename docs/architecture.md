# Comic Studio Architecture

This document describes the system for engineers who will read and change the code. Every
claim is checkable against the tree. File paths are given throughout; line numbers are
omitted except where a single line is the fact.

## System overview

Comic Studio is a local-first NiceGUI application. One Python process serves the whole
studio: the web UI, the file-backed storage layer, the language agent, and the render
queue. `main.py` calls `ui.run` with `reload=False` (hot reload would kill in-flight
renders) on the port named by the `COMIC_STUDIO_PORT` environment variable, default 8080.

Storage is files on disk. Every persisted object is one JSON file in its own directory
under `data/`. There is no database. `data/` is served as static files with
`follow_symlink=True`, because `data/` is a directory of symlinks: each symlink points at
a git repository that is a publishing house (see "Publisher houses"). Window state —
selection, the conversation thread, the agent's memory, dark mode — persists in
`state.json` at the repository root (`gui/state.py`), written atomically under a lock and
excluded from git.

The UI's position is a selection chain — a trail of `SelectedKind` links from house down
to panel. Most subsystems key off the innermost link: path templates, toolkits, and
persona choice all switch on a `SelectedKind` value. See "GUI architecture" for the full
selection model.

Text generation uses model `gpt-5.2`; image generation uses `gpt-image-1.5`
(`helpers/generator.py`). Renders cost real money and are quoted before batches. The image
model generates only three sizes: 1024×1024, 1536×1024, and 1024×1536. The app is
single-machine; multi-author collaboration happens through git, not through the app.

The app's user-facing language is comics vocabulary. Terms used in this document:

- **house** — a publisher; on disk, a git repository.
- **the wall** — the lobby view of every house, series, and issue.
- **the open book** — the issue view; the comic itself, rendered as sheets.
- **room** — the editing context opened by the current selection's kind; each
  `SelectedKind` is a room, with its own persona and opener.
- **bench** — a direct-manipulation editing surface in the details pane (light table
  tools, issue-view controls) that writes storage directly, without an agent turn.
- **light table** — the per-panel (or cover, insert, mark) editing surface.
- **acetates** — the movable layers on a light table: figures, props, the setting plate,
  letters, trade dress.
- **rough** — the composited blocking image of a panel before rendering; **proof** — the
  rendered panel art; **take** — any rendered candidate image on file.
- **inking** — rendering with the image model.
- **the ledger** — the computed production status of an issue (`helpers/ledger.py`).
- **the wastebasket** — the trash; deletes are moves, purge after 30 days is the only true
  delete.
- Print terms the binder uses: **folio** — the printed page number; **indicia** — the
  fine-print publication block; **recto** — the right-hand page of a spread; **mailbag** —
  the letters-from-readers insert.

## Data model

### Schema objects

Every persisted object is a Pydantic `BaseModel` exposing `primary_key`, `parent_key`, and
`id` properties. Example: `Page.primary_key` is `{page_id, issue_id, series_id}`;
`parent_key` drops `page_id` (`schema/page.py`). The full roster is exported from
`schema/__init__.py`: `CharacterModel`, `CharacterVariant`, `Issue`, `Insert`, `Page` /
`PanelCell` / `PanelRef`, `Story`, `PropAsset`, `Outfit`, `Panel`, `SceneModel`, `Series`,
`Publisher`, `ComicStyle`, `StyleExample`, `StyledVariant`, `ArtBoard`, `Setting`,
`ReferenceImage`, `Cover`, `LayoutFeel`, and the dialog types.

Two objects carry layout truth:

- `PanelCell` is a panel's exact box on the 6-wide × 10-tall unit grid. Fractional
  coordinates are legal. Art is cropped to fill, never distorted.
- `Page` carries both `rows` (lists of `PanelRef`) and `cells`. When `cells` is non-empty
  it is the authoritative geometry. `pinned=True` means the stitcher must never reflow the
  page.

`ArtBoard` is scoped by `scope_id` — a series id for a masthead, a publisher id for a
logo; its primary key is `{scope_id, board_id}` (`schema/artboard.py`).

### Paths and files

`storage/filepath.py` holds five template dicts keyed by class name and `SelectedKind`
value: `PATH_TEMPLATES`, `ROOT_PATH_TEMPLATES`, `FILEPATH_TEMPLATES`,
`IMAGE_PATH_TEMPLATES`, `UPLOAD_PATH_TEMPLATES`. `BASE_PATH` is `'data'`.

The on-disk hierarchy: `data/publishers/{publisher_id}`, `data/styles/{style_id}`,
`data/series/{series_id}`, then `characters/`, `props/`, `outfits/`, `settings/`,
`variants/`, `issues/`, `covers/`, `pages/`, `stories/`, `inserts/`, `scenes/`, `panels/`
nested under their parents. Artboards live at `data/artboards/{scope_id}/{board_id}`.

One JSON file per object, with a fixed basename per class: `publisher.json`,
`series.json`, `style.json`, `character.json`, `prop.json`, `outfit.json`, `setting.json`,
`variant.json`, `issue.json`, `cover.json`, `scene.json`, `page.json`, `story.json`,
`artboard.json`, `insert.json`, `panel.json`, `styled_variant.json`.

**Prose lives in markdown, not JSON.** Long-form text is stored as a `.md` sidecar
beside the object's JSON (the map is `SIDECAR_FIELDS` in `storage/local.py`):
`story.md` for an issue's script and a story's text; `scene.md` and `blocking.md` for a
scene's manuscript and blocking notes; `brief.md` for the render brief of a panel,
cover, insert, or artboard (mastheads and logos as marks); `description.md` for the
canon of a publisher, series, setting, character, prop, or outfit; `logo.md` for the
publisher's logo brief; and `description.md`/`appearance.md`/`attire.md`/`behavior.md`
for a character variant's look. One-line labels (names, panel beats) and structured
specs (style definitions, the shot lists nested inside `setting.json`) stay in the
record. The JSON REFERENCES the sidecar — the field holds the `.md` filename (`""` when
the words were emptied, `null` for an optional brief never begun); on read the sidecar
is the ONLY source of words (a missing sidecar reads as empty), and on write the field
leaves the payload for its sidecar — same atomic tmp-fsync-replace discipline, UTF-8. Emptying a prose field retires its sidecar to the wastebasket. This
is the single supported way of storing prose: external editors and git diffs see
manuscripts as manuscripts. A one-time idempotent migration (`migrate_house_prose`)
runs when a house is mounted or adopted, converting any pre-ruling inline prose —
including wastebasket payloads, so old deletes restore correctly — and stamps
`.git/comic-prose-v2` so later boots skip the walk (v1-stamped houses re-walk once for
the widened map).

Generated art lands in an `images/` subfolder per object. `StyledVariant` images are
style-keyed at `variants/{variant_id}/images/{style_id}`. Reference uploads land in an
`uploads/` subfolder per object — except `StyledVariant`, `Publisher`, and `StyleExample`,
whose uploads path IS the images path. Recognized image extensions: png, jpg, jpeg, gif,
bmp, tiff, webp, svg, heic, avif. Dot-prefixed (hidden) files are always skipped when
listing.

### CRUD semantics

`LocalStorage` (`storage/local.py`) implements the object store:

- `create_object` REASSIGNS the object's id to a fresh UUID4 (which becomes the folder
  name) unless `overwrite=True`, in which case the existing id field is honored. Fresh ids
  are generated by retrying UUID4 until unique within the folder.
- All JSON writes are atomic: unique tmp file + flush + fsync + `os.replace` under a
  process-wide `threading.Lock`, then a parent-directory fsync.
- `read_object` returns `None` for a missing file; no exception. `update_object` raises
  `FileNotFoundError` if the file does not already exist.
- `read_all_objects` scans subfolders of the class root and returns `[]` when the root
  does not exist. Order is filesystem order unless `order_by` (a string or callable) is
  passed.
- `delete_object` defaults to soft delete (a move to the trash). `soft=False` hard-removes
  with `shutil.rmtree` — used for derived layout pages so re-flows never bury real deletes
  in trash churn.
- Uploads reject non-image mime types and never clobber: a same-named upload gets a
  `--{6-hex}` suffix. `upload_binary_image` sniffs PNG magic bytes to choose `.png` vs
  `.jpg` (transparent renders stay PNG) and names the file a fresh UUID.

## Publisher houses: registry, mounts, resolution

### A git repo is a publisher

Each house is a self-contained, normal git repository holding one `Publisher` record plus
its series, styles, prompts, and references. The machine-local registry at
`~/.comic-studio/publishers.json` holds `{"publishers": [{"slug", "path"}]}`. Registry
writes are atomic; `register()` deduplicates by path, refuses a slug collision (two
paths under one folder name would silently shadow each other's mount), and runs the
prose migration on arrival; `registered()` silently drops entries whose path no longer
exists on disk. `unregister()` removes only the
registry entry and the mount — the repo on disk is never touched. An empty rack — a
registry with no houses — is legal.

### Mounts

`main.py` calls `registry.mount_all()` at import time. It turns `./data` into a real
directory of one symlink per registered house (`data/<slug>` → repo path; Windows uses
junctions). It prunes only dangling or unregistered symlinks — a real file or directory
under `data/` is never touched (the rule "visible beats gone": keeping data visible
always wins over removing it). `storage_for(slug)` re-runs `mount_all` when a mount is
missing, because `LocalStorage.__init__` would otherwise `mkdir` a real directory where
the symlink belongs.

Records inside a house store locators as `data/…` relative to their OWN root.
`LocalStorage._rewrite_locators` translates to and from the runtime form `data/<slug>/…`
at the JSON boundary; the translation is the identity when `base_path == 'data'`. This is
what makes a house repo self-contained and cloneable.

The mount slug is the basename of the target directory; the `publisher_id` is the
slugified house name. These differ: Foglamp Press mounts at `data/foglamp-press-comics`
with `publisher_id` `foglamp-press`. Two repos sharing a basename would collide on slug;
`mount_all`'s slug-keyed dict keeps the last.

### storage_for_key and the carnival rule

`storage_for_key` (`storage/registry.py`) resolves a primary key carrying a `series_id`,
`publisher_id`, or `style_id` to the registered mount that actually holds that id, via the
finders `house_of_series` / `house_of_publisher` / `house_of_style`. The series and style
finders are directory probes (`os.path.isdir` on the mount path); the publisher finder
reads each house's `Publisher` record instead, because the folder name is the mount slug,
not the `publisher_id`, so a probe could not work there. When no house claims the id, the
caller's fallback storage is returned.

**The carnival rule**: a fallback storage rooted OUTSIDE the mounts — a test fixture tmp
copy, a scratch clone — is returned immediately and never hijacked. Fixture data shares
real ids with live repos; without this rule, resolution would aim tool writes at the
author's live data. The rule is named for the 2026-07-10 carnival-scene data-loss incident
(root cause fixed in commit 0bc560e) and is behaviorally pinned by
`tests/test_ledger.py::test_the_carnival_rule_protects_fixtures`.

`house_of_style` is deliberately first-hit-wins and ambiguous: default styles are copies
sharing ids across houses. It is used only as a legacy-link fallback; canonical style URLs
carry the publisher.

### Founding, adopting, cloning, syncing

`clone_house` (`helpers/house_git.py`) fetches a house from a git URL: it clones into a
staging sibling of the destination (`GIT_TERMINAL_PROMPT=0`, so a private HTTPS repo
fails fast instead of hanging), validates the result with `looks_like_house`, then moves
it into place — a failed or foreign clone never leaves debris at the destination. The
GUI's *A NEW PUBLISHING HOUSE* dialog exposes it as **Clone & adopt** (paste a URL), and
the demo-house door clones `github.com/dlewissandy/comic-studio-example`, falling back
to founding the built-in Foglamp Press demo locally when the clone cannot deliver.

`found_house` (`storage/registry.py`) creates a new house: `target/series`, then styles /
prompts / references copied from the first available source (`~/.comic-studio/templates/house`,
else the first registered sister house, else the app bundle). With no styles source it
raises `RuntimeError` before any registration. It writes the Publisher record, a
`.gitignore` (`.trash/`, `.queue/`, `.spend.json`, `**/exports/`, `**/.trash--*`,
`.DS_Store` — working scratch never enters history), runs `git init -b main` only when no
`.git` exists, and makes a founding commit (identity fallback: `Comic Studio` /
`studio@comic-studio.local`). A failed founding commit only logs a warning; the house
registers regardless.

A folder that already `looks_like_house` (has `publishers/` plus `series/` or `styles/`,
with a readable Publisher record) is adopted with `registry.register` alone: no git init,
no styles copy. This is the collaboration path: author B clones the repo and adopts it.

The wall's sync glyph runs `sync_house` (`helpers/house_git.py`) in a worker thread:
commit dirty work, then `git pull --rebase --autostash`, then `git push`, each with
captured output and a 120-second timeout. Commit messages are generated from the porcelain
by folding files into objects and naming them in comics nouns
(`STUDIO SYNC: <top-5 counts> — <up to 3 series names>`). Pull failure stops before push
with a receipt telling the author to resolve and sync again — there is no in-app merge
tool; resolution is plain git. `repo_state` (dirty / ahead / behind counts for the badge)
never touches the network and is cached 8 seconds, so the behind count is only as accurate
as the last fetch.

Merge granularity follows the one-JSON-per-object layout: two authors touching distinct
objects touch distinct files and merge cleanly; both editing the same object conflict on
one JSON file (and rendered PNGs are binary).

Never in a house repo and never synced: the registry (`~/.comic-studio/publishers.json`),
the spend ledger (`~/.comic-studio/spend.json`), `.env` with `OPENAI_API_KEY`, and
`state.json`.

## The agentic stack

### One Editor

`init_agents` (`agentic/__init__.py`) builds a single Agent named "the Editor" with model
`LANGUAGE_MODEL = 'gpt-5.2'` (`agentic/constants.py`), carrying `ALL_TOOLS` — the
deduplicated union of every per-kind toolkit, computed at import keyed on tool name
(`agentic/toolkits.py`). Every toolkit kind in the returned dict maps to that same Editor
instance. The per-kind kits survive only as a room-by-room map and as test pins; the
runtime agent always holds the union.

The union is 157 tools across 25 kinds. Verb breakdown: 47 update, 26 read, 24 create,
20 delete, 10 generate, 5 select, 4 import, 2 move, 2 export, plus 17 singletons
(`undo_last_delete`, `derive_character`, `compose_character_variant`,
`extract_outfit_from_variant`, `list_library_assets`, `mark_breakdown_current`,
`render_missing_panels`, `stitch_issue_pages`, `layout_issue_pages`, `preflight_issue`,
`attach_panel_reference`, `split_layer`, `inpaint_image_region`, `outpaint_image_region`,
`ink_cast_in_one_hand`, `swap_variant_outfit`, `dedupe_props`). The four cover kinds share
one kit; the image-editor kits hold only inpaint and outpaint.

Room voices are cosmetic: `ROLE_NAMES` (`gui/coauthor.py`) maps rooms to studio staff (the
Layout Artist, the Penciller, the Character Designer, and so on), but every reply balloon
renders under the single name "the Editor".

### Per-turn instruction assembly

`instructions(wrapper, agent)` is passed to the Agent as a callable and rebuilt EVERY turn
(`agentic/instructions.py`). It concatenates, in order:

1. **Room persona** — chosen by `selection[-1].kind.value`, falling back to `lobby`. The
   `PERSONAS` dict covers 25 kinds — every selection kind that has a room — with the four
   cover kinds aliased to the cover persona.
2. **Boilerplate** — first readable file among
   `~/.comic-studio/templates/house/prompts/system/boilerplate.txt`, each mounted house's
   `prompts/system/boilerplate.txt`, then legacy `data/prompts/system/boilerplate.txt`;
   `''` if none. Cached with `lru_cache(maxsize=1)`, so edits require a restart.
3. **The laws** (`SPEAK_ONLY_DONE_WORK`), five, verbatim: SPEAK ONLY DONE WORK (never
   claim work without a tool call this turn); THE LEDGER IS THE TRUTH (status questions
   must call `preflight_issue` or a `read_*` first); STAY WHERE THE AUTHOR STANDS
   (`select_*` only on explicit ask; creating, reading, rendering never navigates); CLOSE
   WITH A WORD (end every turn with a line to the author); BARE APPROVALS (a bare "yes"
   with no pending proposal gets a question, not action).
4. **WHERE THE AUTHOR STANDS** — the selection chain printed as `kind: 'name' (id=…)`,
   declared as the ids "this" and "here" refer to.
5. **THE STUDIO WALL** — a roster of every house / series / issue with real ids across all
   mounted houses (or the handed storage when off the registry root), cached 10 seconds.
   The header orders the Editor to resolve names against this list from any room and never
   invent an id. On any exception the roster degrades to `''`.
6. **Details block** — nothing for a bare lobby; a JSON id→name map for a single
   all-publishers / all-series / all-styles selection; otherwise THE OBJECT IN HAND, the
   full `model_dump` of the innermost selected object. Image-editor rooms append IMAGE
   EDITOR STATE (mode, selection, image).

The assembled instructions are logged at debug level each turn.

### The memory thread

There is ONE memory thread: `state.agent_thread` persists across rooms. A send uses
`_trim_thread(list(thr))` if the thread exists, else seeds from the visible conversation.
`_trim_thread` caps at 140 items, trimming only at a whole user turn so a tool call is
never split from its output; the docstring records that an earlier 80-item cap caused
"dumber than dirt" amnesia. The thread is persisted to `state.json` capped at the last 120
dict items and restored on page build, filtering non-dicts. Older turns are forgotten;
that is the cost of the cap.

Room changes append a system "hat note" to the thread — `[The author walked to <name>
(<key>)…]` — and consecutive silent walks coalesce by replacing the last note. The visible
thread gets a coalescing MEANWHILE caption that is also a clickable door back to that room
(`gui/thread.py`).

On success the thread becomes `stream.to_input_list()`. On STOP it becomes the messages
plus one assistant memo ("Stopped by the author mid-turn.") listing up to 40 receipts. On
failure the memo is the error note plus up to 40 receipts, so "go on" resumes without
re-billing done work.

### Streaming, receipts, the stop door

A turn runs `Runner.run_streamed(agent, input=messages, context=state, max_turns=40)`
(`messaging.py`); the stream handle is stored on `state._live_stream` for the stop door.
Raw text deltas append to the reply markdown, scrolling history per token.

Each tool call adds a receipt row (line, quiet flag, answer, image) to the turn's work
entry, with a verb-prefix emoji and up to three short scalar args on the line; read / list
/ select rows are "quiet". Tool answers are truncated to 1500 characters; the first
existing `.jpg`/`.jpeg`/`.png` path in an answer is attached as a thumbnail. If
`state.is_dirty`, the details pane refreshes mid-turn so edits appear live. The work line
is one collapsed expansion per turn ("worked — N steps · M pieces inked"); a turn with
zero receipts leaves no work line at all. A "life signs" ticker cycles hand-lettered verbs
every 2.4 s; a tool call pins a tool-truth phrase until the tool answers.

There are three stop doors: a header stop button visible only during a turn, a stop icon
on the live work bubble, and typed stop words (stop / cancel / halt / abort variants).
`stop_turn` cancels the stream and manually enqueues a `QueueCompleteSentinel`, because
`cancel()` kills the producer without waking the consumer. The stop note reads "Stopped at
your word — a render already on the wire may still land on the board", and it is appended
to whatever streamed rather than depending on an exception. A stop cannot recall a render
already sent to the API.

Failure behavior: `MaxTurnsExceeded` prints "I ran out of steam mid-way… say go on"; other
exceptions print the first 200 characters of the error and suggest "try again". A turn
ending with no words gets a closing composed from the last ≤6 human-readable tool answers,
or a placeholder pointing at the work line. The `finally` block always re-enables send,
clears the lock / stream / label, cancels the ticker, and re-arms the suggestion strip.

While a turn runs, a new message is queued and auto-sent afterward without clobbering a
draft the author typed meanwhile. Whitespace-only input returns before any thread write —
a bare Enter sends nothing and bills nothing. Enter sends only when alone; Shift+Enter
inserts a newline.

### The one-shot input intercept

The conversation box doubles as the app's modal editor. A bench prompt prefills the box
and arms `state._input_intercept = (prefix, handler, ack)`. On send, if the text still
starts with the prefix, the handler runs DIRECTLY — no agent turn, no LLM billing — and
the words land in the thread; a handler exception posts "That didn't take — … retry". An
erased prefix stands the intercept down and the message goes to the Editor normally. The
intercept is consumed either way. Armed from the issue view, the light table (four sites),
and the style room.

### Openers and chips

`opening_and_chips` (`gui/coauthor.py`) computes a per-room opener and up to four chips
from cheap storage reads only — no model call until the author actually speaks; any greeter
exception is swallowed. Chips come in two kinds: a string chip SENDS a real message
through `send()` (or, ending with `…`, prefills the box — a prompt starter); a
`(label, action)` tuple chip is a DOOR that runs its action instantly with no agent turn.
Issue-room chips quote the real production ledger (actual missing-panel counts, the first
three todos).

An image dropped into the conversation (image mimetypes only) is stored via
`upload_reference_image` on the nearest ancestor accepting uploads, posts a paperclip
aside, and auto-sends a real user message to the Editor. With no accepting ancestor the
drop is refused.

### Cost controls

Every OpenAI image render goes through `invoke_generate_image_api` or
`invoke_edit_image_api` (`helpers/generator.py`, model `gpt-image-1.5`). Both record to
the spend ledger AFTER a successful API call, inside the invoke functions themselves
(`helpers/generator.py:178, 238`), so every call site is covered regardless of where it
lives; the call sites are in `agentic/tools/imaging.py` (20) plus the light table's
cut-out edit (`make_cutout_body`, `gui/light_table.py`). Text-only turns bill only the
chat model, never the spend ledger.

The spend ledger is `~/.comic-studio/spend.json`, shape
`{"YYYY-MM-DD": {"low": n, "medium": n, "high": n}}`, written atomically under a lock; a
corrupt file heals to `{}`. Estimated per-image rates: low $0.02, medium $0.07, high
$0.19; unknown quality $0.10. The header spend meter (render count + ~cost, refreshed
every 15 s) opens a 7-day receipts dialog labeled "Estimates at published image rates —
the invoice is the truth." Quota and billing errors re-raise as `StudioOutOfInk` with a
plain-language message pointing at OpenAI billing. With no `OPENAI_API_KEY`, a persistent
amber banner tells the author to put the key in a `.env` and restart, before the first
message can fail in jargon.

Batch renders quote first: `render_missing_panels` and kin report "Estimated cost" and
require `confirm=true` before any API call (pinned by `tests/test_render_queue.py`).
Running batches get an in-place progress bar with HOLD (finish the piece in hand, then
wait) and STOP (set the rest aside) buttons. Every queued render writes a slip to
`~/.comic-studio/queue/`; a header "N on the drawing board" chip counts on-disk slips
younger than 900 s every second, so every window sees work in flight. At startup, slips
older than 900 s are reported in chat as work lost to the last shutdown, and deleted only
after that report posts; younger slips are never deleted, so one instance's startup sweep
never removes slips for another instance's renders still in flight.

Agent handoffs are effectively unused: `handle_handoff_event` only logs, with a TODO.
Unhandled stream item types are logged as errors, not raised.

## The layout engine

### The grid and the vocabulary

The page grid is 6 units wide × 10 tall (`helpers/stitcher.py`). Panel aspects are
landscape 1.5, portrait 2/3, square 1.0. `size_mult` clamps the author's size to the
aspect's vocabulary — squares 1×/2×/3×, portrait and landscape 1×/2× only; legacy names
(small / regular / large / splash) still read.

Three shape truths coexist:

- **Intent** — `panel.aspect` and `panel.size`, what the author asked for.
- **Laid** — `laid_aspect` reads the panel's CURRENT stored page cell and reports the
  aspect the book actually prints, falling back to the panel's own aspect when unplaced.
- **Law** — `size_mult`'s clamp. The shape picker in the book is generated from this law
  (7 boxes) and shows both truths in its header: "held at …" when locked, "auto · laid X
  (asked Y)" when the flow flexed an unlocked panel.

### Exact-fill and band flow

`flow_run` tries EXACT-FILL pagination first: locked panels (`shape_locked=True`) keep
their shape, unlocked panels flex, and every page is a gapless exact cover of the 6×10
grid. `helpers/tilings.py` enumerates every exact cover from six pieces — square 1× (2,2),
landscape 1× (3,2), portrait 1× (2,3), square 2× (4,4), landscape 2× (6,4), portrait 2×
(4,6). 354 canonical tilings exist; exact fills exist for 4 to 15 panels per page.
`paginate` (`helpers/pagination.py`) is a pure back-to-front dynamic program choosing page
breaks; a locked panel with an un-tileable shape (e.g. square 3×) raises
`LayoutImpossible` immediately, naming the panel index.

On `LayoutImpossible`, `flow_run` falls back to band flow and returns the reason as a
note. `pack_bands` preserves reading order and true aspects with signature band shapes
(portrait plus two stacked landscapes; portrait pairs at h=4.5; three squares across at
h=2; a 2× landscape splash at h=4); leftover width becomes centered breathing, never
stretch. In band flow the same `paginate` runs in its band mode, stacking bands until 10
units are spent; `justify` spreads slack as inter-band gutters capped at 0.5 units plus
symmetric margins; the last page keeps its natural height. The fallback reason is stashed
in the in-memory `_LAYOUT_NOTES` dict keyed `(series_id, issue_id)` — transient,
recomputed each stitch, cleared by a clean flow, and lost on restart. The book shows it as
a non-blocking amber banner.

Four feel knobs — density, verticality, irregularity, variety, each in [-1, 1] — steer
tiling choice, moving only unlocked panels; a scene's `layout_feel` overrides the
issue's. All-neutral knobs reproduce the plain flow (pinned by `tests/test_layout_feel.py`).

### Stitching, pins, and the unproof rule

`stitch_pages` breaks the panel run at bare scenes, insert anchors, and — when
`issue.layout_by_scene` — every scene boundary. Pinned pages pass through verbatim, only
the folio reassigned. `apply_stitch` snapshots the outgoing layout to
`series/{sid}/issues/{iid}/.trash--layout--{6hex}.json`, HARD-deletes the old `Page`
objects (`soft=False`), and writes new ones with `overwrite=True`. `remember_stitch`
persists the derived layout quietly in place (no trash) when its signature differs, and
never touches a hand-designed layout (any stored page with rows but no cells returns
immediately).

`pin_page_layout` writes each panel's aspect and size from the picked tiling pieces,
dissolves any older pin claiming the same panels (one pin per panel), saves a pinned page
`page-pin-{panel8}`, and re-remembers the book. `repack_page` dissolves a pin. A pin whose
panel was struck dissolves itself: `alive_pins` returns only pinned pages whose every cell
names a living panel.

**The unproof rule**: `unproof_mismatched` clears `panel.image` when the drawn image's
aspect class (ratio > 1.15 landscape, < 0.87 portrait, else square) mismatches its laid
cell. The take stays on file — only the panel's featured selection (`panel.image`) is
cleared — and the names collect in `LAST_UNPROOFED` for receipts. It runs after every
`remember_stitch` and every repack. A reflow that flexes a panel's shape therefore
silently unselects its proof rather than print cropped art.

## The render pipeline

### Model calls

Text calls default to `gpt-5.2` at temperature 0.7 via `openai.responses.parse`, with
optional structured output and base64-JPEG image inputs. Image generation and edits both
use `gpt-image-1.5`; generate passes `moderation='low'`; edit supports a mask, reference
image file handles, `background` → PNG with alpha, and `input_fidelity` via `extra_body`
(`helpers/generator.py`). The API key is loaded by `load_dotenv()` and read per call with
`os.getenv`.

Quality tiers are `IMAGE_QUALITY` LOW / MEDIUM / HIGH (`helpers/image.py`). Tier choices in
the tree follow one rule (recorded in memory as "blocking is fast and cheap"): throwaway
blocking artifacts render LOW; durable reference assets the finals inherit render HIGH.
Examples: a setting master not yet inked in the board's style queues a HIGH render; the
opaque-backdrop cut-out and setting dressing are single MEDIUM edits.

### Setting masters

Setting masters are orientation-keyed per style (`helpers/masters.py`): the landscape
master is stored under the bare `style_id`, portrait and square under
`'<style_id>/portrait'` and `'<style_id>/square'`. A render at a mismatched orientation
writes its own key instead of clobbering — a portrait cover's re-ink can never replace the
landscape master every landscape panel shares. When the exact orientation is missing,
`master_for` borrows another orientation of the right style and reports the borrow (it
returns `(path, exact)`). Pinned by `tests/test_masters_truth.py`.

### The compositor

`helpers/compositor.py` is the single compositing implementation. `base_canvas` builds
the canvas at the three render sizes (`DIMS`: landscape 1536×1024, portrait 1024×1536,
square 1024×1024); `paste_acetates` places layers with the same blocking math the drag JS
displays; `paste_letters` pastes letters last, in craft order — and the book's CSS balloon
styles mirror its output. The light-table flatten, group merge-down, the rough the book
and reader print, and letters printing all call these functions — one implementation, no
drift. `is_placeholder()` keeps scaffold text out of composites, briefs, and print; the
ledger's `letters` line consumes it too.

### Reference collection and the brief

Render tools live in `agentic/tools/imaging.py`. The standing ruling ("render honors the
brief"): render draws only what the panel says; a bare board reads the panel's
`breakdown_brief` to pick the correct references — cast sheets in the board's style, the
setting plate, props — without roughing first. Casting is explicit: the render wears who
you cast, the setting is a removable layer, and nothing is auto-stamped onto the table.

### The queue

Renders are queued, not inline: each queued render writes a `{label, queued_at}` slip to
`~/.comic-studio/queue/`. Batches run in a background task after the cost quote is
confirmed; HOLD finishes the piece in hand then waits, resume continues with FRESH boards,
STOP sets the rest aside; sends stay unblocked during batches (pinned by
`tests/test_batch_holds.py`). The header drawing-board chip and the startup
orphaned-slip report are described under "Cost controls" above; the spend ledger is the
billing record.

## The binder and the reader

### Composition

The page canvas is 994 × 1528 px — 6.625 × 10.1875 in US comic trim at 150 dpi — with
~47 px side margins and a 28 px gutter (`helpers/binder.py`). `compose_book` returns every
sheet in order: front cover; inside-front (indicia over a located insert or cover art, or
a composed title / credits / indicia sheet when the slot is bare); interior pages with
folio stamps; labeled overflow pages for rendered panels the layout forgot (never
dropped); inserts slotted after their anchor scene's last page, unfolioed; inside-back;
back. The indicia small print stamps over inside-front art in a translucent white band —
including over an inside-front insert. Located inserts (`location='inside-front'` /
`'inside-back'`) beat cover art for their slot.

Incomplete work still prints: mailbag inserts with a description typeset as a letters page
until rendered; other unrendered inserts print a named placeholder sheet; both add a
"missing" note. Dangling page refs print as named placeholder boxes and are reported.
Unrendered panels with a light-table rough print the rough with an amber ROUGH corner
stamp. `refresh_machine_layout` re-stitches before ANY composition when the stitched
layout drifted, but never touches hand-laid pages.

### Exports

PDF saves at `resolution=150 quality=95`. CBZ is a `ZIP_STORED` zip of JPEG q92 pages
named `{i:03d}-{label-slug}.jpg` plus a `ComicInfo.xml` carrying Series / Number / Title /
PageCount. The export filename is `{series-slug}-{issue_number:02d}`. Each bind writes
`{output}.meta.json` with the book signature, timestamp, and page count; download chips in
the book compare it against the current signature and flag `· stale` or `· old bind`.

`book_signature` is an md5-16 fingerprint of the issue JSON, series name, stories text,
inserts, covers (path + mtime), page geometry, and every panel's art or rough signature.
`reader_sheets` composes with the exact PDF math and caches JPEGs (q90) at
`series/{sid}/issues/{iid}/exports/sheets/` with a manifest keyed by signature; a cache
hit requires the matching signature AND all files present; stale JPEGs are removed on
recompose.

### The reader

`/read` is the spinner rack — every issue across all mounted houses as a cover tile.
`/series/{sid}/issue/{iid}/read` resolves the owning house via the registry and renders
read-only spreads: cover alone on the recto, then two-up; edge thumbs, arrow keys,
PageUp/Down, and touch swipe turn spreads; narrow viewports (width < height × 0.95) switch
to single-page mode preserving position. The bottom counter quotes sheet labels and opens
a jump menu of every sheet; a left drawer lists every house / series / issue; incomplete
books show a "reading a proof" expansion quoting the production ledger.

## The ledger and the production board

`helpers/ledger.py` `issue_ledger` builds lines keyed `script` / `breakdown` / `drift` /
`scenes` / `panels` / `letters` / `covers` / `back-cover` / `inserts` / `placement`, each
carrying a count, per-offender items, a `data-banchor` anchor (the DOM attribute the open
book scrolls to), and the stop of the book's detail dial it lands on (see "The open
book"). `summary()` prints "press-ready" or "N things before press". `drift` fires when
the sha1 of the current script text differs from `issue.broken_script_sha`; `placement`
uses `binder.page_coverage` for unplaced and dangling panels. Every surface — colophon,
masthead badge, reading room, issue-room chips — reads this ONE ledger.

`helpers/production.py` stages an issue through 8 fixed stages: scripted, scenes, beats,
layout, roughed, inked, covers_roughed, covers_inked. "Done" requires `total > 0` and
`done >= total` — an empty stage is "not started", never complete. Cover stages floor the
total at 1 so "nothing yet" never reads as done. Roughed means figure images on the light
table or already rendered; inked means the image file exists on disk; layout counts panels
referenced by stored pages (`page_coverage` walks `Page.rows`, so hand-laid rows-only
pages count too). `press_ready` means all started stages are complete.

## Trash and recovery

Deletes are moves. `soft_delete` moves a file or folder to
`{base_path}/.trash/{epoch-ms}-{8hex}/payload` with a `manifest.json` recording
`original_path`, `deleted_at`, a note, and `is_dir` (`storage/trash.py`). `soft_backup`
COPIES into the trash leaving the original in place — pre-overwrite insurance, used by the
light table's `snapshot_board` before destructive mutations.

`restore` refuses to land outside the basket's own base (a copied basket cannot write into
the tree it was copied from) and refuses when the original path is occupied. `swap_entry`
restores an occupied entry by first soft-backing-up the current occupant, then swapping
the old version in. `purge(older_than_days=30)` is the ONLY place the studio truly deletes
anything.

The header wastebasket dialog aggregates entries across every mounted house, newest first
with day captions; a name filter appears above 8 entries; occupied entries get a swap-back
button, free ones a restore button; the purge button appears only when 30-day-old entries
exist and always asks first (`main.py`).

Exceptions to the wastebasket, by design: derived layout pages are hard-deleted (re-flows
would otherwise bury real deletes in churn), and a reference image's ✕ on the light table
renames the file in place to a dot-prefixed `.trash--` name, hiding it from listings.
Insert ✕ in the book is a real strike (a direct `delete_insert` tool call, soft), not an
agent request. Trash restore silently skips entries whose original path is occupied,
walking back to the newest restorable one.

## GUI architecture

### Layout, state, and routes

The page is a header (breadcrumbs, dark switch, spend meter, drawing-board chip,
wastebasket, stop button), a 70/30 splitter of details ("the bookroom") and the
conversation history with a pinned NEXT chip strip, and a footer textarea with Send.
Routes: `/` (lobby, restores the last selection as a resume card), `/publishers…`,
`/library`, `/styles…` (legacy, re-walked to the owning house), `/read`,
`/series/{sid}/issue/{iid}/read`, `/series/{tail}`. Unknown tails land at the front door
with a notify naming the unrecognized path, never a silent redirect to the lobby.
Cmd/Ctrl-K opens the command palette; browser back/forward reloads to re-resolve
selection from the URL; `DARK_MODE` sets the default theme.

`state.json` persists four keys: the selection, the single flattened visible thread, the
agent thread (last 120 items), and dark mode. A legacy per-room `conversations` key is
consumed read-only by the one-time pre-thread migration (which backs up to
`state.json.pre-thread.bak` and folds the rooms into `thread`) and is never written back.
The selection is a trail (chain) of `SelectedKind` links; `change_selection` drives both
navigation and the agent's hat notes. Every `SelectedKind` must pass
`selection_to_context` without raising (pinned by `tests/test_one_thread.py`) — a new
room ships only after a real tool call runs through it.

There is ONE thread and it must survive concurrency: `APPState.write` unions thread
entries by id, so two windows appending at once both survive, idempotently (pinned in
`tests/test_drawing_board.py`). A page reload mid-turn leaves an
"interrupted — a reload cut this turn short" row. Empty reply balloons are deleted, not
persisted.

The refresh model is repaint-on-change: benches mutate storage, post a quiet thread
receipt (`table_receipt`; receipts never raise), and call `state.refresh_details()`;
mid-turn, `state.is_dirty` triggers the same repaint so the Editor's edits appear live.

### The open book

The issue view IS the comic: sheets at trim proportion, imposed in reading order — front
cover, inside-front, stories, content, orphaned inserts, inside-back, back, colophon. A
five-stop detail dial (SCRIPTS, SCENES, BEATS, ROUGHS, PROOFS) is per-issue, in-memory
only, lost on restart, as is the remembered scroll anchor (spent once per paint). Every
paint reads all scenes / panels / stories / inserts / covers up front, quietly runs
`remember_stitch` (exceptions swallowed with a warning), and computes the ledger once.

**The grid-purity rule: the book grid holds only pages.** The page-turn bar rides ON the
preceding sheet — a vertical dashed slot at its right edge, standing in the gutter —
never a grid cell, so two-up pairing cannot shift; the inside-back cover carries
`book-col-1` so the closing pair holds regardless of interior parity.

Book interactions split three ways: direct local writes (moves, saves, pins, casting,
setting picks, insert creation, art drops — pure storage, free), one-shot intercept edits
(script / beat / notes text through the conversation box, saved directly when the prefix
is intact), and agent requests (breaks, deletes of panels / scenes / stories, credits,
covers, bind — a chip fills the chat box and clicks send). The only direct render in the
book is an insert's "Ink it", which queues a billed render under "the Production Artist".
The pencil on a tile is non-destructive: "Rough it" shows only while `figure_images` is
empty, then becomes "Proof it" — a click can never clobber a rough; it navigates to the
panel and lets the light table auto-fire its own flow (one code path, no copy).

### The light table

`light_table()` serves four board kinds detected by duck-typing — cover, mark (artboard),
insert, panel — on one identical code path. Layers ("acetates") are keyed in
`board.figure_blocking`: `<character_id>/<variant_id>` for figures, `element/<slug>` for
props, `background/plate` for the setting plate, `balloon/<i>` / `caption/<pos>/<i>` /
`letterblock/<i>` for letters, `dress/…` for trade dress. Persisted per key: x, y, h, fs,
z, on, lock, flip, rot, tx, ty, text. The setting is never auto-stamped: the plate shows
only when `background/plate` was explicitly laid.

The drag JS ships in the page head. It grabs through transparent pixels via a 1 px canvas
alpha test, uses a ~3 px drag threshold so clicks never displace, clamps positions, snaps
to thirds / center / baseline (Shift skips), resizes with Ctrl/Cmd+wheel, tilts with
Alt+wheel and `[` `]`, nudges with arrows, and keeps a client-side ring of 60 before-states
for Cmd/Ctrl-Z. A plain wheel always scrolls the page. Every gesture ends in a
`rough_block` event whose server handler writes the blocking and syncs the server-side
element style so a repaint cannot snap the acetate back. Wheel writes debounce 300 ms,
nudges 400 ms, and pending writes flush before deselect.

Page-level rescues: on socket disconnect the table freezes (drags refused, because edits
could not save) and a reconnect after death reloads the page; the app-level drag JS also
routes files dropped on an insert sheet into that sheet's hidden uploader. The stack panel
is the z-order — rows drag to reorder, drop-onto nests into groups; flattening a group
composites visible members and DISCARDS hidden ones. Destructive bench mutations call
`snapshot_board` (a soft backup) first.

Known defect in the current tree: the table's "…or drop a reference image" row handler
`on_drop_reference` only posts a receipt and refreshes — the
`storage.upload_reference_image` call was removed in commit 565ef85, so that specific drop
path stores nothing.

### The healing bench

The image-editor rooms (`gui/image_editor.py`, `gui/image_editor_choices.py`) are a full
room for repairing a single image. The author draws a marquee selection on the image in
the browser; it is harvested at send time — `send()` (`messaging.py`) reads
`window.__imageEditorSelections[dom_id]` into `state.image_editor_selection` before the
turn runs — so the Editor's inpaint / outpaint tools see the region the author marked.
Each edit produces candidate takes reviewed on a choices sheet, tracked by
`state.image_editor_session_id`; pasting a take down replaces the image while the
original (`state.image_editor_original_image`) stays on file for recovery. The room's
persona, kit (inpaint and outpaint only), and IMAGE EDITOR STATE block are described
under "The agentic stack".

## Testing

### Shape and configuration

313 tests across 50 modules under `tests/`, plus `tests/conftest.py`. Pytest config in
`pyproject.toml`: `testpaths=['tests']`, `asyncio_mode='auto'`, one registered marker
`api` ("test makes a real OpenAI API call"). `uv run pytest -m "not api"` is the fast run;
`uv run pytest` includes the two live tests, costs money, and needs a valid key.

### Isolation

Two fixtures keep tests off live data:

- `_sandbox_registry` (autouse) monkeypatches `REGISTRY_PATH` and `DATA_DIR` to
  nonexistent tmp paths for EVERY test, blinding the suite to the real publisher rack
  (the machine-local registry of houses).
- `tmp_data` copies the fixture house (the DND NERDS house, resolved once at collection
  time before the sandbox blinds the registry; falls back to repo `data/`) into a fresh
  `mkdtemp()` per test and removes it after. The copy EXCLUDES `.trash`, because trash
  manifests hold cwd-relative originals and a restore would escape the sandbox.

The carnival rule (see storage) is the third leg: even a leaked real id in fixture data
cannot resolve to a live mount from an off-mount storage. A dedicated regression guard,
`tests/test_storage_isolation.py`, pins that `LocalStorage` honors `base_path` and that
writes never leak into the real data directory.

`mock_imaging` replaces both image APIs with a stub that parses the requested size and
returns a JPEG of that ASPECT — necessary because the unproof rule would otherwise
unselect every square mock laid on a non-square cell. It patches both
`agentic.tools.imaging` and `helpers.generator` names, because some bodies import at call
time. No test ever bills a gpt-image render; the only 2 `api`-marked tests are text-only
agent chats in `tests/test_ui_send.py`, asserting sentinel words that can only come from a
real streamed reply, and they skip cleanly (`api_alive` probe) when the key, network, or
quota is unavailable.

### Standing gates

`tests/test_ux_docket.py` (15 tests) holds the standing gates: a pyflakes F821 subprocess
gate over `gui/ helpers/ agentic/ main.py messaging.py` (the latent-NameError class); the
DRAG_JS payload pins (both drag events must carry all 8 id keys, or a board kind loses
every drag); `read_board` never raises on malformed payloads; the fresh-before-write pins
(`fresh_board` syncs words before writes; `reassign_balloon`, `ungroup`, and
`wear_style_on_table` each call `fresh_board` BEFORE `update_object`); tilt and dress
survive; wastebasket-first for destructive mutations; one render aspect
(`_render_aspect` used by prompt, plate, and canvas); the size law; the unproof rule; and
`creator()` resolving the mount from the object's OWN primary key via `storage_for_key`.

Other pinned rulings: every button's brief posts into a context whose toolkit holds the
named tools (`test_button_promises.py`); every chip has a real tool behind it
(`test_chips_match_tools.py`); agent selects walk the same canonical trails as the UI
(`test_doors_land_true.py`); split may only change lifted regions, enforced in pixels
(`test_split_fidelity.py`); batch HOLD/STOP semantics (`test_batch_holds.py`); batches
quote cost before any mock call (`test_render_queue.py`); no third-party IP in the demo
house (`test_demo_house.py`).

`tests/test_ui_send.py` is the only NiceGUI `User`-harness module (27 tests): lobby
greeting, inline edits, palette, dashboard, resume card, receipts, style rename via
conversation, the choices sheet, the reading-room door, and an assertion that no route
shadows NiceGUI's image serving. Assertions are text-level (`should_see`), not visual.

### What is NOT covered

- Real-API image rendering is never exercised: prompt quality, image API errors, and
  billing behavior have zero automated coverage.
- The reader's visual output is untested in a browser. Book composition is asserted at
  PIL level (sheet order, labels, uniform trim, CBZ contents); pixel asserts exist only
  for the compositor tilt and the drawing-board patch. No screenshot comparison exists.
- No test drives two live browser clients; the closest is the unit-level thread-union pin.
- Only 2 tests touch the live OpenAI API, both text-only, both skipping silently when the
  API is unavailable — a broken live pipeline can pass a green suite.
- No CI configuration exists in the tree; gates run only when someone runs pytest locally.
- The scratch-clone practice ("never run mutating verification against a shared live
  instance") is a documented working rule, not enforced by any code.

Known warts: `test_ui_send.py` uses an unregistered
`module_under_test` mark that pytest warns about; the wall's comment promising a
drawing-board ribbon on the live issue is unimplemented — the live issue gets only a
tooltip.

## Design rules that bit us

Each of these is an invariant that was paid for. State them plainly; keep them true.

- **One truth per question.** Production status has exactly one source, `issue_ledger`;
  every surface quotes it. The Editor's law THE LEDGER IS THE TRUTH exists because a model
  will otherwise answer status questions from stale memory.
- **The book grid holds only pages.** Any non-page element inserted into the book's grid
  shifts two-up pairing. The page-turn bar rides a sheet's right edge, in the gutter; the
  closing covers hold their column by class, not by count.
- **Fresh before write.** A bench that writes an object must re-read it first
  (`fresh_board` before `update_object`), or an out-of-band edit — a dblclick, another
  window, the Editor mid-turn — is clobbered by stale state. This bug class recurred
  enough to earn source-level test pins.
- **The key names its own house.** Tool writes resolve their mount from the OBJECT's
  primary key via `storage_for_key`, never from ambient context — and a storage rooted
  outside the mounts is never hijacked (the carnival rule). The alternative destroyed live
  data once.
- **Every promise in the UI must be implemented.** Every button and chip must have a real
  tool or handler behind it, enforced by `test_button_promises.py` and
  `test_chips_match_tools.py`. The current `on_drop_reference` defect is what breaking
  this rule looks like: a drop target that swallows the file and reports success.
- **The pencil never clobbers a rough.** Destructive re-generation is always behind an
  explicit, negatively-styled confirmation; the default action on an already-roughed panel
  is proofing, not re-roughing.
- **Derived data bypasses the wastebasket; authored data never does.** Machine-stitched
  pages are hard-deleted and rewritten on every paint; everything the author made goes to
  the trash first, with a snapshot before overwrites.
- **Trim memory at turn boundaries.** The agent thread is trimmed only at whole user
  turns, never between a tool call and its output; the 80-item cap that ignored this
  produced visible amnesia.
