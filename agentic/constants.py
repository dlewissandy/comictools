import os
from functools import lru_cache

LANGUAGE_MODEL = "gpt-5.2"


@lru_cache(maxsize=1)
def boilerplate_instructions() -> str:
    """The shared system boilerplate.  Resolved lazily (data/ holds house
    MOUNTS at import time, not content): the studio template first, then
    any mounted house's copy, then the legacy single-root layout."""
    candidates = []
    template = os.path.expanduser(os.path.join(
        "~", ".comic-studio", "templates", "house", "prompts", "system", "boilerplate.txt"))
    candidates.append(template)
    try:
        from storage import registry
        for h in registry.registered():
            candidates.append(os.path.join(registry.mount_path(h["slug"]),
                                           "prompts", "system", "boilerplate.txt"))
    except Exception:
        pass
    candidates.append(os.path.join("data", "prompts", "system", "boilerplate.txt"))
    for path in candidates:
        try:
            with open(path, "r") as f:
                return f.read()
        except OSError:
            continue
    return ""
