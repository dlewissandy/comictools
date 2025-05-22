from nicegui import ui

def header(text: str, level: int = 1) -> None:
     if level == 0:
        return ui.label(text).style('font-size: 3rem; font-weight: bold;')
     if level == 1:
        return ui.label(text).style('font-size: 2rem; font-weight: bold;')
     if level == 2:
        return ui.label(text.title()).style('font-size: 2rem; font-weight: bold;')
     if level == 3:
        return ui.label(text.title()).style('font-size: 1.5rem; font-weight: bold;')
     if level == 4:
        return ui.label(text.title()).style('font-size: 1rem; font-weight: bold;')
     if level == 5:
        return ui.label(text.title()).style('font-size: 0.75rem; font-weight: bold;')
     return ui.label(text).style('font-size: 0.75rem;')

def markdown(body: str) -> None:
    with ui.element().classes('w-full q-pa-md'):
            # Add custom CSS to ensure markdown content wraps properly
            ui.add_head_html('''
                <style>
                    .markdown-content {
                        width: 100%;
                        max-width: 100%;
                        overflow-wrap: break-word;
                        word-wrap: break-word;
                        word-break: normal;
                        hyphens: auto;
                    }
                    .markdown-content * {
                        white-space: normal !important;
                        max-width: 100%;
                    }
                    .markdown-content pre {
                        white-space: pre-wrap !important;
                        max-width: 100%;
                        overflow-x: auto;
                    }
                    .markdown-content code {
                        white-space: pre-wrap !important;
                    }
                    .markdown-content p, .markdown-content li {
                        overflow-wrap: break-word;
                        word-wrap: break-word;
                        word-break: normal;
                    }
                </style>
            ''')
            
            # Apply the custom class to the markdown container
            with ui.element('div').classes('markdown-content'):
                ui.markdown(body)