# Task List

- Add agent tools for character name updates, variant creation from image, and variant deletion; wire into `agentic/toolkits.py` (around lines 146–197).
- Implement issue name update and scene reordering support in `agentic/toolkits.py` (lines 184, 196).
- Persist send-button state and handoff history in `messaging.py` (`TODO` markers at lines 67, 152, 177).
- Make cover generator text elements configurable in `agentic/tools/imaging.py` (around line 191).
- Add storyboard→panels conversion UI and panel reordering/empty-state fixes in `gui/scene.py` (line 73) and `gui/panel.py` (lines 154–155).
- Clean up card rendering API (Callable vs literal kind) and add reference-image drop region in `gui/elements.py` (lines 325, 596).
- Define proper `parent_key`/ID fields for `ReferenceImage` in `schema/reference_image.py` to allow reliable storage/lookup.
- Expand scenes to capture richer setting details and support generating/managing multi-angle reference images.
- Add a way to generate panels from a scene/story (e.g., split story into panel beats and create panels automatically).
