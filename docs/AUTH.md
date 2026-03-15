# Authorization Strategy

## Goals
- Keep the creator in control while keeping access friction low.
- Ensure all data and assets are scoped to a workspace and protected by default.
- Keep the system lightweight today, while enabling multi-user expansion later.

## Non-Goals (for now)
- Complex enterprise RBAC.
- Multi-tenant collaboration workflows beyond a small workspace model.
- Custom identity provider buildout.

## Guiding Principles
- Default deny: all access requires an authenticated user and workspace scope.
- Authorization enforced as close to data as possible (Postgres RLS).
- Keep the app simple: small role set, predictable permissions.
- Avoid long-lived secrets on clients.

## Agent as Persistent Team Participant
To make the agent a true member of the team, it needs scoped, auditable memory tied to the same workspace and authorization model, without requiring formal "tasks."

Core requirements:
- The agent has a stable identity within a `workspace_id`.
- Each window/session has its own short-lived working context; persistent memory remains workspace-scoped.
- Memory is permissioned like any other data object.
- The agent can synthesize cross-session insights, but never bypasses workspace access rules.

Memory scopes:
- `workspace_memory`: team norms, terminology, preferred workflows.
- `session_memory`: per-window context that expires or is explicitly saved.
- `personal_memory` (optional): individual preferences and working styles, only with explicit consent.
- `pinned_context` (optional): user-labeled context saved from a session without requiring a task model.

Controls and safety:
- Every memory write is attributed (`created_by`, `created_at`) and auditable.
- Memory can be viewed, edited, or deleted by workspace `owner` (and optionally `editor`).
- Personal memory is opt-in and visible to the person it references.

This makes the agent persistent without weakening access boundaries, and keeps memory consistent with RLS and the broader data ownership model.

## Recommended Approach (Aligned With DB Design)
- Use managed auth (Supabase Auth, Clerk, or Auth0) with OIDC/JWTs.
- Store core graph in Postgres; use Row-Level Security (RLS) for access control.
- Store images in object storage; serve via signed URLs or a scoped proxy.

This matches the database design recommendation and keeps auth risk low while preserving a clear upgrade path.

## Identity Providers (Multi-Authenticator Support)
Support multiple OIDC providers from day one:
- Google
- Apple
- Microsoft (Live/Entra)

Implementation notes:
- Use the auth provider's built-in account linking to map multiple provider identities to a single app user.
- Treat email as a hint, not a primary key; require verified email for account linking.
- Maintain a separate `auth_identities` table (or provider-managed equivalent) with:
  - `user_id`, `provider`, `provider_subject`, `email`, `email_verified`, `created_at`
- Keep a stable internal `users.id` as the primary key for workspace ownership and preferences.

Account linking rules (safe defaults):
- If a user signs in with a new provider and a verified email matches an existing user, link after explicit user confirmation.
- If no match, create a new user and identity record.
- If email is unverified (common with some Apple relay flows), do not auto-link.

Provider-specific notes:
- Apple may provide relay emails; store and treat as normal but do not assume it is unique across providers.
- Microsoft has both personal (Live) and enterprise (Entra) accounts; support both via OIDC.
  - If enterprise is added later, treat it as a separate provider or tenant-scoped provider.

## Data Ownership Model
- Every record is scoped to a `workspace_id`.
- Each user belongs to one or more workspaces.
- All data access checks are based on `(user_id, workspace_id)`.

Tables should include:
- `workspaces` (id, name, owner_user_id, created_at)
- `workspace_members` (workspace_id, user_id, role)
- Core entities (series, issues, scenes, panels, characters, variants, styles, images) with `workspace_id` and `created_by`.

## Roles and Permissions (Lightweight)
Start with a minimal, studio-style model:
- `owner`: full access (CRUD + manage members + billing).
- `editor`: CRUD on all workspace content.
- `viewer`: read-only access.

MVP can safely start with just `owner` (single-user workspace) and add `editor`/`viewer` later without schema churn.

## Shared Content (Partial Collaboration)
Support collaboration on all or part of a document by combining workspace roles with object-level grants.

Workspace roles:
- Apply to the entire workspace by default.
- `owner` and `editor` can share content with others.
- `viewer` can only read shared content.

Object-level grants:
- Allow sharing a specific `series`, `issue`, `scene`, `panel`, or `image`.
- Grants can be assigned to a `user` (and later `team`).
- Grant roles mirror workspace roles (`editor`, `viewer`).
- Grants can include `expires_at` for temporary access.

Inheritance:
- Sharing a parent object shares its descendants by default.
- Example: sharing an `issue` grants access to its `scenes`, `panels`, and `images`.
- If needed later, explicit overrides can be added, but MVP avoids deny rules.

Data model (minimal):
- `access_grants` (workspace_id, object_type, object_id, principal_type, principal_id, role, created_by, created_at, expires_at)
- Optional `teams` and `team_members` when group sharing is needed.

## Authorization Rules (RLS-first)
Use RLS on all workspace-scoped tables:
- Read: user must be a member of the record's workspace.
- Write: user must be `owner` or `editor` **and** the row's `workspace_id` must match a workspace the user is a member of.
- Admin: only `owner` can manage members or delete workspace.

Example policy intent (not exact SQL):
- `select` where `exists (workspace_members where user_id = auth.uid and workspace_id = row.workspace_id)`
- `insert` where role in (`owner`, `editor`) **and** `workspace_id` is in the user's workspaces
- `update/delete` where role in (`owner`, `editor`) **and** `workspace_id` is in the user's workspaces

Shared content policy intent:
- `select` also allowed when an `access_grant` exists for the row or an ancestor.
- `insert/update/delete` also allowed when an `access_grant` with role `editor` exists for the row or an ancestor.

Additional guards:
- Make `workspace_id` immutable after insert (prevent cross-workspace row moves).
- Use database constraints or triggers to enforce `created_by = auth.uid()` on insert.
- Keep RLS enabled by default and explicitly opt out only for trusted server-only jobs.

## Sessions and Tokens
- Use provider-issued JWTs; short-lived access tokens, refresh handled by SDK.
- Store tokens in httpOnly cookies when possible to reduce XSS risk.
- Do not store tokens in localStorage.
- If cookies are used, enforce CSRF protections (SameSite=Lax/Strict, CSRF tokens on state-changing requests).

## Image Access
- Images live in object storage.
- Access via signed URLs scoped to the authenticated user and workspace.
- Image metadata in `images` table is guarded by RLS.
- Signed URL issuance must pass the same RLS checks as the `images` row (never sign by key alone).

## User Preferences and Secrets
- Store preferences in `user_preferences` with `user_id` FK and RLS.
- Encrypt any sensitive fields (API keys) with envelope encryption.
- Avoid placing secrets in JSONB unless encrypted.

## Auditing (Lightweight)
- Track `created_by`, `updated_by`, `created_at`, `updated_at` on core tables.
- Optional event log later if collaboration grows.

## Minimal MVP Checklist
- Managed auth provider configured.
- Postgres RLS policies for all workspace-scoped tables.
- `workspace_members` table + role enum.
- Signed URL flow for image access.
- Basic audit fields on core tables.

## Future Expansion
- Invite flows for multi-user collaboration.
- Additional roles (e.g., `producer`, `artist`) if needed.
- Org-level billing and SSO if enterprise becomes a focus.
- Explicit sharing rules (public links or cross-workspace sharing) should be modeled as a separate, auditable access path with clear expiry and revocation.

## Rationale
This strategy keeps authorization lightweight and secure while matching the product vision: a creator-first, studio-style workflow where AI assists but does not own or expose user content. RLS provides a strong default-deny posture without adding app-layer complexity, and the minimal role model supports the current single-user focus while enabling collaboration later.
