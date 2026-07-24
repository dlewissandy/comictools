"""THE ONE CONVERSATION: typed entries, one thread, honest migration.

The model of record is state.thread — these pins hold the flatten
migration lossless, the merge law, and the work-entry fold."""
from gui.thread import flatten_conversations, merge_threads, persistable


def test_flatten_migration_keeps_every_word():
    """Every user and staff word in the old per-room shape survives the
    flatten; tool rows fold into work entries; the current room comes LAST."""
    conversations = {
        "/series/wl": [
            {"name": "You", "text_html": "<p>write me a story</p>", "sent": True},
            {"name": "the Editor", "text_html": "<p>Here is a story about ZANZIBAR.</p>", "sent": False},
            {"name": "Tool Call", "text_html": "<p>🆕 Create scene</p>", "sent": False},
            {"name": "Tool Output", "text_html": "<p>Created the scene.</p>", "sent": False},
            {"name": "the Editor", "text_html": "<p>Done — the scene stands.</p>", "sent": False},
        ],
        "/publishers/dnd": [
            {"name": "You", "text_html": "<p>show me the QUOKKA logo</p>", "sent": True},
        ],
    }
    thread = flatten_conversations(conversations, current_key="/series/wl")

    texts = " ".join(e.get("text") or "" for e in thread)
    assert "ZANZIBAR" in texts and "QUOKKA" in texts and "write me a story" in texts
    kinds = [e["t"] for e in thread]
    assert kinds.count("room") == 2, "each old room contributes one caption"
    assert "work" in kinds, "consecutive tool rows fold into a work entry"
    # the current room's words come LAST so a reload lands mid-conversation
    last_user = [e for e in thread if e["t"] == "user"][-1]
    assert "write me a story" in last_user["text"]
    # every entry is persistable: ids, timestamps, no live handles
    assert all(e.get("id") and e.get("ts") for e in thread)
    assert persistable(thread) == [e for e in thread if e["t"] != "work" or e.get("receipts")]


def test_flatten_skips_empty_rooms():
    thread = flatten_conversations({"/series/empty": [], "/": None}, current_key=None)
    assert thread == []


def test_merge_threads_unions_by_id_and_orders_by_ts():
    a = [{"id": "1", "ts": 1.0, "t": "user", "text": "first"},
         {"id": "2", "ts": 3.0, "t": "reply", "text": "third"}]
    b = [{"id": "1", "ts": 1.0, "t": "user", "text": "first"},
         {"id": "3", "ts": 2.0, "t": "user", "text": "second"}]
    merged = merge_threads(a, b)
    assert [e["text"] for e in merged] == ["first", "second", "third"]


def test_work_entries_without_receipts_never_persist():
    entries = [
        {"id": "a", "ts": 1.0, "t": "user", "text": "hi"},
        {"id": "b", "ts": 2.0, "t": "work", "status": "done", "receipts": [],
         "_close": lambda s: None},
        {"id": "c", "ts": 3.0, "t": "work", "status": "done",
         "receipts": [{"line": "🆕 **Create scene**", "quiet": False,
                       "answer": "Created.", "image": None}]},
    ]
    kept = persistable(entries)
    assert [e["id"] for e in kept] == ["a", "c"]
    assert all(not k.startswith("_") for e in kept for k in e), "live handles never hit disk"


def test_work_summary_speaks_the_work():
    from gui.thread import _work_summary
    entry = {"status": "done", "receipts": [
        {"line": "x", "quiet": True, "answer": None, "image": None},
        {"line": "y", "quiet": False, "answer": None, "image": "a.jpg"},
        {"line": "z", "quiet": False, "answer": None, "image": "b.jpg"},
    ]}
    s = _work_summary(entry)
    assert "3 step" in s and "2 pieces inked" in s
    entry["status"] = "stopped"
    assert "stopped at your word" in _work_summary(entry)


def test_merge_lets_the_writers_fresh_copy_win():
    """A coalesced room caption re-labeled in memory beats its stale twin
    on disk — same id, the writer's copy wins."""
    disk = [{"id": "m", "ts": 1.0, "t": "room", "name": "Old Room"}]
    mine = [{"id": "m", "ts": 5.0, "t": "room", "name": "Joey"}]
    merged = merge_threads(disk, mine)
    assert len(merged) == 1 and merged[0]["name"] == "Joey"


def test_render_thread_keeps_the_chat_pure(user=None):
    """THE CHAT IS THE CONVERSATION: projecting the thread renders balloons
    and captions — never asides (asides are toast-only receipts)."""
    entries = [
        {"id": "1", "ts": 1, "t": "user", "text": "hello"},
        {"id": "2", "ts": 2, "t": "aside", "text": "🗑 struck a thing", "bench": "b", "image": None},
        {"id": "3", "ts": 3, "t": "work", "status": "done",
         "receipts": [{"line": "did", "quiet": False, "answer": None, "image": None}]},
        {"id": "4", "ts": 4, "t": "reply", "text": "hi there"},
    ]
    # the projection logic itself: asides are skipped, work folds into reply
    import gui.thread as th
    rendered = []
    orig_work = th._render_work
    th._render_work = lambda s, e, live: rendered.append(f"work-{e['id']}")
    try:
        from types import SimpleNamespace
        import contextlib

        class _FakeUI:
            def __getattr__(self, name):
                def make(*a, **k):
                    class _El:
                        def classes(self, *a, **k): return self
                        def style(self, *a, **k): return self
                        def props(self, *a, **k): return self
                        def __enter__(self): return self
                        def __exit__(self, *a): return False
                    return _El()
                return make
        orig_ui, th.ui = th.ui, _FakeUI()
        orig_ccm = None
        import gui.avatars as av
        orig_ccm = av.comic_chat_message
        av.comic_chat_message = lambda **k: th.ui.element("div")
        th._render_entries(SimpleNamespace(history=None), entries)
    finally:
        th._render_work = orig_work
        th.ui = orig_ui
        av.comic_chat_message = orig_ccm
    assert rendered == ["work-3"], \
        "asides never render in the chat; the turn's work folds into the reply balloon"


def test_begin_turn_orders_work_before_reply():
    """begin_turn appends work THEN reply — so a reload folds the work line
    inside the reply balloon (the projection reads them in order)."""
    from types import SimpleNamespace
    import gui.thread as th

    class _FakeUI:
        def __getattr__(self, name):
            def make(*a, **k):
                class _El:
                    def classes(self, *a, **k): return self
                    def style(self, *a, **k): return self
                    def props(self, *a, **k): return self
                    def clear(self): pass
                    def delete(self): pass
                    def __enter__(self): return self
                    def __exit__(self, *a): return False
                    content = ""
                return _El()
            return make
    import gui.avatars as av
    orig_ui, th.ui = th.ui, _FakeUI()
    orig_ccm = av.comic_chat_message
    av.comic_chat_message = lambda **k: th.ui.element("div")
    try:
        state = SimpleNamespace(thread=[], history=th.ui.element("div"))
        work, refresh, reply, md = th.begin_turn(state)
        kinds = [e["t"] for e in state.thread]
        assert kinds == ["work", "reply"]
        # a turn that touched nothing leaves NO work line
        work["_close"]("done")
        assert [e["t"] for e in state.thread] == ["reply"]
    finally:
        th.ui = orig_ui
        av.comic_chat_message = orig_ccm


def test_root_is_the_lobby():
    """THE FRONT DOOR: / parses to the lobby and the lobby prints as /."""
    from gui.routes import selection_from_path, selection_to_url
    from gui.selection import SelectionItem, SelectedKind
    from types import SimpleNamespace
    sel = selection_from_path(SimpleNamespace(), [])
    assert sel and sel[0].kind == SelectedKind.LOBBY
    assert selection_to_url([SelectionItem(name="Studio", id=None,
                                           kind=SelectedKind.LOBBY)]) == "/"
    # the retired all-series root still prints / so old trails re-home
    assert selection_to_url([SelectionItem(name="Series", id=None,
                                           kind=SelectedKind.ALL_SERIES)]) == "/"


def test_the_conversation_is_the_modal():
    """A bench prompt that only wants words rides the conversation box:
    the one-shot intercept runs the work directly, carries the words in
    the thread, and stands down if the author changed the subject."""
    import asyncio
    from types import SimpleNamespace
    from messaging import send

    ran = []

    def make_state(value, intercept):
        return SimpleNamespace(
            _sending=False,
            user_input=SimpleNamespace(value=value, run_method=lambda *a: None,
                                       update=lambda: None, _props={}),
            _input_intercept=intercept,
            thread=[], history=None,
            write=lambda: None, selection=[],
        )

    # Enter with a direction → the handler runs with the words
    st = make_state("Pose Ezra: arms crossed, smirking",
                    ("Pose Ezra: ", lambda d: ran.append(d), None))
    asyncio.run(send(state=st))
    assert ran == ["arms crossed, smirking"]
    assert [e["t"] for e in st.thread] == ["user"], "the words ride the thread"
    assert st._input_intercept is None, "one shot only"

    # Enter alone → None (the script decides)
    ran.clear()
    st = make_state("Pose Ezra: ", ("Pose Ezra: ", lambda d: ran.append(d), None))
    asyncio.run(send(state=st))
    assert ran == [None]

    # the author erased the prefix and asked something else → stand down
    ran.clear()
    st = make_state("what styles do we have?",
                    ("Pose Ezra: ", lambda d: ran.append(d), None))
    try:
        asyncio.run(send(state=st))
    except Exception:
        pass   # it fell through toward the real agent path — that's the point
    assert ran == [] and st._input_intercept is None


def test_every_selection_kind_walks_the_context():
    """EVERY kind must pass through selection_to_context without raising —
    the 'Unknown selection kind: lobby' failure class dies here."""
    from gui.selection import SelectedKind, SelectionItem, selection_to_context
    for kind in SelectedKind:
        sel = [SelectionItem(name="x", id="some-id", kind=kind)]
        try:
            selection_to_context(sel)
        except ValueError as ex:
            raise AssertionError(f"{kind.value} raises: {ex}")


def test_lobby_chips_keep_their_promises():
    """The resume chip is a DOOR (change_selection, no agent turn); the
    status chip names the real bench; the starter chip is a prefill."""
    from types import SimpleNamespace
    from gui.coauthor import opening_and_chips
    from gui.selection import SelectionItem, SelectedKind as K
    walked = []
    resume = [SelectionItem(name="Studio", id=None, kind=K.LOBBY),
              SelectionItem(name="Rugor", id="rugor", kind=K.SERIES),
              SelectionItem(name="Guardian of Blackstone Pass", id="i1", kind=K.ISSUE)]
    state = SimpleNamespace(
        selection=[SelectionItem(name="Studio", id=None, kind=K.LOBBY)],
        resume_selection=resume,
        change_selection=lambda new: walked.append(new),
        storage=SimpleNamespace(read_all_objects=lambda *a, **k: [SimpleNamespace()]))
    opener, chips = opening_and_chips(state)
    door = next(c for c in chips if isinstance(c, tuple))
    assert door[0] == "Pick up where I left off"
    door[1]()
    assert walked and walked[0][-1].id == "i1", "the door WALKS, no agent turn"
    grounded = next(c for c in chips if isinstance(c, str) and "needs doing" in c)
    assert "Rugor" in grounded and "Guardian" in grounded, "the ask names the real bench"
    assert any(isinstance(c, str) and c.endswith("…") for c in chips), "a prefill starter"
    assert "Guardian of Blackstone Pass" in opener


def test_text_editors_ride_the_conversation_box():
    """No text-entry modals: the bench brief and the book's shared text
    editor arm the one-shot intercept instead of opening a dialog."""
    import re
    lt = open("gui/light_table.py").read()
    m = re.search(r"def edit_brief_dialog\(\):(.*?)\n            _has_brief", lt, re.S)
    assert m, "the brief editor exists"
    body = m.group(1)
    assert "_input_intercept" in body, "the brief rides the conversation box"
    assert "ui.dialog" not in body and "studio_dialog" not in body, \
        "the brief editor must not open a modal"

    iss = open("gui/issue.py").read()
    m = re.search(r"def edit_text_dialog\(.*?\):(.*?)\n    # ----", iss, re.S)
    assert m, "the shared text editor exists"
    body = m.group(1)
    assert "_input_intercept" in body, "book text edits ride the conversation box"
    assert "studio_dialog" not in body and "ui.textarea" not in body, \
        "the shared text editor must not open a modal"


# ---------------------------------------------------------------------------
# THREAD HYGIENE: the agent thread never carries half a tool call — the
# Responses API refuses a function_call_output whose call is missing
# ('No tool call found for function call output…'), and once a dangling
# half was SAVED, every later turn failed the same way.
# ---------------------------------------------------------------------------
def test_sane_tail_heals_a_beheaded_tool_call():
    """The exact field failure: a blind [-120:] save cut between a call and
    its output, so the loaded thread OPENED on a dangling output."""
    from helpers.agent_thread import sane_tail
    items = [
        {"type": "function_call_output", "call_id": "c0", "output": "x"},
        {"role": "user", "content": "heal the marked patch"},
        {"type": "function_call", "call_id": "c1", "name": "inpaint_image_region",
         "arguments": "{}"},
        {"type": "function_call_output", "call_id": "c1", "output": "ok"},
        {"role": "assistant", "content": "done"},
    ]
    out = sane_tail(items)
    assert not any(it.get("call_id") == "c0" for it in out), \
        "the orphaned output must not reach the API"
    assert any(it.get("type") == "function_call" and it.get("call_id") == "c1"
               for it in out)
    assert any(it.get("type") == "function_call_output" and it.get("call_id") == "c1"
               for it in out), "a whole pair survives intact"


def test_sane_tail_caps_at_a_whole_user_turn_and_keeps_pairs_whole():
    from helpers.agent_thread import sane_tail
    items = []
    for i in range(50):
        items += [{"role": "user", "content": f"u{i}"},
                  {"type": "function_call", "call_id": f"c{i}", "name": "t",
                   "arguments": "{}"},
                  {"type": "function_call_output", "call_id": f"c{i}", "output": "ok"},
                  {"role": "assistant", "content": "done"}]
    out = sane_tail(items, max_items=10)
    assert len(out) <= 10
    assert out[0].get("role") == "user", "the cap cuts at a whole user turn"
    calls = {it["call_id"] for it in out if it.get("type") == "function_call"}
    outs = {it["call_id"] for it in out if it.get("type") == "function_call_output"}
    assert calls == outs, "no half-pairs survive the cap"


def test_sane_tail_drops_unanswered_calls_and_non_dicts():
    from helpers.agent_thread import sane_tail
    items = [
        {"role": "user", "content": "go"},
        {"type": "function_call", "call_id": "c9", "name": "t", "arguments": "{}"},
        "not-a-dict",
        {"role": "assistant", "content": "…"},
    ]
    out = sane_tail(items)
    assert not any(it.get("call_id") == "c9" for it in out), \
        "a call whose answer never landed is dropped too"
    assert all(isinstance(it, dict) for it in out)
