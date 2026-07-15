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
    and captions — never asides (the daybook holds those)."""
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
    orig_aside, orig_work = th._render_aside, th._render_work
    th._render_aside = lambda *a, **k: rendered.append("aside")
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
        th._render_aside, th._render_work = orig_aside, orig_work
        th.ui = orig_ui
        av.comic_chat_message = orig_ccm
    assert "aside" not in rendered, "asides never render in the chat"
    assert "work-3" in rendered, "the turn's work folds into the reply balloon"


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
