# Memory Model

## Purpose
Provide a persistent, permissioned memory system that helps the agent act as a reliable team participant without requiring a formal task model.

## Principles
- Workspace-first: all persistent memory is scoped to a `workspace_id`.
- Session-safe: each window/session has its own short-lived context to prevent bleed.
- Auditable: every write has `created_by`, `created_at`, and a source trail.
- Consent-based: personal memory is opt-in and visible to the person it describes.
- Forgetful by default: low-signal memory should decay unless explicitly pinned.

## Memory Types
- `workspace_memory`: stable team norms, vocabulary, conventions, and default decisions.
- `session_memory`: temporary context for a single window/session; expires or is discarded by default.
- `pinned_context`: user-labeled context saved from a session without a task/issue model.
- `personal_memory`: individual preferences and working styles, only with explicit consent.

## Lifecycle
1. Capture: summarize interactions into short, structured notes.
2. Distill: periodically roll up session notes into workspace norms or a pinned context.
3. Pin: user explicitly saves a named context for future reuse.
4. Decay: unpinned session memory expires; stale workspace memory is reviewed or pruned.

## Multi-Window Behavior
- Each window has an isolated `session_memory` scope.
- All windows share the same `workspace_memory`.
- If two windows write to the same memory object, last write wins with an audit trail.
- Users can explicitly merge a session into `pinned_context` or workspace norms.

## Authorization and Access
- Memory objects are stored like any other workspace-scoped data.
- RLS applies to all memory tables.
- `owner` (and optionally `editor`) can view/edit/delete workspace memory.
- Personal memory is readable by the subject and workspace `owner`.

## Data Model (Minimal)
- `memory_objects` (id, workspace_id, scope, title, body, created_by, created_at, updated_at, expires_at, visibility)
- `memory_links` (memory_id, related_object_type, related_object_id)
- Optional: `memory_events` for append-only audit trails.

## UX Notes
- Visible session context per window.
- Explicit "Pin" and "Forget" actions.
- Memory review surfaces for owners (cleanup and corrections).

## Open Questions
- Default expiration for `session_memory` (e.g., 24h or end of session).
- How often to prompt for distillation of recurring patterns.
- Whether to allow opt-in cross-workspace memory (likely no).
