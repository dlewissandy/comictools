"""
The conversation's CAST: every dialog in the chat is a comic panel, and every
speaker is a drawn character.  The human is THE WRITER (pencil behind the
ear); the coauthor is THE ARTIST (beret, brush-happy eyes).  Both are inked
in the studio's own style — bold outlines on paper.
"""
import base64

from nicegui import ui

_INK = "#1a1512"
_PAPER = "#faf6ec"
_PENCIL = "#f2c94c"


def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


WRITER_AVATAR = _svg_data_uri(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <circle cx="24" cy="24" r="21" fill="{_PAPER}" stroke="{_INK}" stroke-width="3"/>
  <path d="M9 22 a15 13 0 0 1 30 0 l-5 -2 -4 -4 -6 3 -6 -4 -5 4 z" fill="{_INK}"/>
  <circle cx="17.5" cy="26.5" r="2.3" fill="{_INK}"/>
  <circle cx="30.5" cy="26.5" r="2.3" fill="{_INK}"/>
  <path d="M17 33 Q24 38.5 31 33" fill="none" stroke="{_INK}" stroke-width="2.6" stroke-linecap="round"/>
  <g transform="rotate(24 39 26)">
    <rect x="36.5" y="16" width="4.6" height="15" rx="1" fill="{_PENCIL}" stroke="{_INK}" stroke-width="2"/>
    <path d="M36.7 31 l2.1 4.2 2.1 -4.2 z" fill="{_PAPER}" stroke="{_INK}" stroke-width="1.6"/>
  </g>
</svg>''')

ARTIST_AVATAR = _svg_data_uri(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <circle cx="24" cy="24" r="21" fill="{_PAPER}" stroke="{_INK}" stroke-width="3"/>
  <ellipse cx="24" cy="14.5" rx="15" ry="6.5" fill="{_INK}" transform="rotate(-8 24 14.5)"/>
  <circle cx="28" cy="6.5" r="2.4" fill="{_INK}"/>
  <path d="M14 26.5 q3.2 -3.4 6.4 0" fill="none" stroke="{_INK}" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M27.6 26.5 q3.2 -3.4 6.4 0" fill="none" stroke="{_INK}" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M18 33 Q24 38 30 33" fill="none" stroke="{_INK}" stroke-width="2.6" stroke-linecap="round"/>
</svg>''')


def comic_chat_message(name: str, sent: bool, **kwargs):
    """A chat message drawn as a comic panel with its speaker's character."""
    avatar = WRITER_AVATAR if sent else ARTIST_AVATAR
    return ui.chat_message(name=name, sent=sent, avatar=avatar, **kwargs)
