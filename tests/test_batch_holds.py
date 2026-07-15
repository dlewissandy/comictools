"""THE BATCH HOLDS FOR YOU: hold finishes the piece in hand and waits;
resume continues with FRESH boards; stop sets the rest aside."""
import asyncio
from types import SimpleNamespace


def _state():
    return SimpleNamespace(thread=[], history=None, _render_pending=None,
                           refresh_details=lambda: None, write=lambda: None)


def _run_batch(state, jobs, script):
    """Run enqueue_renders with a control script: {after_piece_index: action}."""
    from helpers.render_queue import enqueue_renders

    async def drive():
        task = enqueue_renders(state, jobs)
        line = next(e for e in state.thread if e.get("board"))
        for _ in range(400):
            done = len([r for r in line["receipts"] if r["line"].startswith("🎨")])
            for at, action in list(script.items()):
                if done >= at:
                    action(line)
                    script.pop(at)
            if task.done():
                break
            await asyncio.sleep(0.02)
        await task
        return line
    return asyncio.run(drive())


def test_hold_waits_then_resume_finishes(tmp_path, monkeypatch):
    import helpers.render_queue as rq
    monkeypatch.setattr(rq, "QUEUE_DIR", str(tmp_path / "q"))
    state = _state()
    order = []
    import time as _t
    jobs = [(f"piece {i}", (lambda i=i: (_t.sleep(0.06), order.append(i))[0] or f"done {i}"), None)
            for i in range(3)]

    def hold_then_release(line):
        line["_ctl"]["hold"] = True

        async def release():
            await asyncio.sleep(0.15)
            line["_ctl"]["hold"] = False
        asyncio.ensure_future(release())

    line = _run_batch(state, jobs, {1: hold_then_release})
    assert order == [0, 1, 2], "every piece ran — the hold only paused the flow"
    assert line["status"] == "done"


def test_stop_sets_the_rest_aside(tmp_path, monkeypatch):
    import helpers.render_queue as rq
    monkeypatch.setattr(rq, "QUEUE_DIR", str(tmp_path / "q"))
    state = _state()
    order = []
    import time as _t
    jobs = [(f"piece {i}", (lambda i=i: (_t.sleep(0.08), order.append(i))[0] or f"done {i}"), None)
            for i in range(4)]

    line = _run_batch(state, jobs, {1: lambda l: l["_ctl"].__setitem__("stop", True)})
    assert len(order) < 4, "the tail was set aside"
    assert any("set aside" in (r.get("line") or "") for r in line["receipts"]), \
        "the stop leaves an honest receipt"


def test_sends_stay_unblocked_during_batches():
    """The send lock guards AGENT turns only — a running render batch never
    sets state._sending, so the author keeps talking."""
    src = open("helpers/render_queue.py").read()
    assert "_sending" not in src, "the drawing board never takes the send lock"
