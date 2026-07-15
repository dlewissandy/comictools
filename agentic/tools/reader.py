import os

from loguru import logger
from agents import function_tool, Tool, RunContextWrapper
from typing import Callable, Optional, Union
from pydantic import BaseModel
from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind, selection_to_context
from storage.generic import GenericStorage
from schema import (
    ComicStyle,
    Publisher,
    CharacterModel,
    CharacterVariant,
    Panel,
    Cover,
    SceneModel,
    Series,
    Issue,
    Setting,
)

# -------------------------------------------------------------------------
# Functions to read objects from the database.   These are used by the tools
# To perform the file operations
# -------------------------------------------------------------------------
def read_all(
        wrapper: RunContextWrapper[APPState], 
        cls: type[BaseModel], 
        parent_key: dict[str, str] | None = None,
        order_by: Optional[Union[str, Callable[[BaseModel], str]]] = None
        ) -> list[BaseModel]:
    """
    Read all objects of a given class from the database.   

    Args:
        wrapper: The run context wrapper containing the application state.
        cls: The class of the objects to read.
        parent_key: An optional primary key for the parent object.   If not provided, the function will
            read all the objects rooted on the current selection.
    Notes: This function throws if any of the objects are ill formed.
    """
    state: APPState = wrapper.context
    storage:GenericStorage = state.storage

    logger.trace(f"Finding all objects of type {cls.__name__}")
    context = selection_to_context(state.selection)

    CONTEXT_ERROR_MSG = f"Cannot find {cls.__name__} instances."

    # THE KEY NAMES ITS OWN GROUND: an explicit parent_key whose series/
    # publisher/style id resolves to a registered house reads THAT house,
    # from anywhere — the wall's status asks name real ids the author may
    # not be standing in.
    if parent_key is not None:
        from storage import registry as _reg
        _base = str(getattr(storage, 'base_path', ''))
        _on_mounts = _base == _reg.DATA_DIR or _base.startswith(_reg.DATA_DIR + os.sep)
        _keyed_home = _reg.storage_for_key(parent_key, None) if _on_mounts else None
        if _keyed_home is not None:
            objs = _keyed_home.read_all_objects(cls=cls, primary_key=parent_key)
            if order_by is None:
                return objs
            if callable(order_by):
                return sorted(objs, key=order_by)
            return sorted(objs, key=lambda obj: getattr(obj, order_by))

    if len(context) == 0 and cls.__name__ not in ["Series", "Publisher", "ComicStyle"]:
        logger.error(CONTEXT_ERROR_MSG)
        raise ValueError(CONTEXT_ERROR_MSG)

    if len(context) == 0:
        # AT THE LOBBY the studio spans every mounted house — top-level
        # reads (Series, Publisher, ComicStyle) aggregate across the rack
        from storage import registry as _reg
        if _reg.registered() and str(storage.base_path) == _reg.DATA_DIR:
            out = []
            for _slug, st in _reg.mounted_storages():
                out.extend(st.read_all_objects(cls=cls))
            return out
        return storage.read_all_objects(cls=cls)

    # If we reach here, the requested object is a child of the last item in the hierarchy
    pk_parent = context[-1][1] if parent_key is None else parent_key
    objs = storage.read_all_objects(cls=cls, primary_key=pk_parent)

    if order_by is None:
        return objs
    elif callable(order_by):
        return sorted(objs, key=order_by)
    elif isinstance(order_by, str):
        return sorted(objs, key=lambda obj: getattr(obj, order_by))
    else:
        logger.error(f"Invalid order_by argument: {order_by}")
        raise ValueError(f"Invalid order_by argument: {order_by}")


def read_one(wrapper: RunContextWrapper[APPState], cls: type[BaseModel], pk: dict[str, str]) -> BaseModel:
    """
    Find an object in the storage by its primary key.
    
    Args:
        pk: The primary key of the object to find.
    
    Returns:
        The object if found, otherwise a status message.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    logger.trace(f"Finding object with key = {pk}")
    context = selection_to_context(state.selection)

    CONTEXT_ERROR_MSG = f"Cannot find object with key = {pk}.   It is not in the context of the current selection.  You may need to change the current selection."
    NOT_FOUND_ERROR_MSG = f"Cannot find object with key = {pk}.   It is not in the database.   You may want to verify the primary key(s)"
    TOP_LEVEL_IDS = ['series_id', 'publisher_id', 'style_id']

    pk_keys = list(pk.keys())

    # THE KEY NAMES ITS OWN GROUND: a pk whose series/publisher/style id
    # resolves to a registered house is grounded no matter where the author
    # stands — status asks from the wall must read the TRUE house, never
    # the one the author happens to be browsing.  An id no house claims
    # falls through to the context discipline below (hallucinated ids
    # still get caught).
    from storage import registry as _reg
    _base = str(getattr(storage, 'base_path', ''))
    _on_mounts = _base == _reg.DATA_DIR or _base.startswith(_reg.DATA_DIR + os.sep)
    _keyed_home = _reg.storage_for_key(pk, None) if _on_mounts else None
    if _keyed_home is not None:
        storage = _keyed_home
        logger.debug(f"Keyed read — {pk} names its own house")
    elif len(pk_keys)==1 and pk_keys[0] in TOP_LEVEL_IDS:
        # Special case: Top level ids can be retrieved regardless of the current context.
        logger.debug("Finding top level object with key = {pk}")
    elif len(context) == 0:
        # If the context is empty, we can still find series, publishers and styles (since they)
        # are top level objects in the hierarchy.
        if any(k not in TOP_LEVEL_IDS for k in pk):
            # However if the user selected something that is not at the top level of the hierarch, then
            # We throw an error
            logger.error(CONTEXT_ERROR_MSG)
            raise ValueError(CONTEXT_ERROR_MSG)
        logger.debug("Finding top level object with key = {pk}")

    # Special case for when the context and the primary key of the current selection are the same
    elif len(context) > 0 and context[-1][1] == pk:
        logger.debug(f"Finding current selection {pk}")

    # The requested object should be a child of the selected object
    elif len(context) > 0 and len(pk) == len(context)+1:
        parent_pk = context[-1][1]
        parent_keys = list(parent_pk.keys())
        child_keys = pk.keys()
        while len(parent_keys) > 0:
            k = parent_keys.pop()
            if k not in child_keys:
                logger.error(CONTEXT_ERROR_MSG)
                raise ValueError(CONTEXT_ERROR_MSG)
            if pk[k] != parent_pk[k]:
                logger.error(CONTEXT_ERROR_MSG)
                raise ValueError(CONTEXT_ERROR_MSG)

    # An ANCESTOR of the selected object — a panel's own scene, issue, and
    # series are all part of ITS context.  Reading UP the chain (for the
    # setting, style, or issue that composing the panel needs) is never
    # wandering into unrelated data, so it must be allowed: with a panel
    # selected, reading its scene was being rejected, blocking every render.
    elif len(context) > 0 and all(
            k in context[-1][1] and context[-1][1][k] == v for k, v in pk.items()):
        logger.debug(f"Finding ancestor {pk} of the current selection")

    else:
        logger.error(CONTEXT_ERROR_MSG)
        raise ValueError(CONTEXT_ERROR_MSG)

    obj = storage.read_object(cls=cls, primary_key=pk)
    if obj is None:
        logger.error(NOT_FOUND_ERROR_MSG)
        raise ValueError(NOT_FOUND_ERROR_MSG)
    return obj


# -------------------------------------------------------------------------
# TOOLS TO FIND ALL TYPED CHILD OBJECTS OF THE SELECTION
# -------------------------------------------------------------------------

@function_tool
def read_all_publishers(wrapper: RunContextWrapper[APPState]) -> list[Publisher]:
    """
    Get a list of ALL publishing houses the studio knows — every registered
    publisher repo, not just the open one.

    Returns:
        A list of publishers.
    """
    from storage import registry
    if registry.registered():
        from gui.home import all_house_publishers
        return all_house_publishers(wrapper.context.storage)
    return read_all(wrapper=wrapper, cls=Publisher, parent_key=None)

@function_tool
def read_all_styles(wrapper: RunContextWrapper[APPState]) -> list[ComicStyle]:
    """
    Get a list of all comic styles in the database.
    
    Returns:
        A list of comic styles.
    """
    return read_all(wrapper=wrapper, cls=ComicStyle)

@function_tool
def read_all_series(wrapper: RunContextWrapper[APPState]) -> list[Series]:
    """
    Get a list of all comic series in the database.
    
    Returns:
        A list of comic series.
    """
    return read_all(wrapper=wrapper, cls=Series)

@function_tool
def read_all_characters(wrapper: RunContextWrapper[APPState], series_id: str) -> list[CharacterModel]:
    """
    Look up a characters in a series.   

    Args:
        series_id: The identifier of the series the characters belongs to.
    
    Returns:
        The list of details about the characters in the series.
    """
    return read_all(wrapper=wrapper, cls=CharacterModel, parent_key={"series_id": series_id})

@function_tool
def read_all_variants(
    wrapper: RunContextWrapper[APPState],
    series_id: str, 
    character_id: str                  
    ) -> list[CharacterVariant]:
    """
    Look up a all the variants of a character.
    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character for which to look up variants.
    
    Returns:
        A list of all variants for the currently selected character.
    """
    parent_key = {"series_id": series_id, "character_id": character_id}
    return read_all(wrapper=wrapper, cls=CharacterVariant, parent_key=parent_key, order_by="name")

@function_tool
def read_all_covers(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> list[Cover]:
    """
    Look up all covers in a comic book issue.

    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue.

    Returns:
        A list of Cover objects representing the covers in the issue.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id}

    ORDER: list[str] = ["front", "inside-front", "inside-back", "back"]

    return read_all(
        wrapper=wrapper, 
        cls=Cover, 
        parent_key=parent_key,
        order_by=lambda cover: ORDER.index(cover.location.value)
    )

@function_tool
def read_all_issues(wrapper: RunContextWrapper[APPState], series_id: str) -> list[Issue]:
    """
    Look up all issues in a comic book series.
    
    Args:
        series_id: The identifier of the comic book series.
    
    Returns:
        A list of Issue objects representing the issues in the series.
    """
    return read_all(wrapper=wrapper, cls=Issue, parent_key={"series_id": series_id})

@function_tool
def read_all_scenes(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> list[SceneModel]:
    """
    Look up all scenes in a comic book issue.
    
    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue.
    
    Returns:
        A list of SceneModel objects representing the scenes in the issue.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id}
    return read_all(wrapper=wrapper,cls=SceneModel, parent_key=parent_key) 

@function_tool
def read_all_panels(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str) -> list[Panel]:
    """
    look up all the panels in a scene

    Args:
        series_id: The identifier of the series the scene belongs to.
        issue_id: The identifier of the comic book issue the scene belongs to.
        scene_id: The identifier of the scene to look up panels for.
    Returns:
        A list of Panel objects representing the panels in the scene.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return read_all(wrapper=wrapper, cls=Panel, parent_key=parent_key)

# -------------------------------------------------------------------------
# FIND A SPECIFIC CHILD OBJECT OF THE CURRENT SELECTION
# -------------------------------------------------------------------------

@function_tool
def read_publisher(wrapper: RunContextWrapper[APPState], publisher_id: str) -> Publisher | str:
    """
    Find a publisher by its ID.
    
    Args:
        publisher_id: The ID of the publisher.
    
    Returns:
        The Publisher object if found, otherwise a status message.
    """
    pk = {"publisher_id": publisher_id}
    return read_one(wrapper=wrapper, cls=Publisher, pk=pk)

@function_tool
def read_style(wrapper: RunContextWrapper[APPState], style_id: str) -> ComicStyle | str:
    """
    Get the detailed information about a comic book style given its identifier.
    
    Args:
        style_id: The unique identifier of the comic style.
    
    Returns:
        The ComicStyle object if found, otherwise a status message.
    """
    pk = {"style_id": style_id}
    return read_one(wrapper=wrapper, cls=ComicStyle, pk=pk)

@function_tool
def read_series(wrapper: RunContextWrapper[APPState], series_id: str) -> Series | str:
    """
    Get a comic series by its ID.
    Args:
        series_id: The ID of the comic series.  

    Returns:
        The Series object if found, otherwise a status message.
    """
    pk = {"series_id": series_id}
    return read_one(wrapper=wrapper, cls=Series, pk=pk)


@function_tool
def read_character(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str) -> CharacterModel | str:
    """
    Look up a character by its series and character identifiers.   

    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character to look up.
    
    Returns:
        The character object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "character_id": character_id}
    return read_one(wrapper=wrapper, cls=CharacterModel, pk=pk)

@function_tool
def read_variant(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str) -> CharacterVariant | str:
    """
    Look up a variant of a character.

    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character for which to look up variants.
        variant_id: The identifier of the variant to look up.

    Returns:
        The CharacterVariant object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "character_id": character_id, "variant_id": variant_id}
    return read_one(wrapper=wrapper, cls=CharacterVariant, pk=pk)

@function_tool
def read_issue(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> Issue | str:
    """
    Look up an issue of a comic book given its series and issue identifiers.   

    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue to look up.
    
    Returns:
        The Issue object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id}
    return read_one(wrapper=wrapper, cls=Issue, pk=pk)

@function_tool
def read_cover(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str) -> Cover | str:
    """
    Look up a cover of a comic book given its series and issue identifiers.

    Args:
        series_id: The identifier of the series the cover belongs to.
        issue_id: The identifier of the comic book issue the cover belongs to.
        cover_id: The identifier of the cover to look up.
    Returns:
        The Cover object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id}
    return read_one(wrapper=wrapper, cls=Cover, pk=pk)

@function_tool
def read_scene(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str) -> SceneModel | str:
    """
    Look up a scene of a comic book given its series and issue identifiers.

    Args:
        series_id: The identifier of the series the scene belongs to.
        issue_id: The identifier of the comic book issue the scene belongs to.
        scene_id: The identifier of the scene to look up.

    Returns:
        The SceneModel object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return read_one(wrapper=wrapper, cls=SceneModel, pk=pk)

@function_tool
def read_panel(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Panel | str:
    """
    Look up a panel of a comic book given its series, issue, and scene identifiers.
    Args:
        series_id: The identifier of the series the panel belongs to.
        issue_id: The identifier of the comic book issue the panel belongs to.
        scene_id: The identifier of the scene the panel belongs to.
        panel_id: The identifier of the panel to look up.
    Returns:
        The Panel object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return read_one(wrapper=wrapper, cls=Panel, pk=pk)

@function_tool
def read_setting(wrapper: RunContextWrapper[APPState], series_id: str, setting_id: str) -> Setting | str:
    """
    Look up a setting (set) by its series and setting identifiers.

    Args:
        series_id: The identifier of the series the setting belongs to.
        setting_id: The identifier of the setting to look up.

    Returns:
        The Setting object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "setting_id": setting_id}
    return read_one(wrapper=wrapper, cls=Setting, pk=pk)


@function_tool
def read_series_bible(wrapper: RunContextWrapper[APPState], series_id: str) -> str:
    """
    THE SERIES BIBLE in one read: every character (with its variants),
    every setting, and every style the series knows — names AND ids,
    compact.  Use this ONCE instead of separate read_all_characters /
    read_all_variants / read_all_settings calls when breaking a story
    into scenes or casting panels: it saves the whole turn budget.

    Args:
        series_id: The ID of the comic series.

    Returns:
        A compact text bible: characters with variant ids, settings, styles.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    from schema import CharacterModel, CharacterVariant, Setting, ComicStyle
    lines = [f"SERIES BIBLE for {series_id}", "", "CHARACTERS (cast with these exact ids):"]
    for c in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
        lines.append(f"* {c.name} — character_id={c.character_id}")
        for v in storage.read_all_objects(CharacterVariant, primary_key={
                "series_id": series_id, "character_id": c.character_id}):
            styles = ", ".join((v.images or {}).keys()) or "no styled sheets yet"
            lines.append(f"    - variant '{getattr(v, 'name', '') or v.id}' — "
                         f"variant_id={v.id} (sheets: {styles})")
    lines.append("")
    lines.append("SETTINGS (set scenes with these exact ids):")
    for st in storage.read_all_objects(Setting, primary_key={"series_id": series_id}):
        masters = ", ".join((st.images or {}).keys()) or "no masters yet"
        lines.append(f"* {st.name} — setting_id={st.setting_id} (masters: {masters})")
    lines.append("")
    lines.append("STYLES:")
    for sty in storage.read_all_objects(ComicStyle):
        lines.append(f"* {sty.name} — style_id={sty.style_id}")
    return "\n".join(lines)


@function_tool
def read_all_settings(wrapper: RunContextWrapper[APPState], series_id: str) -> list[Setting]:
    """
    Look up all the settings (sets) in a series.   Use this before creating a new
    setting so that existing sets are reused instead of duplicated.

    Args:
        series_id: The identifier of the series.

    Returns:
        The list of settings in the series.
    """
    return read_all(wrapper=wrapper, cls=Setting, parent_key={"series_id": series_id}, order_by="name")


@function_tool
def read_all_stories(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    List the issue's stories (a main feature and any backups) with their ids,
    running order, titles and text — use the story_id with update_story /
    delete_story.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.

    Returns:
        The stories in running order.
    """
    from schema import Story
    return read_all(wrapper=wrapper, cls=Story,
                    parent_key={"series_id": series_id, "issue_id": issue_id},
                    order_by="story_number")


@function_tool
def read_all_inserts(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    List the issue's full-page inserts (posters, ads, pin-ups, the mailbag)
    with their ids, kinds, anchors and render state — use the insert_id with
    update_insert / delete_insert / generate_insert_art.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.

    Returns:
        The inserts in book order.
    """
    from schema import Insert
    return read_all(wrapper=wrapper, cls=Insert,
                    parent_key={"series_id": series_id, "issue_id": issue_id},
                    order_by="after_scene_number")


@function_tool
def read_board_table(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str,
                     scene_id: Optional[str] = None, panel_id: Optional[str] = None,
                     cover_id: Optional[str] = None, insert_id: Optional[str] = None) -> str:
    """
    SEE THE LIGHT TABLE: everything on a board's table right now — every
    acetate with its position, size, tilt, pin and eye state, the letters
    as blocked, the pinned references.   A board is a panel (scene_id +
    panel_id), a cover (cover_id), or an insert (insert_id).   Use this
    before advising on composition or inking: the table IS the author's
    intent.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        scene_id: The panel's scene (with panel_id).  Optional.
        panel_id: The panel to look at.  Optional.
        cover_id: The cover to look at.  Optional.
        insert_id: The full-page insert to look at.  Optional.

    Returns:
        A human-readable inventory of the table.
    """
    import os
    from schema import Cover, Insert, Panel
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    if cover_id:
        board = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
        what = f"the {getattr(getattr(board, 'location', None), 'value', 'front')} cover" if board else None
    elif insert_id:
        board = storage.read_object(cls=Insert, primary_key={
            "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
        what = f"the '{board.name}' {board.kind}" if board else None
    else:
        board = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id,
            "scene_id": scene_id, "panel_id": panel_id})
        what = f"panel {board.panel_number} ('{board.name}')" if board else None
    if board is None:
        return "That board was not found."

    blk = board.figure_blocking or {}

    def state_of(key, dflt_on=1):
        b = blk.get(key) or {}
        bits = []
        if not b.get('on', dflt_on):
            bits.append("LIFTED OFF the table")
        if b.get('lock'):
            bits.append("pinned")
        pos = (f"at {round(float(b.get('x', 50)))}% from left, "
               f"{round(float(b.get('y', 0)))}% up, {round(float(b.get('h', 60)))}% tall")
        if b.get('flip'):
            bits.append("mirrored")
        if b.get('rot'):
            bits.append(f"tilted {float(b['rot']):g}°")
        return pos + (" — " + ", ".join(bits) if bits else "")

    lines = [f"THE LIGHT TABLE of {what} ({board.aspect.value}):"]
    for ref in (board.character_references or []):
        key = f"{ref.character_id}/{ref.variant_id}"
        posed = bool((board.figure_images or {}).get(key))
        lines.append(f"* figure {ref.character_id} ({ref.variant_id})"
                     f"{' — POSED acetate' if posed else ' — no acetate yet'}; {state_of(key)}")
    for key, path in sorted((board.figure_images or {}).items()):
        if key.startswith('element/'):
            lines.append(f"* element '{key.split('/', 1)[1].replace('-', ' ')}'; {state_of(key)}")
        elif key == 'background/plate':
            lines.append(f"* the split background (a background reworked from a take); {state_of('background')}")
    for i, d in enumerate((getattr(board, 'dialogue', None) or [])[:4]):
        lines.append(f"* balloon {i + 1}: {d.character_id} ({d.emphasis.value}) "
                     f"“{d.text}”; {state_of(f'balloon/{i}')}")
    for pos in ('top', 'bottom'):
        caps = [n for n in (getattr(board, 'narration', None) or []) if n.position.value == pos]
        for i, n in enumerate(caps[:2]):
            lines.append(f"* {pos} caption {i + 1}: “{n.text}”; {state_of(f'caption/{pos}/{i}')}")
    ups = [u for u in storage.list_uploads(board) if u and os.path.exists(u)]
    if ups:
        lines.append(f"* {len(ups)} pinned reference image(s)")
    groups = getattr(board, 'layer_groups', None) or {}
    for g, members in groups.items():
        lines.append(f"* group '{g}': {len(members)} layer(s)")
    if len(lines) == 1:
        lines.append("* a bare board — nothing laid yet")
    return "\n".join(lines)
