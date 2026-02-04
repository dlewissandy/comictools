# Bug List

- `agentic/tools/reader.py:99` — `any(pk.keys(), ...)` is invalid and raises `TypeError`; replace with a generator check like `any(k not in TOP_LEVEL_IDS for k in pk)`.
- `agentic/tools/navigation.py:64-75` — `select_series` mutates `state.selection` directly, bypassing `change_selection`, so breadcrumbs/details don’t refresh and state isn’t persisted.
- `messaging.py:97-104` — `handle_message_output_event` ignores the generated message; no UI output is appended for tool-driven responses.
- `storage/local.py:335-347` — `find_reference_image` references undefined `relation` and uses the uploads list rather than reference uploads, causing lookup failures.
- `main.py:64` — missing space when concatenating `MIDDLE_STYLING_CLASSES` results in an invalid class string for the middle pane.
- `schema/reference_image.py:18-27` — `id` returns only `relation.value`, producing non-unique IDs and potential overwrites in storage.
