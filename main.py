
import os
import json
from loguru import logger
from loguru._defaults import LOGURU_FORMAT
from nicegui import ui, app
from gui.speech import init_speech_support, start_listening, stop_listening, speak, cancel_speech
from gui.state import APPState, STATE_FILEPATH, set_dark_mode
from dotenv import load_dotenv
from gui.selection import (SelectionItem)
from messaging import send
from storage.local import LocalStorage
from helpers.render_queue import orphaned_slips as _orphaned_slips
_ORPHAN_SLIPS = _orphaned_slips()
load_dotenv()

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# These ensure that the dark and light modes are set consistently for each UI region
HEADFOOT_STYLING_CLASSES = "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300"
MIDDLE_STYLING_CLASSES = "text-gray-900 dark:text-gray-300"
# Default selection to initialize the breadcrumbs
DEFAULT_SELECTION = [{"kind":"all-publishers", "name":"Publishers", "id":None}]

# ---------------------------------------------------------
# LOGGER INITIALIZATION
# ---------------------------------------------------------
def ellipsis(record):
    msg = record["message"]
    if len(msg) > 100:
        record["message"] = msg[:97] + "..."

def init_logger():
    from sys import stderr

    logger.remove()  # Remove the default logger
    logger.add(stderr, level="WARNING", backtrace=True, diagnose=True)
    logger.add("app.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)
    

# ---------------------------------------------------------
# UI LAYOUT INITIALIZATION
# ---------------------------------------------------------
def init_layout(logger):
    """
    Initializes the UI layout with the main components.
    This includes the header, middle, and footer regions.   The ui elements are layed out
    as depicted below:

    +----------------------------------------------------------+
    | Breadcrumbs                             Dark Mode Switch |  Header Region
    +----------------------------------------------------------+
    |  details                   |    history                  |  Middle Region
    | (Current Selection)        | (Conversation History)      |
    +----------------------------------------------------------+
    | User Input Field and Send Button                         |  Footer Region
    +----------------------------------------------------------+
    """
    # THE COMIC SKIN — the app lays out like a comic book page: paper ground,
    # inked panels for assets and artwork, narrator caption boxes for headings,
    # speech balloons for the conversation.  Two token classes carry it all.
    ui.add_head_html('<link href="https://fonts.googleapis.com/css2?family=Bangers&display=swap" rel="stylesheet">')
    from gui.light_table import DRAG_JS
    ui.add_head_html(DRAG_JS)
    ui.add_css("""
        :root { --ink:#181410; --paper:#f2ead8; --panel:#fffdf4;
                --caption:#f9df7b; --caption-ink:#181410; }
        .body--dark { --ink:#e9dfc7; --paper:#15130f; --panel:#211d16;
                      --caption:#7d651e; --caption-ink:#f6eed9; }

        .q-page, .nicegui-content { background: var(--paper); }
        .q-header { border-bottom: 3px solid var(--ink); }
        .q-footer { border-top: 3px solid var(--ink); }

        /* display lettering */
        .comic-title { font-family: 'Bangers', 'Arial Black', Impact, sans-serif;
                       font-size: 2.6rem; letter-spacing: 1.5px; line-height: 1.05;
                       color: var(--ink);
                       text-shadow: 2px 2px 0 rgba(0,0,0,.15); }
        .comic-title-sm { font-size: 2rem; }

        /* narrator caption boxes */
        .caption-box { display: inline-block; background: var(--caption); color: var(--caption-ink);
                       border: 2px solid var(--ink); box-shadow: 2px 2px 0 var(--ink);
                       padding: 1px 10px; font-weight: 800; text-transform: uppercase;
                       font-size: .85rem; letter-spacing: .8px; transform: rotate(-.4deg); }
        .caption-box-sm { font-size: .72rem; padding: 0 8px; }
        .caption-flex { display: inline-flex; align-items: center; gap: 4px; }
        .panel-caption { position: absolute; top: -12px; left: -8px; z-index: 6; }
        .caption-btn { color: var(--caption-ink) !important; min-height: 0 !important;
                       padding: 0 !important; margin: -2px -4px -2px 2px !important; }

        .comic-label { font-weight: 800; text-transform: uppercase;
                       font-size: .8rem; letter-spacing: .5px; color: var(--ink); }
        .comic-label-sm { font-size: .68rem; opacity: .75; }

        /* panels: assets and rendered artwork live in inked comic panels */
        .soft-card { background: var(--panel) !important;
                     border: 2.5px solid var(--ink) !important;
                     border-radius: 2px !important;
                     box-shadow: 3px 3px 0 rgba(0,0,0,.4) !important; }

        /* page rows: sections separated by a firm ink rule, no boxes */
        .section-flat { background: transparent !important; border: none !important;
                        border-bottom: 2px solid var(--ink) !important;
                        border-radius: 0 !important; box-shadow: none !important;
                        margin-bottom: 10px; }

        /* the page grid: panels stitched with gutters, nothing floating */
        /* the page is the size container: cq units inside children resolve
           against ITS width (container units on the container itself fall
           back to the viewport — that was the scaling bug). */
        .comic-page { display: grid; grid-template-columns: repeat(12, 1fr);
                      gap: 12px; width: 100%; align-items: stretch;
                      grid-auto-flow: dense; container-type: inline-size; }
        .mosaic-host { container-type: inline-size; width: 100%; }
        .flow-caption { display: flex; flex-direction: column; align-items: flex-start;
                        justify-content: center; gap: 6px; min-height: 90px; }

        /* THE MOSAIC: a stack of BLOCKS.  Each block is a band of cards whose
           top and bottom edges rule straight across; each band is its own
           grid, scaled uniformly so it fills the full page width — the unit
           is arbitrary, so every band picks its own. */
        .comic-mosaic { display: flex; flex-direction: column; width: 100%; }
        .comic-block { display: grid; width: 100%; gap: 0;
                       /* columns/rows are set inline per band: subunits of
                          1/6 unit keep 8/3-wide covers exactly on-grid */ }
        /* gutters come from cell padding, so a frame's aspect stays EXACT */
        .comic-block > * { min-width: 0; min-height: 0; padding: 6px;
                           position: relative; }
        .rspan-2 { grid-row: span 2; } .rspan-3 { grid-row: span 3; }
        .rspan-4 { grid-row: span 4; } .rspan-5 { grid-row: span 5; }
        .rspan-6 { grid-row: span 6; } .rspan-7 { grid-row: span 7; }
        .rspan-8 { grid-row: span 8; } .rspan-9 { grid-row: span 9; }
        .rspan-10 { grid-row: span 10; } .rspan-12 { grid-row: span 12; }
        /* the panel FRAME fills its region; the art sits inside untouched —
           object-fit: contain never crops or distorts */
        .mosaic-card { width: 100%; height: 100%; display: flex;
                       flex-direction: column; margin: 0 !important;
                       min-width: 0; min-height: 0; overflow: hidden;
                       position: relative; }
        .comic-mosaic > * { min-width: 0; min-height: 0; }
        .mosaic-card .q-img { flex: 1 1 0; min-height: 0; }
        /* !important: QImg writes object-fit inline, and cropping art is a
           firing offense in this studio */
        .mosaic-card .q-img__image { object-fit: contain !important; }
        /* EXCEPT scene panels: frame and art share the same shape, so the
           art fills its frame and the page reads as the rendered scene */
        .mosaic-card.panel-fill .q-img__image { object-fit: cover !important; }
        /* the caption lives in the margin: it fades in when you hover the
           panel, so frames stay a consistent ruled size */
        .panel-hover-caption { position: absolute; left: 8px; bottom: 8px;
                               z-index: 5; opacity: 0; pointer-events: none;
                               transition: opacity .15s ease-in; }
        .q-card:hover > .panel-hover-caption { opacity: 1; }
        /* scene panels: the bottom edge belongs to the reading-order chips
           and the top-right to delete, so the name rides top-left, ABOVE
           the overlay controls */
        .panel-fill .panel-hover-caption { bottom: auto; top: 8px;
                                           z-index: 12; }

        /* THE LIGHT TABLE: acetate layers and the penciller's rough */
        .rough-canvas { position: relative; width: 100%;
                        border: 2.5px solid var(--ink); border-radius: 2px;
                        background: var(--paper); overflow: hidden;
                        box-shadow: 3px 3px 0 rgba(0,0,0,.35); }
        .rough-figure { position: absolute; bottom: 2%; height: 52%;
                        max-width: 46%; transform: translateX(-50%);
                        filter: drop-shadow(2px 2px 0 rgba(0,0,0,.25)); }
        /* a POSED acetate is a real cut-out: it stands taller and grounded */
        .rough-figure.rough-figure-posed {
                        filter: drop-shadow(3px 3px 2px rgba(0,0,0,.3)); }
        /* an UNPOSED figure is a pencil ghost: their reference sheet stands
           in as a silhouette — clearly not ink yet, but blockable.  The
           filter rides the IMAGE only, so the dashed edge and the selection
           box stay crisp */
        .rough-figure:not(.rough-figure-posed) {
                        outline: 2px dashed rgba(59,130,246,.55);
                        outline-offset: -2px; }
        .rough-figure:not(.rough-figure-posed) .q-img__image {
                        filter: grayscale(1) contrast(.7) opacity(.55); }
        /* BLOCKING: grab a figure and place it; scroll on it to scale */
        .rough-drag { cursor: grab; touch-action: none; user-select: none;
                      max-width: none; }
        .rough-drag:active { cursor: grabbing; }
        /* THE PIN: a pinned acetate stays put — clicks fall through to the
           acetates beneath it */
        .rough-locked { pointer-events: none !important; cursor: default; }
        /* DROP-READY: the upload box under a dragged file lights up */
        .drop-ready { outline: 3px dashed #2e7d32 !important; outline-offset: -3px;
                      background: rgba(46,125,50,.08) !important; }
        /* THE LINE IS DEAD: the connection dropped — edits can't save, so
           the table says so instead of letting work silently evaporate */
        .rough-line-dead::before {
            content: '⚠ CONNECTION LOST — moves are NOT saving.  Reloading…';
            position: absolute; top: 8px; left: 50%; transform: translateX(-50%);
            z-index: 90; background: #b71c1c; color: #fff; font-weight: 700;
            font-size: .72rem; padding: 4px 12px; border-radius: 3px;
            box-shadow: 0 2px 8px rgba(0,0,0,.4); white-space: nowrap; }
        .rough-line-dead { outline: 3px solid #b71c1c; }
        /* SELECTION: dashed border + corner grab handles on the acetate */
        .rough-sel-box { position: absolute; inset: 0;
                         border: 1.5px dashed #3b82f6;
                         pointer-events: none; z-index: 4; }
        .rh { position: absolute; width: 11px; height: 11px;
              background: #fff; border: 1.5px solid #3b82f6;
              border-radius: 2px; pointer-events: auto; }
        /* a selected take LOCKS the table; only Unlock stays live */
        .table-locked > * { pointer-events: none; opacity: .55; }
        .table-locked > .table-unlock { pointer-events: auto; opacity: 1; }
        /* a locked element itself (e.g. the style swatch) also goes quiet */
        .style-swatch.table-locked { pointer-events: none; opacity: .55; }
        .stack-row { cursor: grab; }
        /* ONE SELECTION: the acetate on the rough and its stack row light
           up together — pick either, the other answers */
        .stack-row--sel { outline: 2px solid #3b82f6; outline-offset: -2px;
                          background: rgba(59,130,246,.10) !important;
                          border-radius: 4px; }
        /* tools unfold on the selected (or hovered) row — at rest a row is
           just its eye, its pin, its face and its name.  visibility (not
           display) keeps the row's geometry still: nothing jumps on hover */
        .stack-row .row-tool { visibility: hidden; }
        .stack-row:hover .row-tool, .stack-row--sel .row-tool { visibility: visible; }
        /* UNPOSED SILHOUETTE: the cast member's stand-in on the rough */
        .rough-silhouette { position: absolute; border: 2px dashed rgba(59,130,246,.75);
                            border-radius: 6px; background: rgba(59,130,246,.08);
                            display: flex; flex-direction: column; align-items: center;
                            justify-content: center; gap: 2px; cursor: pointer;
                            transition: background .12s; }
        .rough-silhouette:hover { background: rgba(59,130,246,.18); }
        .rough-silhouette__icon { font-size: 2.2rem; opacity: .55; }
        .rough-silhouette__name { font-size: .6rem; font-weight: 700; opacity: .75;
                                  text-align: center; padding: 0 4px; }
        /* THE HAND-SKILLS PLACARD: taught once, at the moment of first use */
        .rough-placard { position: absolute; bottom: 8px; left: 50%;
                         transform: translateX(-50%); z-index: 80;
                         background: #f3e5ab; color: #1c1a17; border: 1.5px solid #1c1a17;
                         font-size: .62rem; font-weight: 600; padding: 3px 10px;
                         max-width: 92%; width: max-content; text-align: center;
                         box-shadow: 2px 2px 0 rgba(0,0,0,.3);
                         animation: placard-in .25s ease-out; pointer-events: none; }
        @keyframes placard-in { from { opacity: 0; transform: translate(-50%, 6px); }
                                to { opacity: 1; transform: translate(-50%, 0); } }
        /* THE INK BAR RIDES ALONG: the main action never scrolls away */
        .ink-bar { position: sticky; bottom: 4px; z-index: 20;
                   background: var(--paper); padding: 6px 4px;
                   border-top: 1.5px solid var(--ink); width: 100%; }
        /* a locked bench has no pinned action — a faded bar floating over
           the rows would double-expose them */
        .table-locked .ink-bar { position: static; }
        /* THE BENCH REFLOWS: in a narrow room the three columns stack
           instead of crushing each other */
        @container (max-width: 1200px) {
            .light-columns { flex-wrap: wrap !important; }
            .light-columns > div { flex: 1 1 340px !important;
                                   width: auto !important; min-width: 300px !important; }
        }
        /* drop ONTO a row to nest under it; drop at an edge to reorder */
        .stack-row.stack-drop-onto { outline: 2px solid #3b82f6; outline-offset: -2px;
                                     background: rgba(59,130,246,.12) !important; }
        .stack-row.stack-drop-above { box-shadow: 0 -3px 0 0 #3b82f6; }
        .stack-row.stack-drop-below { box-shadow: 0 3px 0 0 #3b82f6; }
        .rh-nw { top: -6px; left: -6px; cursor: nwse-resize; }
        .rh-ne { top: -6px; right: -6px; cursor: nesw-resize; }
        .rh-sw { bottom: -6px; left: -6px; cursor: nesw-resize; }
        .rh-se { bottom: -6px; right: -6px; cursor: nwse-resize; }
        /* LETTERS PRINT WHAT YOU BLOCK: family, wrap width, line height and
           padding mirror helpers/compositor.paste_letters — the rough IS
           the proof */
        .rough-balloon { position: absolute; transform: translateX(-50%);
                         background: #fff; color: #1a1512;
                         border: 2px solid #1a1512; border-radius: 1.2em;
                         padding: .55em .7em; font-size: .68rem;
                         font-family: 'Comic Sans MS', 'Chalkboard SE', 'Comic Neue', sans-serif;
                         width: max-content; max-width: 38%;
                         white-space: normal; text-align: center;
                         line-height: 1.3; overflow: visible; }
        /* the TAIL: drawn on the SVG overlay, its tip draggable */
        .rough-tails { position: absolute; inset: 0; width: 100%; height: 100%;
                       pointer-events: none; z-index: 69; overflow: visible; }
        .rough-tail-shape { fill: #fff; stroke: #1a1512; stroke-width: 2; }
        .rh-tip { fill: #fff; stroke: #3b82f6; stroke-width: 2;
                  pointer-events: auto; cursor: move; }
        /* EMPHASIS styles — the balloon wears its voice */
        .rough-balloon--whisper { border-style: dashed; font-style: italic;
                                  color: #555; }
        .rough-balloon--shout { border-width: 3.5px; font-weight: 900;
                                text-transform: uppercase;
                                border-radius: 4px; transform: translateX(-50%) rotate(-1deg); }
        .rough-balloon--thought { border-radius: 50%; padding: .9em 1.2em; }
        /* display lettering knocks out of the art exactly as it prints:
           comic-yellow fill with a heavy ink stroke */
        .rough-balloon--sound-effect { background: transparent; border: none;
                                 letter-spacing: 1px;
                                 color: #fcd838; font-weight: 900;
                                 -webkit-text-stroke: 1.5px #1c1a17;
                                 paint-order: stroke fill; }

        /* in-place letter editing (double-click) */
        .rough-editing { outline: 2px solid #3b82f6; white-space: normal;
                         min-width: 80px; cursor: text; z-index: 99 !important; }
        .rh-flip { position: absolute; bottom: -24px; left: 50%;
                   transform: translateX(-50%); background: #fff;
                   border: 1.5px solid #3b82f6; border-radius: 3px;
                   font-size: 10px; padding: 0 5px; cursor: pointer;
                   pointer-events: auto; white-space: nowrap; }
        .rough-narration { position: absolute; left: 4px;
                           background: var(--caption); color: var(--caption-ink);
                           border: 2px solid var(--ink); border-radius: 2px;
                           padding: .55em .7em; font-size: .68rem; max-width: 60%;
                           font-family: 'Comic Sans MS', 'Chalkboard SE', 'Comic Neue', sans-serif;
                           width: max-content; line-height: 1.3;
                           white-space: normal; }
        /* RECEIPTS ARE PAPER SLIPS: stamped with the bench they came from */
        .receipt-slip { position: relative; border: 1.5px dashed var(--ink);
                        border-radius: 2px; background: rgba(243,229,171,.25);
                        padding: 6px 10px 4px; transform: rotate(-.3deg); }
        .receipt-slip__stamp { position: absolute; top: 3px; right: 8px;
                               font-size: .54rem; letter-spacing: .1em;
                               text-transform: uppercase; opacity: .55; }
        /* THE RESUME CARD: the lobby's front door back to the last bench */
        .resume-card { display: flex; align-items: center; gap: 14px;
                       border: 2px solid var(--ink); border-radius: 4px;
                       background: var(--paper); padding: 10px 14px;
                       margin: 10px 0 4px; box-shadow: 3px 3px 0 rgba(0,0,0,.25);
                       transition: transform .12s, box-shadow .12s; }
        .resume-card:hover { transform: translate(-1px, -1px);
                             box-shadow: 4px 4px 0 rgba(0,0,0,.3); }
        .resume-card__art { width: 64px; aspect-ratio: 16/27; border-radius: 2px;
                            border: 1.5px solid var(--ink); flex: 0 0 auto; }
        /* the mailbag's letter blocks: text plates, wider than captions */
        .rough-letterblock { max-width: 55%; text-align: left;
                             white-space: pre-line; }
        /* a locked, empty table ghosts its featured print on the glass */
        .rough-ghost-print { opacity: .4; filter: saturate(.65); }
        .rough-ghost-print__note { position: absolute; bottom: 6px; left: 50%;
                                   transform: translateX(-50%); z-index: 6;
                                   font-size: .62rem; font-style: italic;
                                   color: #8a8378; background: rgba(255,255,255,.75);
                                   padding: 0 8px; border-radius: 8px;
                                   white-space: nowrap; }
        .rough-prop { background: rgba(255,255,255,.8); color: #1a1512;
                      border: 1.5px solid var(--ink); border-radius: 8px;
                      padding: 0 6px; font-size: .62rem; }
        .light-layer { border: 1.5px solid var(--ink); border-radius: 2px;
                       background: var(--panel); padding: 2px 6px;
                       box-shadow: 2px 2px 0 rgba(0,0,0,.2); }
        .light-thumb { width: 40px; height: 28px; border: 1.5px solid var(--ink);
                       border-radius: 2px; object-fit: cover; flex-shrink: 0; }
        /* reference acetates pin to the rough like photos taped to the table */
        .rough-pin { position: absolute; width: 16%; background: #fff;
                     padding: 2px; border: 2px solid var(--ink);
                     box-shadow: 2px 3px 4px rgba(0,0,0,.35); }
        /* THE STYLE SWATCH: a printer's color chip taped to the board */
        .style-swatch { display: flex; align-items: center; gap: 6px;
                        padding: 2px 8px 2px 3px; background: var(--panel);
                        border: 2px solid var(--ink); border-radius: 2px;
                        box-shadow: 2px 2px 0 rgba(0,0,0,.3);
                        transform: rotate(-1.5deg);
                        transition: transform .15s ease, box-shadow .15s ease; }
        .style-swatch:hover { transform: rotate(0deg) scale(1.05);
                              box-shadow: 3px 3px 0 rgba(0,0,0,.35); }
        .style-swatch-art { width: 34px; height: 24px; object-fit: cover;
                            border: 1.5px solid var(--ink); flex-shrink: 0; }
        .style-swatch-name { font-size: .68rem; font-weight: 700;
                             text-transform: uppercase; letter-spacing: .04em;
                             white-space: nowrap; }
        .style-swatch-current { outline: 3px solid var(--accent, #c62828);
                                outline-offset: 2px; }
        /* GHOST CARDS: work not yet inked — dashed frame, faded art, one CTA */
        .ghost-card { border-style: dashed !important; }
        .ghost-card .q-img { opacity: .3; filter: grayscale(55%); }

        /* THE OPEN BOOK: the issue view IS the comic — pages lie on the
           table in side-by-side spreads, the cover opening the book alone
           on the recto like a real one.  THE BOOKROOM is a CSS container:
           pages size to the room they're in, not the window — a narrow
           pane (chat open, split screen) stacks single pages instead of
           clipping the spread */
        .bookroom { container-type: inline-size; }
        .book { display: grid; --pw: min(380px, 42cqw);
                grid-template-columns: repeat(2, var(--pw));
                column-gap: 8px; row-gap: 34px; justify-content: center;
                padding: 18px 0 26px; }
        @container (max-width: 560px) {
            .book { --pw: min(420px, 88cqw);
                    grid-template-columns: var(--pw) !important; }
            .book-page--recto { grid-column: auto !important; }
            .book-masthead { flex-wrap: wrap !important; }
        }
        .book-page { width: var(--pw); aspect-ratio: 6.625 / 10.1875; position: relative;
                     background: #fdfcf8; border-radius: 2px; overflow: hidden;
                     box-shadow: 0 6px 18px rgba(0,0,0,.35), 0 1px 4px rgba(0,0,0,.25);
                     cursor: default;
                     /* THE PAGE IS PAPER: identical in both themes — ink stays
                        ink even when the room around the table goes dark */
                     color: #1c1a17;
                     --ink: #181410; --caption: #f9df7b; --caption-ink: #181410; }
        .book-page .text-gray-500 { color: #6b7280 !important; }
        .book-page--recto { grid-column: 2; }
        .book-page--ghost { border: 2px dashed var(--ink); background: transparent;
                            box-shadow: none; cursor: pointer;
                            display: flex; flex-direction: column;
                            align-items: center; justify-content: center; }
        .book-page--tray { cursor: default; justify-content: flex-start;
                           align-items: stretch; }
        .page-cap { position: relative; align-self: flex-start; margin: 10px 0 4px 10px;
                    background: var(--caption, #f3e5ab); border: 1.5px solid var(--ink);
                    color: var(--caption-ink, #1c1a17); font-size: .6rem; font-weight: 800;
                    letter-spacing: .08em; padding: 1px 8px; z-index: 6; width: fit-content; }
        .book-page > .page-cap { position: absolute; top: 6px; left: 8px; margin: 0; }
        .page-cap--foot { position: relative !important; top: auto !important;
                          left: auto !important; margin: 6px 0 2px 10px !important; }
        .page-ghost-cta { font-size: 1rem; font-weight: 700; opacity: .7; }
        .page-ghost-hint { font-size: .72rem; opacity: .6; font-style: italic; }
        .page-folio { position: absolute; bottom: 4px; left: 50%; transform: translateX(-50%);
                      font-size: .62rem; color: #8a8378; z-index: 6; }
        .page-tools { position: absolute; top: 4px; right: 4px; z-index: 7;
                      background: rgba(255,255,255,.75); opacity: 0; transition: opacity .15s; }
        .book-page:hover .page-tools { opacity: 1; }
        .page-small-print { position: absolute; bottom: 10px; left: 10%; width: 80%;
                            text-align: center; font-size: .56rem; color: #8a8378;
                            font-style: italic; }
        /* the colophon's ledger rows FLOW — seven absolute lines on one
           spot is a smear, not a ledger */
        .ledger-line { font-size: .56rem; color: #8a8378; font-style: italic; }
        /* the coauthor must be readable in the dark room — Quasar pins
           message text to black unless told to inherit the theme's ink */
        .q-message-text-content { color: inherit !important; }

        /* tiles: the panels living on the page — art when inked, the beat's
           words on script paper until then */
        .tile { position: absolute; overflow: hidden; cursor: pointer;
                border: 1.5px solid #1c1a17; background: #fff;
                transition: box-shadow .12s; }
        .tile:hover { box-shadow: inset 0 0 0 2px #c62828; z-index: 5; }
        .tile-beat { position: absolute; inset: 0; background: #f9f4e0;
                     padding: 4px 6px; overflow: hidden; }
        .tile-beat--capped { padding-top: 16px; }
        .tile-beat__text { font-size: .6rem; line-height: 1.25; color: #333;
                           display: -webkit-box; -webkit-line-clamp: 6;
                           -webkit-box-orient: vertical; overflow: hidden; }
        .tile-cap { position: absolute; top: 0; left: 0; z-index: 6; cursor: pointer;
                    background: var(--caption, #f3e5ab); border: 1px solid var(--ink);
                    border-top: none; border-left: none; color: var(--caption-ink, #1c1a17);
                    font-size: .5rem; font-weight: 800; letter-spacing: .05em;
                    padding: 0 5px; max-width: 85%; overflow: hidden;
                    text-overflow: ellipsis; white-space: nowrap; }
        .tile-tools { position: absolute; bottom: 2px; right: 2px; z-index: 6;
                      background: rgba(255,255,255,.85); border-radius: 10px;
                      opacity: .45; transition: opacity .15s; }
        .tile:hover .tile-tools { opacity: 1; }
        .size-chip { cursor: pointer; border: 1.5px solid #1c1a17; border-radius: 9px;
                     padding: 0 6px; font-size: .6rem; font-weight: 800; line-height: 1.4;
                     background: #fff; color: #1c1a17; }
        .size-chip:hover { background: #f3e5ab; }

        /* the masthead stays put over the table */
        .book-masthead { position: sticky; top: 0; z-index: 40;
                         background: var(--paper); padding: 6px 0 4px;
                         border-bottom: 2px solid var(--ink); }
        /* THE DETAIL DIAL: stories · scenes · beats */
        .dial-chip { cursor: pointer; border: 2px solid var(--ink); border-radius: 3px;
                     padding: 1px 10px; font-size: .64rem; font-weight: 800;
                     letter-spacing: .06em; opacity: .55; transition: all .12s; }
        .dial-chip:hover { opacity: .85; }
        .dial-chip--on { opacity: 1; background: var(--caption, #f3e5ab);
                         color: var(--caption-ink, #1c1a17);
                         box-shadow: 2px 2px 0 rgba(0,0,0,.35); }

        .book-page--insert { gap: 8px; }
        .insert-foot { position: absolute; bottom: 0; left: 0; right: 0;
                       background: rgba(255,255,255,.85); z-index: 6;
                       opacity: 0; transition: opacity .15s; }
        .book-page:hover .insert-foot { opacity: 1; }

        /* the script & colophon pages read like manuscript */
        .book-page--script { display: flex; flex-direction: column; }
        .script-body { flex: 1; overflow-y: auto; padding: 30px 16px 4px; min-height: 0; }
        .script-text { font-size: .72rem; line-height: 1.45; }
        .script-text p { margin-bottom: .5em; }
        .script-foot { padding: 2px 10px; }
        .script-bare { padding: 0 10px 10px; }
        /* THE PAGE NEVER SCROLLS: a long manuscript fades out like a real
           proof; the "continues" slip opens the whole text */
        .script-clamp { overflow: hidden !important;
                        -webkit-mask-image: linear-gradient(#000 72%, transparent 96%);
                        mask-image: linear-gradient(#000 72%, transparent 96%); }
        .script-continues { align-self: center; margin: -4px 0 2px; z-index: 6; }

        /* MANUSCRIPT SLIPS: 2-3 bare scenes clipped to one working sheet */
        .book-page--slips { padding-top: 4px; }
        .page-slip { flex: 1 1 0; min-height: 0; display: flex; flex-direction: column;
                     overflow: hidden; position: relative; padding-top: 2px; }
        .page-slip + .page-slip { border-top: 1.5px dashed rgba(28,26,23,.4); }
        .page-slip .slip-body { flex: 1; min-height: 0; overflow: hidden; padding: 0 14px;
                                -webkit-mask-image: linear-gradient(#000 70%, transparent 98%);
                                mask-image: linear-gradient(#000 70%, transparent 98%); }
        .page-slip .page-cap { position: relative; top: auto; left: auto;
                               margin: 4px 0 3px 10px; cursor: pointer; }
        /* hidden tools must not catch stray clicks — a ghost "tear this
           scene out" button is a trap, not a tool */
        .page-slip .script-foot { opacity: 0; pointer-events: none; transition: opacity .15s; }
        .page-slip:hover .script-foot { opacity: 1; pointer-events: auto; }

        /* THE CREDITS SET IN TYPE: the colophon prints like an indicia */
        .colophon-credits { display: flex; flex-direction: column; gap: 2px;
                            align-items: center; text-align: center; }
        .credit-line { gap: 8px; cursor: pointer; padding: 1px 8px; border-radius: 2px; }
        .credit-line:hover { background: rgba(28,26,23,.06); }
        .credit-role { font-size: .52rem; font-weight: 800; letter-spacing: .14em;
                       opacity: .6; }
        .credit-name { font-size: .7rem; font-variant: small-caps; }
        .credit-name--unset { opacity: .45; font-style: italic; font-variant: normal; }

        /* THE TRAY: loose panels waiting for a page */
        .tray-tiles { padding: 26px 10px 6px; overflow-y: auto; }
        .tray-tile { width: 30%; aspect-ratio: 3/2; position: relative; cursor: pointer;
                     border: 1.5px solid #1c1a17; background: #f9f4e0; overflow: hidden; }
        .tray-tile:hover { box-shadow: inset 0 0 0 2px #c62828; }
        .tray-tile__place { position: absolute; bottom: 1px; right: 1px; z-index: 6;
                            background: rgba(255,255,255,.85); }
        .comic-page > * { min-width: 0; }
        .cpanel { position: relative; background: var(--panel);
                  border: 2.5px solid var(--ink); border-radius: 2px;
                  box-shadow: 3px 3px 0 rgba(0,0,0,.4); padding: 10px; }
        .cspan-3 { grid-column: span 3; } .cspan-4 { grid-column: span 4; }
        .cspan-6 { grid-column: span 6; } .cspan-8 { grid-column: span 8; }
        .cspan-9 { grid-column: span 9; } .cspan-12 { grid-column: span 12; }
        @media (max-width: 900px) {
          .cspan-3, .cspan-4, .cspan-6, .cspan-8, .cspan-9 { grid-column: span 12; }
        }
        /* markdown inside panels: no extra air */
        .cpanel .q-pa-md { padding: 4px 2px !important; }

        /* the conversation is comic PANELS: each message a square-cornered
           inked frame, its speaker's name a caption box riding the top
           rule, the speaker a drawn CHARACTER in the margin */
        .q-message-text { border: 2.5px solid var(--ink); border-radius: 4px;
                          box-shadow: 4px 4px 0 rgba(0,0,0,.45);
                          background: var(--panel) !important; color: var(--ink) !important;
                          padding: 14px 16px 12px; margin-top: 0;
                          position: relative; overflow: visible; }
        .q-message-sent .q-message-text { background: var(--caption) !important;
                                          color: var(--caption-ink) !important; }
        /* the balloon tail: an inked wedge pointing at the speaker's
           portrait — outline triangle underneath, fill triangle on top */
        .q-message-text::before { content: ''; position: absolute; top: 12px;
                                  border: 9px solid transparent; }
        .q-message-text::after  { content: ''; position: absolute; top: 16px;
                                  border: 5.5px solid transparent; }
        .q-message-received .q-message-text::before {
            left: -16px; border-right: 16px solid var(--ink); border-left: 0; }
        .q-message-received .q-message-text::after {
            left: -9px; border-right: 10px solid var(--panel); border-left: 0; }
        .q-message-sent .q-message-text::before {
            right: -16px; left: auto; border-left: 16px solid var(--ink); border-right: 0; }
        .q-message-sent .q-message-text::after {
            right: -9px; left: auto; border-left: 10px solid var(--caption); border-right: 0; }
        .q-message-name { font-weight: 800; text-transform: uppercase;
                          font-size: .7rem; letter-spacing: .5px;
                          background: var(--caption); color: var(--caption-ink);
                          border: 2px solid var(--ink); border-radius: 2px;
                          box-shadow: 2px 2px 0 rgba(0,0,0,.4);
                          display: inline-block; padding: 1px 10px;
                          position: relative; z-index: 2;
                          margin: 0 0 -7px 10px; }
        .q-message-sent .q-message-name { margin: 0 10px -7px 0; }
        .q-message-avatar { width: 46px; height: 46px; min-width: 46px;
                            border: 2.5px solid var(--ink); background: #faf6ec;
                            box-shadow: 2px 2px 0 rgba(0,0,0,.35); }
    """)

    # SET THE DARK MODE BASED ON THE ENVIRONMENT VARIABLE
    dark_mode = os.getenv('DARK_MODE', 'False').lower() in ['true', '1', 'yes']
    # INITIALIZE THE WINDOW LAYOUT
    ui.query('.nicegui-content').classes('w-full')
    ui.query('.q-page').classes('flex')   
    header = ui.header().classes().classes(HEADFOOT_STYLING_CLASSES)
    middle = ui.row().classes('w-screen flex-1 overflow-hidden ' + MIDDLE_STYLING_CLASSES).style('padding-left:12px; padding-right:12px;')
    footer = ui.footer().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300')

    # INITIALIZE EACH OF THE REGIONS
    # Header region has breadcrums for navigation and the dark mode switch
    with header:
        breadcrumbs = ui.button_group()
        ui.space()
        darkswitch = ui.switch('Dark mode')


    # Middle region has the details and history sections, side by side with a movable splitter
    # The details shows the current selection while the history shows the conversation history
    with middle:
        with ui.splitter(limits=(20,80), value=70).classes('h-full w-full') as splitter:
            with splitter.before:
                # the details pane is THE BOOKROOM: a CSS container, so the
                # open book sizes its pages to this pane, not the window
                details = ui.scroll_area().classes("h-full w-full bookroom "+MIDDLE_STYLING_CLASSES).style('padding-left:12px; padding-right:12px;')
            with splitter.after:
                history = ui.scroll_area().classes("h-full w-full "+MIDDLE_STYLING_CLASSES+" border").style('padding-left:12px; padding-right:12px;')

    # Footer region has the suggestion chips and the user input field
    with footer:
        with ui.column().classes('w-full').style('gap: 2px;'):
            suggestions_row = ui.row().classes('w-full').style('gap: 6px; min-height: 0;')
            input_row = ui.row().classes('w-full flex-nowrap items-center')
    with input_row:
        placeholder = "message"
        user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3 ') \
            .classes('w-full self-center stt-input').style('flex-grow: 1; width: 100vh;') \
            .mark('conversation')

        attach_upload = ui.upload(auto_upload=True, max_files=1).props('accept=image/*').classes('hidden')
        attach_button = ui.button(icon='attach_file').props('flat round').classes('q-ml-sm').tooltip('Attach a reference image to what you are working on')
        attach_button.on('click', lambda _: attach_upload.run_method('pickFiles'))
        mic_button = ui.button(icon='mic').props('flat round').classes('q-ml-sm').tooltip('Dictate')
        stop_mic_button = ui.button(icon='mic_off').props('flat round').tooltip('Stop dictating')
        speak_button = ui.button(icon='volume_up').props('flat round').tooltip('Read aloud')
        stop_speak_button = ui.button(icon='volume_off').props('flat round').tooltip('Mute')
        send_button = ui.button('Send', icon='send').props('rounded unelevated').classes('q-ml-sm')

    return (
        breadcrumbs,
        details,
        history,
        user_input,
        send_button,
        suggestions_row,
        attach_upload,
        darkswitch,
        mic_button,
        stop_mic_button,
        speak_button,
        stop_speak_button,
    )


def build_page(selection_override: list[SelectionItem] | None = None):
    """
    Build the studio page.   With no override, the page restores the last
    selection and chat history from the state file (the classic root behavior).
    With an override (a deep-linked URL), the page opens on that selection with
    a fresh conversation and does NOT persist over the root window's state —
    each window carries its own context (see UX_ideas.md).
    """
    # INITIALIZE THE LOGGER
    init_logger()

    # INITIALIZE THE UI LAYOUT WITH BASIC ELEMENTS
    (
        breadcrumbs,
        details,
        history,
        user_input,
        send_button,
        suggestions_row,
        attach_upload,
        darkswitch,
        mic_button,
        stop_mic_button,
        speak_button,
        stop_speak_button,
    ) = init_layout(logger)

    # READ THE STATE DATA FROM FILE
    state_data = json.load(open(STATE_FILEPATH, 'r')) if os.path.exists(STATE_FILEPATH) else {}

    # SYNC THE APPLICATION STATE WITH THE STORED VALUES
    conversations = state_data.get('conversations', {}) if selection_override is None else {}
    if selection_override is None:
        selection = [SelectionItem(**item) for item in state_data.get('selection', DEFAULT_SELECTION)]
        messages = None  # resolved from the conversation store below
    else:
        selection = selection_override
        messages = []
    dark_value = state_data.get('dark_mode', False)
    darkswitch.value = dark_value

    state: APPState = APPState(
        breadcrumbs = breadcrumbs,
        details = details,
        history = history,
        user_input = user_input,
        send_button = send_button,
        selection = [] ,  # Initially set selection to empty
        storage = LocalStorage(base_path="data"),
        persist = selection_override is None,
        suggestions_row = suggestions_row,
     )

    state.conversations = conversations
    if messages is None:
        # the selection's own thread; fall back to the legacy single history
        messages = conversations.get(state.conversation_key(selection), state_data.get('messages', []))

    state.dark_mode = dark_value
    state.restore_history(messages)
    state.change_selection(selection)   # update the selection to force the redraw of the breadcrumbs
    state.refresh_details()             # Redraw the details based on the current selection

    # The asset catalog drawer: it lays assets ON a light table (a panel,
    # cover or insert bench) or stages them for the open book — so the
    # button only appears where the drawer can actually act.
    from gui.drawer import build_asset_drawer
    toggle_assets = build_asset_drawer(state)
    with breadcrumbs.parent_slot.parent:  # the header row
        assets_btn = ui.button('Assets', icon='collections_bookmark', on_click=lambda _: toggle_assets()) \
            .props('unelevated no-caps').tooltip('Browse the studio asset catalog')
    assets_btn.move(breadcrumbs.parent_slot.parent, target_index=0)  # primary: leftmost
    state.assets_btn = assets_btn
    state.update_assets_button()

    # The command palette: Cmd/Ctrl-K jumps to any object by name.
    from gui.palette import build_palette
    open_palette = build_palette(state)
    with breadcrumbs.parent_slot.parent:
        palette_btn = ui.button(icon='search', on_click=lambda _: open_palette()) \
            .props('flat round').tooltip('Jump to anything (Ctrl/Cmd-K)')
    palette_btn.move(breadcrumbs.parent_slot.parent, target_index=1)
    ui.keyboard(on_key=lambda e: open_palette()
                if e.key.name in ('k', 'K') and (e.modifiers.ctrl or e.modifiers.meta) and e.action.keydown and not e.action.repeat
                else None, ignore=[])

    # THE DRAWING BOARD: a quiet header chip while the studio renders —
    # you always know work is underway without watching the chat.
    with breadcrumbs.parent_slot.parent:
        with ui.row().classes('items-center no-wrap').style('gap: 6px; display: none;') as board_chip:
            ui.spinner('dots', size='1.4em', color='primary')
            board_label = ui.label('').classes('text-xs')
        board_chip.tooltip('The studio is at work — receipts land in the chat as pieces finish')

        # THE WASTEBASKET: deletes are moves, and here's where they went —
        # open it, see what was struck and when, bring anything back
        def open_wastebasket():
            import time as _time
            from storage.trash import list_entries, restore_entry, purge
            entries = list_entries("data")
            with ui.dialog() as dlg, ui.card().classes('soft-card') \
                    .style('min-width: 560px; max-width: 760px; max-height: 70vh;'):
                with ui.row().classes('w-full items-center'):
                    ui.label('The wastebasket').classes('caption-box caption-box-sm')
                    ui.space()
                    if entries:
                        def do_purge():
                            n = purge("data", older_than_days=30)
                            ui.notify(f"Emptied {n} entr{'y' if n == 1 else 'ies'} older than 30 days.",
                                      type='info')
                            dlg.close()
                        ui.button('Empty 30-day-old entries', icon='delete_forever') \
                            .props('outline dense size=sm no-caps color=negative') \
                            .tooltip('The only true delete in the studio — everything younger stays') \
                            .on('click', lambda _: do_purge())
                if not entries:
                    ui.label('Empty — nothing has been struck.').classes('text-sm text-gray-500 q-mt-sm')
                with ui.column().classes('w-full q-mt-sm').style('gap: 4px; overflow-y: auto;'):
                    for en in entries:
                        rel = os.path.relpath(en['original_path'], 'data') if en['original_path'] else '?'
                        age_h = (_time.time() - en['deleted_at']) / 3600
                        age = (f"{age_h * 60:.0f}m ago" if age_h < 1
                               else f"{age_h:.0f}h ago" if age_h < 48 else f"{age_h / 24:.0f}d ago")
                        with ui.row().classes('w-full items-center flex-nowrap light-layer') \
                                .style('gap: 8px; padding: 2px 8px;'):
                            ui.icon('folder' if not en['occupied'] else 'block') \
                                .classes('text-sm text-gray-500')
                            ui.label(rel).classes('text-xs') \
                                .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;') \
                                .tooltip(en['note'] or rel)
                            ui.label(age).classes('text-xs text-gray-500').style('flex-shrink: 0;')
                            if en['occupied']:
                                ui.label('superseded').classes('text-xs text-gray-500')
                            else:
                                def bring_back(entry=en['entry'], rel=rel):
                                    restored = restore_entry("data", entry)
                                    if restored:
                                        ui.notify(f"Brought back {rel}.", type='positive')
                                        dlg.close()
                                        state.refresh_details()
                                    else:
                                        ui.notify("Couldn't restore — its place is occupied.",
                                                  type='warning')
                                ui.button(icon='restore_from_trash').props('flat round dense size=xs') \
                                    .tooltip('Bring it back exactly where it was') \
                                    .on('click', lambda _, e2=en['entry'], r2=rel: bring_back(e2, r2))
            dlg.open()

        ui.button(icon='delete_outline').props('flat round dense') \
            .tooltip('The wastebasket — everything struck, ready to bring back') \
            .on('click', lambda _: open_wastebasket())

        # THE SPEND METER: renders cost real money — the header tells the
        # truth quietly (today's count and a rough dollar estimate)
        spend_label = ui.label('').classes('text-xs text-gray-500') \
            .tooltip("Today's renders and a rough cost estimate — every image "
                     "the studio inked since midnight")

        def _spend_tick():
            from helpers.generator import spend_today
            n, cost = spend_today()
            spend_label.set_text(f"🎨 {n} · ~${cost:.2f}" if n else '')
        _spend_tick()
        ui.timer(15.0, _spend_tick)

    # WORK THAT DIED WITH THE LAST SHUTDOWN: the docket's leftover slips —
    # report them once, in the chat, with the labels ready to re-run
    def _report_orphans():
        global _ORPHAN_SLIPS
        labels, _ORPHAN_SLIPS = _ORPHAN_SLIPS, []
        if not labels:
            return
        try:
            from gui.avatars import comic_chat_message
            with state.history:
                with comic_chat_message(name='the Editor', sent=False).classes('w-full'):
                    ui.markdown("⚠️ The studio went down with work still on the drawing board:\n"
                                + "\n".join(f"* {l}" for l in labels)
                                + "\n\nSay the word and I'll run them again.")
            state.history.scroll_to(percent=100)
        except Exception as e:
            logger.debug(f"orphan-slip report skipped: {e}")
    ui.timer(2.5, _report_orphans, once=True)

    # PASTE AN IMAGE anywhere: boards offer take/plate/reference; other
    # views file it as a reference on what you're working on
    from gui.light_table import handle_clipboard_image
    ui.on('clipboard_image', lambda e: handle_clipboard_image(state, e.args))

    def _board_tick():
        # the chip reads the ON-DISK docket, so every window sees the work
        # in flight — not just the one that started it
        try:
            import time as _time
            from helpers.render_queue import QUEUE_DIR
            # count only living slips (younger than the orphan guard) so a
            # dead run's leftovers never make the chip lie forever
            n = 0
            if os.path.isdir(QUEUE_DIR):
                import json as _json
                for f in os.listdir(QUEUE_DIR):
                    if not f.endswith('.json'):
                        continue
                    try:
                        slip = _json.load(open(os.path.join(QUEUE_DIR, f)))
                        if _time.time() - slip.get('queued_at', 0) < 900:
                            n += 1
                    except (OSError, ValueError):
                        pass
        except OSError:
            n = len(getattr(state, '_render_pending', None) or [])
        if n:
            board_label.set_text(f"{n} on the drawing board")
        board_chip.style(f"display: {'flex' if n else 'none'}; gap: 6px;")
    ui.timer(1.0, _board_tick)

    # Browser back/forward re-resolves the selection from the URL.
    ui.add_body_html("<script>window.addEventListener('popstate', () => location.reload());</script>")

    # Enable browser speech capabilities
    init_speech_support()

    # ENABLE THE EVENT HANDLERS
    darkswitch.bind_value_to(state, "dark_mode")
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))

    from gui.messaging import attach_reference
    attach_upload.on_upload(lambda e: attach_reference(state, e))

    mic_button.on('click', lambda _: start_listening(user_input))
    stop_mic_button.on('click', lambda _: stop_listening())
    speak_button.on('click', lambda _: speak(user_input.value))
    stop_speak_button.on('click', lambda _: cancel_speech())


# ---------------------------------------------------------
# ROUTES (hierarchical resource routes, UX_ideas.md Alt 1)
# Every window/tab deep-links to its selection; reloads are safe.
# ---------------------------------------------------------
def _page_from_path(path: str):
    from gui.routes import selection_from_path
    parts = [p for p in path.split('/') if p]
    selection = selection_from_path(LocalStorage(base_path="data"), parts)
    if selection is None:
        selection = [SelectionItem(**item) for item in DEFAULT_SELECTION]
    build_page(selection_override=selection)


# Serve the data directory (images) from app start, not first page build.
app.add_static_files('/data', './data')


@ui.page('/')
def main_page(client):
    build_page()

@ui.page('/publishers')
def publishers_page():
    _page_from_path('publishers')

@ui.page('/publishers/{tail:path}')
def publisher_page(tail: str):
    _page_from_path('publishers/' + tail)

@ui.page('/library')
def library_page():
    _page_from_path('library')

@ui.page('/styles')
def styles_page():
    _page_from_path('styles')

@ui.page('/styles/{tail:path}')
def style_page(tail: str):
    _page_from_path('styles/' + tail)

@ui.page('/series/{series_id}/issue/{issue_id}/read')
def read_issue_page(series_id: str, issue_id: str):
    """
    THE READING ROOM: the bound issue held open in your hands — two pages
    side by side like a real comic, the cover opening the book alone on the
    recto.  A thumb on either edge (or the arrow keys) turns the spread.
    Every sheet is composed with the SAME math that binds the PDF, so what
    you read IS the book.  Read-only; no chat.
    """
    from helpers.binder import reader_sheets
    from schema import Issue
    storage = LocalStorage(base_path="data")
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    # lights down: this page alone reads against a dark tabletop
    ui.add_css("""
        .reading-room { background: #211d1a !important; overflow: hidden; }
        .reader-stage { position: fixed; inset: 90px 0 34px; display: flex;
                        align-items: center; justify-content: center; }
        .reader-spread { display: flex; align-items: stretch; justify-content: center;
                         height: 100%; gap: 0; }
        .reader-sheet { height: 100%; aspect-ratio: 6.625 / 10.1875; background: #fff;
                        position: relative; flex-shrink: 0;
                        box-shadow: 0 14px 44px rgba(0,0,0,.6), 0 2px 8px rgba(0,0,0,.4); }
        .reader-sheet .q-img { position: absolute; inset: 0; width: 100%; height: 100%; }
        .reader-sheet--verso { border-radius: 4px 1px 1px 4px;
                               box-shadow: -10px 12px 40px rgba(0,0,0,.55), inset -14px 0 18px -14px rgba(0,0,0,.5); }
        .reader-sheet--recto { border-radius: 1px 4px 4px 1px;
                               box-shadow: 10px 12px 40px rgba(0,0,0,.55), inset 14px 0 18px -14px rgba(0,0,0,.5); }
        .reader-thumb { position: fixed; top: 0; bottom: 0; width: 12vw; min-width: 70px;
                        display: flex; align-items: center; z-index: 20;
                        color: #e8e2d8; cursor: pointer; opacity: .35;
                        transition: opacity .15s; border: none; background: transparent;
                        font-size: 64px; line-height: 1; }
        .reader-thumb:hover { opacity: .95; }
        .reader-thumb--left { left: 0; justify-content: flex-start; padding-left: 14px;
                              background: linear-gradient(to right, rgba(0,0,0,.35), transparent); }
        .reader-thumb--right { right: 0; justify-content: flex-end; padding-right: 14px;
                               background: linear-gradient(to left, rgba(0,0,0,.35), transparent); }
        .reader-counter { position: fixed; bottom: 8px; left: 50%; transform: translateX(-50%);
                          color: #8a8378; font-size: 12px; z-index: 20; }
        .reader-dl { color: #211d1a; background: #e8e2d8; padding: 5px 14px; border-radius: 16px;
                     font-size: 13px; font-weight: 600; text-decoration: none; }
        .reader-dl:hover { background: #fff; }
    """)
    ui.query('body').classes('reading-room')
    ui.add_body_html("""<script>
    window.readerSpread = 0;
    window.showSpread = function (k) {
      const sheets = [...document.querySelectorAll('.reader-sheet')];
      if (!sheets.length) return;
      const n = sheets.length;
      const maxK = Math.ceil((n - 1) / 2);
      k = Math.max(0, Math.min(maxK, k));
      window.readerSpread = k;
      // spread 0 = the cover alone on the recto; spread k = sheets 2k-1 | 2k
      const visible = k === 0 ? [0] : [2 * k - 1, 2 * k].filter(i => i < n);
      sheets.forEach((s, i) => {
        s.style.display = visible.includes(i) ? '' : 'none';
        s.classList.remove('reader-sheet--verso', 'reader-sheet--recto');
      });
      if (k === 0) { sheets[0].classList.add('reader-sheet--recto'); }
      else {
        sheets[visible[0]].classList.add('reader-sheet--verso');
        if (visible[1] !== undefined) sheets[visible[1]].classList.add('reader-sheet--recto');
      }
      const counter = document.querySelector('.reader-counter');
      if (counter) counter.textContent = k === 0 ? 'the cover' :
        (visible.length === 2 ? `pages ${visible[0] + 1}–${visible[1] + 1} of ${n}`
                              : `page ${visible[0] + 1} of ${n}`);
      const lt = document.querySelector('.reader-thumb--left');
      const rt = document.querySelector('.reader-thumb--right');
      if (lt) lt.style.visibility = k === 0 ? 'hidden' : 'visible';
      if (rt) rt.style.visibility = k >= maxK ? 'hidden' : 'visible';
    };
    document.addEventListener('keydown', (e) => {
      if (!['ArrowRight','ArrowLeft','PageDown','PageUp'].includes(e.key)) return;
      e.preventDefault();
      const fwd = (e.key === 'ArrowRight' || e.key === 'PageDown');
      window.showSpread(window.readerSpread + (fwd ? 1 : -1));
    });
    window.addEventListener('load', () => setTimeout(() => window.showSpread(0), 60));
    </script>""")
    if issue is None:
        ui.markdown(f"Issue `{issue_id}` not found.").style('color: #e8e2d8;')
        return
    sheets, missing = reader_sheets(storage, series_id, issue_id)
    with ui.row().classes('w-full items-center flex-nowrap').style(
            'padding: 14px 20px 0; gap: 14px; position: relative; z-index: 25;'):
        ui.label(f"{issue.name}").classes('text-2xl font-bold').style('color: #e8e2d8;')
        # take the book with you: the bound exports, one click each
        exports_dir = os.path.join('data', 'series', series_id, 'issues', issue_id, 'exports')
        for fname, label in ((f"{issue_id}.pdf", '⤓ PDF'), (f"{issue_id}.cbz", '⤓ CBZ')):
            path = os.path.join(exports_dir, fname)
            if os.path.exists(path):
                ui.html(f'<a class="reader-dl" href="/{path.replace(os.sep, "/")}" '
                        f'download>{label}</a>')
        ui.space()
        if missing:
            # the reading room quotes THE PRODUCTION LEDGER — the same
            # truth the studio's colophon prints
            from helpers.ledger import issue_ledger
            _led = issue_ledger(storage, series_id, issue_id)
            todo_items = [item for line in _led.todos for item in line.items] \
                or [line.text for line in _led.todos] or missing
            with ui.expansion(f"reading a proof — {_led.summary()}") \
                    .style('color: #8a8378; max-width: 380px;'):
                for m in todo_items:
                    ui.markdown(f"* {m}").style('color: #8a8378;')
    if not sheets:
        ui.label("Nothing rendered yet — render covers and panels, then come back.") \
            .style('color: #e8e2d8; padding: 40px;')
        return
    # THE BOOK IN HAND: all sheets in the spread; JS shows two at a time
    with ui.element('div').classes('reader-stage'):
        with ui.element('div').classes('reader-spread'):
            for i, (label, path) in enumerate(sheets):
                with ui.element('div').classes('reader-sheet') as sh:
                    ui.image(source=path).props('no-spinner')
                    sh.tooltip(label)
    ui.html('<button class="reader-thumb reader-thumb--left" '
            'onclick="window.showSpread(window.readerSpread - 1)">‹</button>')
    ui.html('<button class="reader-thumb reader-thumb--right" '
            'onclick="window.showSpread(window.readerSpread + 1)">›</button>')
    ui.html('<div class="reader-counter"></div>')


@ui.page('/series/{tail:path}')
def series_page(tail: str):
    _page_from_path('series/' + tail)


# reload=False: hot reload restarts the server on every source edit, which
# drops every open tab AND silently kills any render on the drawing board.
# The studio restarts deliberately, not whenever a file changes.
# COMIC_STUDIO_PORT lets a second instance verify new code against the same
# data without dropping the author's live session.
ui.run(reload=False, port=int(os.environ.get('COMIC_STUDIO_PORT', '8080')))

