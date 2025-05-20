from nicegui import ui

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