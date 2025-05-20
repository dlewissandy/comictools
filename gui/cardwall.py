from nicegui import ui

def init_cardwall(columns: int = 4):
    return ui.element('div').classes(f'columns-{columns} w-full gap-2')
