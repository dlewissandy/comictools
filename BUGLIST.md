# Bug List

All previously documented bugs have been fixed and verified (2026-07-10):

- ~~`agentic/tools/reader.py` — invalid `any(pk.keys(), ...)` usage~~ **Fixed**, along with the
  deeper root cause: `read_one`/`read_all` compared primary keys against `context[0]` (the
  shallowest selection) instead of `context[-1]` (the selected object), so reading the current
  selection always failed.
- ~~`agentic/tools/navigation.py` — `select_series` mutated `state.selection` directly~~ **Fixed**;
  now uses `change_selection` so breadcrumbs/details refresh and state persists.
- ~~`messaging.py` — `handle_message_output_event` ignores the generated message~~ **Verified
  working as designed**: message text is streamed into the response markdown via
  `raw_response_event` deltas, which cover post-tool messages as well.
- ~~`storage/local.py` — `find_reference_image` referenced undefined `relation`~~ **Fixed**; also
  `list_uploads` now lists reference uploads instead of generated images.
- ~~`main.py` — missing space when concatenating `MIDDLE_STYLING_CLASSES`~~ **Fixed**.
- ~~`schema/reference_image.py` — non-unique `id`~~ **Already fixed** in an earlier commit;
  `id` returns `image_id`.

## Known non-bugs (stale reports)

- `schema/styled_variant.py` `id` returning `style_id` is intentional: the GUI keys styled
  images by style (`variant.images[style_id]`) and `gui/styled_image.py` reads the selection id
  as a `style_id`. Changing it to `image_id` would break navigation.

## Open (design-level, not defects)

- `create_object` always assigns a fresh UUID as the object id (ignoring caller-provided slugs)
  unless `overwrite=True`. Consistent but ugly; see TASKLIST "Define consistent ID generation
  rules across all models".
