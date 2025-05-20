from nicegui import ui
from gui.cardwall import init_cardwall
from gui.markdown import markdown
from style.comic import ComicStyle

def view_style(breadcrumbs, details, chat_history, selection):
    style = ComicStyle.read(id=selection[-1].id)
    with details:
        markdown(style.format())
        
        init_cardwall()