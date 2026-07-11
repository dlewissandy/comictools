# Asset Library — Design (2026-07-10)

**Problem.** Assets are imprisoned in their series. Characters, settings, and wardrobe
(variants) live under `data/series/{id}/…`; props are inline structs on settings/scenes,
not entities; nothing can be reused across issues in another series without hand-copying
JSON. Publisher is a name and a logo. Meanwhile styles are already global — the one
asset type the app treats as a studio resource, and the model to follow.

**Goal.** A publisher maintains a living asset collection — characters, outfits,
settings, props — and creators pull from it into any series, issue, scene, or panel,
conversationally ("add Mr. Witch to this issue", "use the cracked crystal ball here").

**Invariant.** Managing and using assets happens through the coauthor conversation.
A Library view exists to *browse*; acting on assets is talking.

---

## The fork: three ownership models

### A. Canonical publisher-owned assets (move)
Assets live at `data/publishers/{pid}/assets/…`; series hold references.

- ✅ True single source of truth; edit once, every book updates.
- ❌ Huge migration: `series_id` is baked into every primary key chain
  (CharacterModel, CharacterVariant, CharacterRef on panels/scenes/covers, all
  storage path templates, all tools, the reader context). Everything moves.
- ❌ Fights the current JSON-on-disk storage; this is really the Postgres-era model
  (TASKLIST already plans that migration).

### B. Copy-on-import with provenance (stamp)
Assets stay series-scoped. A Library index enumerates every asset across all series
(grouped by publisher via `series.publisher_id`). "Add X to series Y" deep-copies the
asset into Y, stamping `origin: {series_id, asset_id, imported_at}`.

- ✅ Ships now: every existing tool, key chain, and view keeps working untouched —
  the imported copy is a normal native asset.
- ✅ Matches comics reality: each book's version of a character may *deliberately*
  drift (different era, different wardrobe canon).
- ✅ Provenance enables later reconciliation ("Mr. Witch has drifted from the library
  original — want to sync?").
- ❌ Copies diverge; no push-updates from the original.

### C. Reference links with a resolution layer
Series keep a `linked_assets` manifest (local id → canonical id); storage resolves
reads through links.

- ✅ Single source of truth without moving files.
- ❌ Touches every read path; link-breakage and cycle questions; still awkward on
  JSON-on-disk. A halfway house that costs most of A while delivering less.

## Recommendation: B now, A at the database migration

Copy-on-import delivers the *felt* capability (reuse anything anywhere) immediately
and safely, and the provenance stamp is exactly the data a future canonicalization
needs — when storage moves to Postgres, `origin` fields become foreign keys and the
library becomes authoritative. B is not a detour; it is A's first phase.

---

## MVP slice (phase 1)

1. **Library root** — a fourth top-level section beside Series/Publishers/Styles:
   `/library`, browsable grid of all characters, settings, and props across every
   series, filtered by publisher/kind/search. Cards show the asset's home series and
   reference image. Browsing is a view; *acting* is conversation.
2. **Import tools** (wired to library, series, and issue agents):
   - `list_library_assets(kind?, publisher_id?, query?)`
   - `import_character(source_series_id, character_id, target_series_id)` — copies
     the character, all variants, and styled reference images; stamps origin.
   - `import_setting(source_series_id, setting_id, target_series_id)` — copies the
     setting, props, and master backgrounds; stamps origin.
3. **Props become entities** — `Prop` gains `prop_id` + optional reference image and
   lives at `data/series/{sid}/props/`; settings/scenes reference props by id (with
   inline description kept for backward compat). Enables "the cracked crystal ball"
   to exist once and dress three settings — and to be imported like anything else.
4. **Origin provenance** on Character/Setting/Prop: `origin: {series_id, asset_id,
   imported_at} | None`, shown on the asset card ("from Wonders of the Witchlight").
5. **Coauthor phrasing throughout**: "add Brassic to this series", "bring the
   fortune-teller tent into Dustfall", "what settings does DND Nerds have?" all work
   from the relevant views.

## Phase 2 (publisher-canonical, with the DB migration)

- Publisher-owned canonical assets; series *link* by default, fork explicitly.
- Drift detection: diff an imported copy against its origin; offer sync/fork.
- Wardrobe as first-class shared concept (outfit assets attachable to any character).
- License/usage metadata per asset (who may use what — the multi-user era).

## Open questions

- Series without a publisher (e.g. Joey): library groups them under "Independent"?
- Style-keyed images: importing a character into a series whose issues use a style
  the character has no reference sheet for — import should report it (same
  missing-reference discipline as rendering).
- Name collisions on import (slug ids): suffix vs. prompt the user.
