"""
THREAD HYGIENE: the one agent thread survives capping, saving and loading
without ever splitting a tool call from its output.

The Responses API refuses any thread holding a function_call_output whose
function_call is missing ('No tool call found for function call output…')
— and once a dangling half is SAVED, every later turn fails the same way
until the head is healed.  All three doors pass through here: the send
path caps the live thread, the save path caps what goes to disk, and the
load path heals whatever an older build left behind.
"""


def sane_tail(items: list, max_items: int = 140) -> list:
    """Cap a thread at a whole user turn and drop any half of a tool
    call/output pair that lost its mate.

    (140: a tool-heavy render session was forgetting its own morning at
    80 — the author called it 'dumber than dirt', and half of that was
    amnesia.)
    """
    items = [it for it in (items or []) if isinstance(it, dict)]
    if len(items) > max_items:
        start = len(items) - max_items
        cut = next((i for i in range(start, len(items))
                    if items[i].get('role') == 'user'), start)
        items = items[cut:]
    answered = {it.get('call_id') for it in items
                if it.get('type') == 'function_call_output'}
    kept_calls: set = set()
    out = []
    for it in items:
        kind = it.get('type')
        if kind == 'function_call':
            if it.get('call_id') not in answered:
                continue            # a call whose answer was trimmed away
            kept_calls.add(it.get('call_id'))
        elif kind == 'function_call_output':
            if it.get('call_id') not in kept_calls:
                continue            # an answer whose call was trimmed away
        out.append(it)
    return out
