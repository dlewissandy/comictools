# Database Design: Comic Workspace Storage

## Summary
We should use **PostgreSQL as the primary database** (managed, e.g., Supabase/Neon/RDS) with **JSONB for nosql-ish structures**, **row-level security (RLS)** tied to the auth provider, and **object storage** (S3-compatible or Supabase Storage) for images. This gives us strong consistency for the core graph (series → issues → scenes → panels), flexible fields for evolving schemas, and first-class security for user preferences.

## Requirements (from product vision)
- Structured, hierarchical data (series, issues, scenes, panels, characters, variants).
- “Nosql-ish” flexibility for evolving fields and metadata.
- Image assets (uploads + generated images) stored and retrieved efficiently.
- User preferences must be secure and isolated by user/org.
- Works with a future auth strategy (OAuth/OIDC or managed auth).

## Options Considered
1. **PostgreSQL + JSONB + Object Storage**
   - Pros: Strong relational modeling, JSONB for flexible metadata, mature ecosystem, good auth integration via RLS, easy analytics.
   - Cons: Slightly more upfront schema design than pure document stores.

2. **MongoDB + Object Storage**
   - Pros: Naturally flexible documents, easy to model hierarchical JSON.
   - Cons: We still need relational integrity for cross-references; auth/row-level security often implemented in app code, which is riskier.

3. **Firestore/Firebase**
   - Pros: Built-in auth, scalable, realtime.
   - Cons: Complex querying for relational graph, more vendor lock-in, cost can scale unexpectedly for heavy reads/writes.

## Recommendation
**PostgreSQL with JSONB** provides the best balance of structure and flexibility, especially for a product with a clear hierarchy and many cross-references. It is the safest choice for secure user preferences when combined with auth-aware RLS. Images should live in object storage with metadata and selection state in Postgres.

## Data Model (High Level)
Core entities (relational):
- `users` (or `auth_users` reference from provider)
- `workspaces` / `organizations`
- `series`, `issues`, `scenes`, `panels`
- `characters`, `variants`
- `styles`, `publishers`
- `images` (metadata + storage pointer)

Flexible fields (JSONB):
- `metadata` on most entities for evolving fields (camera notes, tags, seed settings, AI prompts)
- `settings` and `preferences` for user-specific options

Example patterns:
- `series` has `id`, `workspace_id`, `title`, `summary`, `metadata` (JSONB)
- `panel` has `id`, `scene_id`, `beat`, `description`, `aspect_ratio`, `metadata` (JSONB)
- `images` has `id`, `owner_type`, `owner_id`, `kind` (reference/generated/final), `storage_key`, `width`, `height`, `metadata` (JSONB)

## Image Storage
- Store images in S3-compatible object storage.
- Store the object key/URL + metadata in `images` table.
- Use **signed URLs** or proxy endpoints for access, scoped by auth.
- Keep “selected” image for each panel/cover as a foreign key (e.g., `panel.selected_image_id`).

## Auth Strategy Integration
The database needs to align with the chosen auth approach. Two viable paths:

1. **Managed Auth (Supabase/Clerk/Auth0)**
   - Store `auth_user_id` in `users` table.
   - Use JWT claims to enforce **RLS** on user-owned data.
   - Example: `workspace_id` or `user_id` checks in RLS policies.

2. **Custom Auth**
   - Store password hashes using Argon2id (never plaintext).
   - Issue JWTs signed by the app; map JWT `sub` to `users.id`.
   - Enforce per-user policies in DB using RLS or in app layer.

**Recommendation**: Use managed auth + RLS to reduce risk and simplify security.

## Security for User Preferences
User preferences may include personal data or API keys. Approach:
- Store preferences in `user_preferences` table with `user_id` FK.
- Encrypt sensitive fields with envelope encryption (KMS) if needed.
- RLS: users can only read/write their own preferences.
- Avoid placing secrets inside JSONB unless encrypted.

## Operational Considerations
- Use migrations for schema evolution; keep JSONB for additive fields.
- Add indices on foreign keys and JSONB keys used in filters.
- Consider `pgvector` later if embedding search becomes a requirement.
- Use read replicas if heavy read usage emerges.

## Risks and Mitigations
- Risk: Overusing JSONB can reduce queryability.
  - Mitigation: Keep relational columns for core fields; use JSONB for optional fields.
- Risk: Security holes if RLS not enabled.
  - Mitigation: Make RLS default and test policies.

## Next Steps
- Confirm auth provider choice (Supabase Auth vs other).
- Draft initial schema + migrations for core entities.
- Decide object storage provider and bucket structure.
