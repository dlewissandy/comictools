"""THE HOUSE SYNCS LIKE A STUDIO: every publisher is its own git repo,
and the wall carries one small sync control per house.  The commit
message is written like a studio slate — it says what was actually
inked, not 'wip'."""
from __future__ import annotations

import os
import subprocess
import time

from loguru import logger


def _git(path: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", path, *args],
                          capture_output=True, text=True, timeout=timeout)


_STATE_CACHE: dict[str, tuple[float, dict | None]] = {}


def repo_state(path: str, ttl: float = 8.0) -> dict | None:
    """What the wall badge needs, no network: dirty file count, commits
    ahead/behind the upstream (as last fetched), and whether a remote
    exists at all.  None when the path isn't a git repo.  Cached briefly
    so the wall repaints stay snappy."""
    now = time.monotonic()
    hit = _STATE_CACHE.get(path)
    if hit and now - hit[0] < ttl:
        return hit[1]
    out = _repo_state_fresh(path)
    _STATE_CACHE[path] = (now, out)
    return out


def _repo_state_fresh(path: str) -> dict | None:
    if not os.path.isdir(os.path.join(path, ".git")):
        return None
    st = _git(path, "status", "--porcelain", "-uall")
    dirty = len([l for l in st.stdout.splitlines() if l.strip()])
    remote = bool(_git(path, "remote").stdout.strip())
    ahead = behind = 0
    if remote:
        ab = _git(path, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        if ab.returncode == 0 and ab.stdout.split():
            b, a = ab.stdout.split()
            ahead, behind = int(a), int(b)
    return {"dirty": dirty, "ahead": ahead, "behind": behind, "remote": remote}


# path prefix → what the slate calls it (singular, plural)
_NOUNS = [
    ("scenes/",     "panels/",   ("panel", "panels")),
    ("covers/",     None,        ("cover", "covers")),
    ("artboards/",  None,        ("mark", "marks")),
    ("characters/", None,        ("character", "characters")),
    ("settings/",   None,        ("setting", "settings")),
    ("props/",      None,        ("prop", "props")),
    ("outfits/",    None,        ("outfit", "outfits")),
    ("styles/",     None,        ("style", "styles")),
    ("stories/",    None,        ("story", "stories")),
    ("inserts/",    None,        ("insert page", "insert pages")),
    ("pages/",      None,        ("page layout", "page layouts")),
    ("scenes/",     None,        ("scene", "scenes")),
    ("issues/",     None,        ("issue", "issues")),
    ("series/",     None,        ("series record", "series records")),
    ("publishers/", None,        ("house record", "house records")),
    ("prompts/",    None,        ("prompt", "prompts")),
    ("references/", None,        ("reference", "references")),
]


def _noun_for(relpath: str) -> tuple[str, str]:
    for seg, also, noun in _NOUNS:
        if seg in relpath and (also is None or also in relpath):
            return noun
    return ("file", "files")


def nice_commit_message(path: str) -> str:
    """Write the slate from the porcelain: 'STUDIO SYNC: 3 panels, the
    front cover, a masthead mark — Harbor Tales; The Lighthouse Post'."""
    st = _git(path, "status", "--porcelain", "-uall")
    counts: dict[tuple[str, str], set[str]] = {}
    serieses: set[str] = set()
    for line in st.stdout.splitlines():
        if not line.strip():
            continue
        rel = line[3:].strip().strip('"')
        # count the OBJECT, not its files: fold panels/x/images/y.png and
        # panels/x/panel.json into one panel 'x'
        noun = _noun_for(rel)
        parts = rel.split("/")
        key = rel
        for anchor in ("panels", "covers", "characters", "settings", "props",
                       "outfits", "styles", "stories", "inserts", "scenes",
                       "artboards", "issues"):
            if anchor in parts:
                i = parts.index(anchor)
                key = "/".join(parts[:i + 2])
                break
        counts.setdefault(noun, set()).add(key)
        if parts[0] == "series" and len(parts) > 1:
            serieses.add(parts[1])
    if not counts:
        return "STUDIO SYNC: the table is clean"
    bits = []
    for noun, keys in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        n = len(keys)
        bits.append(f"{n} {noun[1] if n != 1 else noun[0]}")
    head = f"STUDIO SYNC: {', '.join(bits[:5])}"
    if serieses:
        names = sorted(s.replace('-', ' ') for s in serieses)
        head += f" — {'; '.join(names[:3])}"
    stamp = time.strftime("%Y-%m-%d %H:%M")
    return f"{head}\n\nSynced from the studio wall, {stamp}."


def sync_house(path: str) -> list[str]:
    """Commit what changed (with the slate message), pull --rebase, push.
    Returns human receipts; every failure speaks plainly and stops."""
    receipts: list[str] = []
    state = repo_state(path)
    if state is None:
        return [f"⚠ {path} is not a git repository."]
    if state["dirty"]:
        msg = nice_commit_message(path)
        _git(path, "add", "-A")
        ident = []
        probe = _git(path, "config", "user.name")
        if not (probe.stdout or "").strip():
            ident = ["-c", "user.name=Comic Studio",
                     "-c", "user.email=studio@comic-studio.local"]
        r = subprocess.run(["git", "-C", path, *ident, "commit", "-m", msg],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return receipts + [f"⚠ commit failed: {(r.stderr or r.stdout)[-200:].strip()}"]
        receipts.append(f"🗃 committed — {msg.splitlines()[0]}")
    else:
        receipts.append("🗃 nothing new to commit")
    if not state["remote"]:
        receipts.append("🏠 no remote — the work is safe in the house repo "
                        "(add one with `git remote add origin …` to sync it out)")
        return receipts
    r = _git(path, "pull", "--rebase", "--autostash")
    if r.returncode != 0:
        return receipts + [f"⚠ pull hit trouble: {(r.stderr or r.stdout)[-200:].strip()} "
                           f"— the repo is untouched beyond the commit; resolve and sync again"]
    pulled = "Already up to date" not in (r.stdout or "")
    if pulled:
        receipts.append("⬇ pulled the latest from the remote")
    r = _git(path, "push")
    if r.returncode != 0:
        return receipts + [f"⚠ push failed: {(r.stderr or r.stdout)[-200:].strip()}"]
    receipts.append("☁ pushed — the house is synced")
    _STATE_CACHE.pop(path, None)
    return receipts


def clone_house(url: str, dest: str, timeout: int = 600) -> str:
    """CLONE A HOUSE from a git URL: the repo lands at dest and the name
    of the publisher living in it comes back.  The clone arrives in a
    temporary sibling first and only takes its place once it proves to
    be a comics house — a failed or foreign clone never leaves debris
    at dest.  Never hangs on a login prompt (private repos over https
    fail fast with advice).  Raises RuntimeError with an author-readable
    reason."""
    import shutil
    from uuid import uuid4

    dest = os.path.abspath(os.path.expanduser(dest))
    if os.path.exists(dest):
        raise RuntimeError(f"{dest} already exists — adopt it from disk "
                           f"instead, or pick another spot")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    staging = f"{dest}.cloning-{uuid4().hex[:6]}"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        try:
            cp = subprocess.run(["git", "clone", "--", url, staging],
                                capture_output=True, text=True,
                                timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"cloning {url} timed out after {timeout}s")
        if cp.returncode != 0:
            tail = ((cp.stderr or "").strip().splitlines() or ["git clone failed"])[-1]
            raise RuntimeError(f"couldn't clone {url}: {tail}  (a private repo "
                               f"needs an SSH url or a git credential helper)")
        from storage.registry import looks_like_house
        pub = looks_like_house(staging)
        if not pub:
            raise RuntimeError(f"{url} cloned, but it isn't a comics house "
                               f"(no publisher record with series or styles) — "
                               f"nothing was adopted")
        os.replace(staging, dest)
        return pub
    finally:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
