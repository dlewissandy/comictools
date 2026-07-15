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
