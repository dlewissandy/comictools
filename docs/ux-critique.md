# UX Critique — Adversarial Pass (2026-07-10)

**Invariant:** the UI *is* a conversation with a coauthor. Nothing below replaces that;
every improvement either strengthens the conversation or removes friction around it.
Everything else is negotiable.

Method: three hostile walkthroughs of the real app — a first-time creator with a story
idea, a working artist mid-production on a 20-scene issue, and a writer returning after
a week away. Pain points are grounded in the current code, not hypotheticals.

---

## 1. The conversation forgets — the coauthor has amnesia

**Pain (severe).** Chat history is *cleared* when you navigate up the hierarchy
(`change_selection`), and each selection kind is a different agent with no memory of
what the previous one discussed. Work with the issue agent on story structure, click
into a scene, come back — the conversation is gone. A human coauthor would remember
what you decided five minutes ago. This is the single biggest violation of the app's
own metaphor.

**Improvements**
- Persist a conversation per object (`conversation_id` keyed to the selection path —
  already sketched in UX_ideas.md). Returning to a scene resumes that scene's thread.
- On agent hand-off (issue → scene), inject a one-paragraph summary of the parent
  conversation into the new agent's context: the scene agent should *know* what the
  issue agent just agreed to.
- Never destroy history as a side effect of navigation. Archive, don't clear.

## 2. Blank-box problem — the coauthor never speaks first

**Pain (severe).** Every view greets you with an empty input labeled "message." A new
user has no idea what this coauthor can do, and even experts must remember tool
vocabulary. The personas know their capabilities; the UI hides them.

**Improvements**
- The coauthor opens: on entering a view, the agent posts one short, context-aware
  line ("This scene has no panels yet — want me to thumbnail a layout from the story?").
  This *is* the conversation metaphor, finally bidirectional.
- 2–4 suggested-prompt chips above the input, per view state ("Break story into
  scenes", "Render missing panels", "Export the issue"). Clicking one sends it as a
  normal message — chips are conversation starters, not wired buttons.

## 3. Long renders lock the room

**Pain (severe).** Image generation takes 1–3 minutes; the send button disables and
the conversation is hostage to the render. Five panels = five serial calls in one
blocked turn. No cancel, no progress, no queue, no "I'll tell you when it's done."

**Improvements**
- Background render queue: render tools enqueue and return immediately; the coauthor
  reports completions in the chat ("Panel 3 is done — want a look?"). Conversation
  stays free while the studio works.
- `render_missing(scene|issue)` batch tool + progress line ("3 of 7 rendered").
- Cancel affordance on in-flight generations.
- Cost preflight: "Rendering this issue = 14 images ≈ $X. Go ahead?" — a coauthor
  asks before spending your money.

## 4. Page layout does not exist *(named pain)*

**Pain (severe).** Artists think in pages; the app thinks in panels. The reader and
PDF are a vertical strip — no Page/Spread model, no panel grids, no page breaks under
authorial control, no facing-page awareness. "Complete issue" currently means
"webcomic strip," not "comic book."

**Improvements**
- `Page` model: ordered panel slots + a layout (grid template or explicit rects),
  scenes flowing across pages. The agent proposes page breakdowns conversationally
  ("Scene 4 wants a splash page for the reveal — agree?").
- Page view in the details pane: live thumbnail of the composed page while you talk.
- Binder composes real page layouts (gutters, bleeds, page numbers); reader pages
  turn like a comic instead of scrolling.
- Panel aspect becomes a consequence of the page slot, not a free-floating choice —
  the layout constrains the shot, like real comics production.

## 5. One take, no contact sheet

**Pain (high).** A render is one image. If it's 80% right you either accept it,
re-roll blind (losing the good take? no — takes accumulate, but there's no comparison
UI), or enter the fiddly image-editor mode. No variations, no side-by-side, no
"keep the pose, fix the hand" quick path.

**Improvements**
- Generate N takes per render (the API supports n>1); show a contact sheet; pick in
  one click or say "the second one, but warmer."
- Inline region annotation on the selected image → feeds inpaint without the separate
  editor mode ceremony.
- The coauthor critiques its own takes: "take 2 kept Ezra on-model best" (a vision
  pass against the reference sheet — automated consistency checking).

## 6. Completeness is invisible until the end

**Pain (high).** Nothing shows production state. Scene cards don't say "4/6 panels
rendered"; the issue view doesn't say "2 scenes have no setting." The only
completeness measure lives in the export tool's afterthought note.

**Improvements**
- Production status on every card: rendered/total badges, missing-reference dots.
- An issue "pre-flight" panel (and matching agent tool): everything standing between
  now and a complete issue, ranked — the binder's missing-list, promoted to a
  first-class dashboard the coauthor can act on ("fix all of these?").

## 7. Trivial edits cost three conversation turns

**Pain (high).** Clicking ✏️ on "price" sends *"I would like to edit the price"* → the
agent asks what value → you type it. Three round-trips through an LLM to change a
number. That's not coauthoring; that's dictating a memo to a very slow assistant.

**Improvements (conversation-preserving)**
- Inline direct editing for scalar/short fields (price, date, names, time-of-day);
  the change is echoed into the chat as a receipt ("✏️ You set price to $3.99") so the
  coauthor stays aware. Substantive prose (stories, beats, descriptions) keeps the
  conversational path — that's where the coauthor adds value.
- Structured dialogue editor on panels (reorder/edit balloon lines directly), with
  the agent for punch-up ("make line 2 snappier").

## 8. Navigation is breadcrumbs-or-nothing

**Pain (medium).** Jumping from scene 3's panel to scene 7's panel means climbing up
and clicking down through card grids. 19 scenes with UUID ids; no tree, no search, no
recents. Deep links (new) help across windows but not within one.

**Improvements**
- Collapsible project tree in a drawer (series → issues → scenes → panels), with
  production-state badges doing double duty.
- Search-anything palette (Cmd-K): objects by name, and "ask the coauthor" as the
  fallback row — search *feeds* conversation.
- "Recently visited" chips.

## 9. Tool activity reads like a debugger, not a colleague

**Pain (medium).** The "Thoughts" expansion shows raw tool names and JSON args.
Mid-turn mutations are invisible until the full response lands (`is_dirty` refresh at
the end). Errors surface as agent apologies with stack-trace flavor.

**Improvements**
- Human receipts instead of raw calls: "🎨 Rendered panel 3 (view)", "✏️ Updated scene
  story", each linking to the object. Keep raw JSON behind a developer toggle.
- Refresh the details pane after each mutating tool call, not just at turn end — you
  watch the coauthor work.
- Error messages say what failed and offer the retry as a suggested chip.

## 10. The chat can't see images

**Pain (medium).** In an image-first studio, the conversation is text-only. You can't
paste a reference into the chat, point at a region, or say "more like this" with a
picture. Uploads are scattered per-view drop zones with inconsistent behavior.

**Improvements**
- Paste/drop images directly into the conversation; the coauthor sees them (vision)
  and can attach them as references to the current object.
- Rendered results appear inline in the chat thread as they complete, not only in the
  details grid.

## 11. No undo, no history, no safety net

**Pain (medium).** `update_issue_story` silently replaces; delete + confirm is gone
forever. There is no version history (TASKLIST knows). A coauthor that can't say
"here's what I changed — revert if you hate it" doesn't earn trust.

**Improvements**
- Before/after summary in chat for substantive rewrites ("I tightened the story —
  diff"), with one-click revert.
- Object-level version history (even naive: timestamped JSON snapshots) + "undo last
  change" tool.
- Soft-delete with a trash instead of `shutil.rmtree`.

## 12. Small paper cuts (quick wins)

- Scene/panel cards show raw scene numbers but not reading order across pages.
- Voice: no visible listening state on Dictate.
- UUID ids leak into URLs and agent replies; slugs exist for some types, not others
  ("define consistent ID generation" — TASKLIST).
- The image editor's mode/selection state is invisible until you ask.
- No mobile/narrow-viewport consideration at all.

---

## Priority shortlist

| # | Improvement | Pain | Effort |
|---|-------------|------|--------|
| 1 | Per-object conversations + hand-off summaries | severe | M |
| 2 | Coauthor speaks first + suggested-prompt chips | severe | S |
| 3 | Background render queue w/ chat notifications + batch render + cost preflight | severe | M |
| 4 | Page/Spread model, page view, real page-layout binding | severe | L |
| 5 | Contact-sheet takes + pick/refine loop | high | M |
| 6 | Production-status badges + pre-flight dashboard | high | S–M |
| 7 | Inline edit for scalar fields w/ chat receipts | high | S |
| 8 | Project tree + Cmd-K search | medium | M |
| 9 | Human-readable action receipts (replace raw tool JSON) | medium | S |
| 10 | Images in the conversation (paste/drop, inline results) | medium | M |
| 11 | Undo / versions / soft delete | medium | M–L |

S = hours, M = a day-ish, L = multi-day. #2, #6, #7, #9 are the highest
pain-relief-per-effort; #1 and #4 are the structural ones that change what the
product *is*.
