# UX Ideas: Path-Based Views for Multi-Window Sessions

## Problem
Today the app generates pages on the fly at the root path. Because the URL never changes, users cannot open multiple browser windows (or tabs) that point to different objects in the same session. We need stable, path-based routes so each window can deep-link to a specific view while sharing the same authenticated session.

## Goals
- Each window has a distinct URL that encodes the current selection.
- URLs are deep-linkable and reload-safe.
- Session auth stays shared across windows (cookie-based).
- Back/forward works in a predictable way.

## Design Alternatives

### 1) Hierarchical Resource Routes (most direct)
Use explicit, human-readable paths for the current selection, with IDs embedded.

Examples:
- `/series/:seriesId`
- `/series/:seriesId/issue/:issueId`
- `/series/:seriesId/issue/:issueId/scene/:sceneId`
- `/series/:seriesId/issue/:issueId/scene/:sceneId/panel/:panelId`
- `/styles/:styleId`, `/characters/:characterId`, `/publishers/:publisherId`

Pros:
- Clear, shareable URLs and breadcrumbs.
- Works naturally with browser history.
- Easy to add “Open in new window” using the current URL.

Cons:
- Requires consistent routing rules across all entities.
- Needs server fallback for client-side routes (serve app shell for all routes).

### 2) Workspace + Selection Query (simple and flexible)
Keep a workspace path and encode the selection in the query string.

Examples:
- `/workspace/:workspaceId?sel=series:123`
- `/workspace/:workspaceId?sel=issue:456&parent=series:123`
- `/workspace/:workspaceId?sel=panel:999&parent=scene:321`

Pros:
- Minimal routing surface; the app always loads one route.
- Easy to extend without restructuring path hierarchy.
- Works well if selection types change frequently.

Cons:
- URLs are less readable.
- Requires parsing to build breadcrumbs.

### 3) View State IDs (server-stored view snapshots)
When a user navigates, create a short-lived view state on the server and use it in the URL.

Examples:
- `/view/:viewId` where `viewId` maps to `{ selection, breadcrumbs, filters }`.

Pros:
- Fully decouples UI state from URL structure.
- Can include complex UI state (filters, tabs, grid modes).

Cons:
- Not transparent; URLs are opaque.
- Requires storage and TTL policies.
- Deep links expire unless persisted.

### 4) Generic Resource Route + Tab Context
Use a consistent path shape for all resources and store the UI “panel” or mode as a query.

Examples:
- `/r/series/:id?tab=issues`
- `/r/scene/:id?tab=panels`
- `/r/panel/:id?tab=images`

Pros:
- Very small router surface area.
- Easy to add new entity types.

Cons:
- Less semantic than hierarchical routes.
- Requires more client logic to resolve context.

## Recommendation (if we want clarity + shareable links)
Start with **Alternative 1 (Hierarchical Resource Routes)** or **Alternative 4 (Generic Resource Route)**.

- Alt 1 is best for readability and user mental model.
- Alt 4 is best for engineering speed and extensibility.

Both approaches support multiple windows because each window has its own URL, and session auth can stay cookie-based. The critical change is to move selection state into the URL (path and/or query) instead of keeping it only in a single in-memory root view.

## UX Notes
- Provide a visible “Open in new window” action near breadcrumbs or headers.
- Make breadcrumbs reflect the URL so sharing a link preserves context.
- On refresh, rehydrate selection from URL and load data accordingly.

## Multi-Window Constraint: Single-Threaded Chat Context
Current chat context is single-threaded and global. This prevents parallel, scoped conversations per window, which is a core expectation for MDI (each window/tab should carry its own context and chat history).

Implications:
- Opening two windows would mix or overwrite conversation context.
- Replies could target the wrong selection if both windows share one chat thread.

Mitigation Ideas:
- Introduce `conversation_id` scoped to the URL (e.g., query param or route state).
- Bind chat history and AI context to `conversation_id` + selection path.
- Optionally allow “fork conversation” when opening a new window, so users can branch context intentionally.
