# Task List

## Core Product Scope
- Define canonical product scope for “multiuser, AI-first comic authoring and publishing” and align `docs/vision.md` and `vision.md`.
- Decide the single source of truth for product docs and de-duplicate or redirect the other vision file.
- Specify target personas (writer, artist, editor, publisher admin) and success metrics per persona.
- Define MVP vs. v1 vs. v2 feature slices for planning.

## Critical Bugs & Code Fixes
- Fix `agentic/tools/reader.py` invalid `any(pk.keys(), ...)` usage and top-level key logic.
- Fix `agentic/tools/navigation.py` to use `state.change_selection` rather than mutating `state.selection`.
- Fix `messaging.py` to append tool-driven responses in `handle_message_output_event`.
- Fix `messaging.py` to properly disable/re-enable the send button during requests.
- Fix `agentic/tools/__init__.py` missing imports for `update_issue_*` and the missing comma in `__all__`.
- Fix `agentic/tools/updater.py` `update_dialog_style` to target `bubble_styles` instead of non-existent `dialog_style`.
- Fix `agentic/tools/creator.py` `create_issue` to set `Issue.name` (not `title`) and correct `series_id`.
- Fix `agentic/tools/creator.py` default `insertion_location` to an instance of `AfterLast`.
- Fix `agentic/tools/imaging.py` to initialize `style.image` dict before writing keys.
- Fix `agentic/tools/imaging.py` styled image ID format string in `create_styled_image_for_character_variant`.
- Fix `schema/styled_variant.py` `id` to return `image_id` and `name` to include the image identifier.
- Fix `storage/local.py` `list_uploads` to use reference upload paths, not image paths.
- Fix `storage/local.py` `find_reference_image` to remove undefined `relation` and use reference uploads.
- Fix `storage/filepath.py` StyleExample path templates and `IMAGE_PATH_TEMPLATES` keying.
- Fix `schema/reference_image.py` `primary_key`/`parent_key` semantics to support reliable storage and lookup.
- Fix `gui/issue.py` delete button to call `post_user_message(state, ...)` with state.
- Fix `gui/style.py` and `gui/scene.py` use of `style.id` to `style.style_id`.
- Fix `gui/style.py` to handle `style.image` being `None` before indexing.
- Fix `gui/panel.py` `aspect_ratio={aspect}` to pass a string, not a set.
- Fix `gui/panel.py` `panel_selector` selection building (`state.selection` vs `state`).
- Fix `gui/scene.py` panel image rendering path (`scene.path` and `image.py` placeholders).
- Fix `gui/reference_image.py` to use object-specific uploads rather than global `data/uploads`.
- Fix `gui/reference_image.py` missing f-string in `name = "Panel {parent.panel_number}"`.
- Fix `gui/style.py` `storage.read_object(...)(...)` call in `view_pick_style`.
- Fix `main.py` missing space when concatenating `MIDDLE_STYLING_CLASSES`.
- Make cover generator text elements configurable in `agentic/tools/imaging.py`.
- Add missing toolkits for character name update, variant creation from image, and variant deletion.
- Add scene reordering and panel reordering tools and UI support.
- Add issue name update tool and wire it into the issue toolkit.

## Data Model Expansion
- Add `User`, `Organization`, `Workspace`, `Membership`, and role/permission models.
- Add `Project` or `Title` entity to group series, issues, assets, and collaborators.
- Add `Page` / `Spread` models for publishing layout, trim, bleed, and placement.
- Add `Asset` model for images with metadata (source, version, tags, ownership).
- Add scene setting metadata model (location, time, weather, mood, props, lighting).
- Add multi-angle reference set model for scenes and locations.
- Add `Comment` / `Annotation` model for collaboration feedback on any entity.
- Add `Version` / `Change` model for audit history and revert.
- Add `Task` / `Approval` model for editorial workflow (review, approve, publish).
- Define consistent ID generation rules across all models.

## Storage & Scalability
- Replace local JSON file storage with a scalable database (Postgres or equivalent).
- Implement migrations for all schema changes and seeded data.
- Build a data migration tool from current local storage to the new database.
- Move images to object storage (S3/GCS/R2) with signed URLs and metadata.
- Add indexing strategy for fast search across series/issues/scenes/panels.
- Add pagination and batching for large lists in UI and API.

## Backend/API Layer
- Introduce a service layer (CRUD + business logic) between UI and storage.
- Implement API endpoints for all entities with validation and error handling.
- Add WebSocket or realtime channels for collaboration updates.
- Add access-control middleware to enforce roles and workspace isolation.
- Add rate limiting and request tracing for AI and image endpoints.

## AI & Agent System
- Add prompt templates for panels, scenes, issues, and series (currently missing).
- Implement panel image generation (prompt building + render + selection).
- Implement scene-to-panels storyboard generation using structured outputs.
- Add a single-shot storyboard/beatboard tool to generate a full panel set from a scene.
- Add AI critique and revision tools (beat notes, pacing, continuity).
- Add AI tools for adding character references and reference images.
- Add AI tools for editing panels (beat, description, dialogue, narration).
- Add AI tools for issue name updates and scene ordering.
- Add model selection, cost controls, and per-workspace quotas.
- Add prompt injection safeguards and system-level safety constraints.
- Update models to current GPT and image generation models in configuration.

## Imaging Pipeline
- Fill empty prompt templates in `data/prompts/imaging/*`.
- Standardize prompt format across covers, panels, styles, and variants.
- Add image versioning, re-rolls, and selection history.
- Add inpainting/outpainting and masking UI flows.
- Add image metadata capture (prompt, references, seed, model).
- Add consistent reference image selection and ordering rules.

## UI/UX Core
- Replace ad-hoc `post_user_message` flows with explicit UI actions and state updates.
- Add inline editing for all fields (issue name, scene story, panel beat, etc.).
- Add drag-and-drop reordering for scenes and panels.
- Add clear empty states and “next action” guidance.
- Add global search and filters (series, issues, characters, assets).
- Add asset library view with tagging and reuse.
- Add undo/redo and change history views.
- Add error and validation feedback for all CRUD operations.
- Add reference-image drop zones and explicit relation tagging in the UI.

## Collaboration Features
- Implement authentication (email/password, OAuth, or SSO).
- Add workspace invites and member management UI.
- Add permissions matrix (owner/admin/editor/viewer).
- Add realtime presence indicators and activity feed.
- Add inline comments and threaded discussions on panels and scenes.
- Add conflict resolution and optimistic locking for concurrent edits.
- Add audit log views with restore/version comparison.

## Publishing Pipeline
- Define publishing formats (PDF, CBZ, PNG bundles) and specs.
- Implement page layout editor (panel placement, gutters, bleed/trim).
- Implement lettering and typography tools or integration path.
- Add cover metadata (ISBN, pricing, credits, legal notices).
- Add export workflows and automated validation checks.
- Add preview mode for full issue review and approvals.

## Architecture & Documentation
- Create architecture doc (frontend, backend, storage, AI services).
- Create data model ERD and entity relationship diagrams.
- Create interaction diagrams for core flows (create series, generate panels, publish).
- Create UX flows for multiuser collaboration and approvals.
- Create API specification and endpoint documentation.
- Update README to match NiceGUI app entrypoint and setup steps.

## Testing & Quality
- Add unit tests for schema validation and storage paths.
- Add integration tests for CRUD and AI tool flows.
- Add UI tests for navigation, creation, and rendering flows.
- Add image generation tests with mocked providers.
- Add linting/formatting (ruff/black) and CI pipeline.

## Observability & Operations
- Add structured logging for UI events and AI actions.
- Add metrics for generation latency, failures, and usage.
- Add error reporting (Sentry or equivalent).
- Add environment config management and secrets handling.
- Add deployment scripts and production configuration.

## Security & Compliance
- Add content moderation for text and image generation.
- Add data privacy policy and retention controls.
- Add workspace isolation tests and access audits.
- Add secure storage for API keys and credentials.

## Product Design & UX Documentation
- Write a design system overview (typography, color, spacing, components).
- Document UI conventions for AI actions and human edits.
- Create onboarding and first-project walkthrough docs.
- Create interaction specifications for AI chat vs. direct edit actions.
