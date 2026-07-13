from loguru import logger
from typing import Optional
from uuid import uuid4
from agents import Agent, function_tool, Tool, RunContextWrapper
from pydantic import BaseModel, Field
import traceback
from schema import (
    Publisher,
    ComicStyle,
    Series,
    Issue,
    SceneModel,
    Panel,
    Cover,
    CharacterModel,
    CharacterVariant,
    CoverLocation,
    Cover,
    ArtStyle,
    CharacterStyle,
    BubbleStyles,
    Narration,
    Dialogue,
    FrameLayout,
    CharacterRef,
    Setting,
    Prop,
    InsertionLocation,
    AfterLast,
    After,
    BeforeFirst,
    Before

)
from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage
from agentic.tools.normalization import normalize_id, normalize_name


def insertion_index(insertion_location: InsertionLocation,
                    item_count: int) -> int:
    """
    Determine the insertion index based on the insertion setting and item count.
    Args:
        item_number (int): The number of the item being inserted.
        insertion_location (InsertionLocation): The setting where the item should be inserted.
        item_count (int): The current number of items in the list.
    """
    # Determine the panel number based on insertion setting
    if isinstance(insertion_location, AfterLast):
        # Insert after the last panel
        item_number = item_count + 1
    elif isinstance(insertion_location, After):
        # Insert after a specific panel
        if insertion_location.index < 0 or insertion_location.index >= item_count:
            raise ValueError(f"Invalid index {insertion_location.index} for insertion setting.")
        item_number = insertion_location.index + 2
    elif isinstance(insertion_location, BeforeFirst):
        # Insert before the first panel
        item_number = 1
    elif isinstance(insertion_location, Before):
        # Insert before a specific panel
        if insertion_location.index < 0 or insertion_location.index >= item_count:
            raise ValueError(f"Invalid index {insertion_location.index} for insertion setting.")
        item_number = insertion_location.index + 1
    else:
        raise ValueError(f"Unknown insertion setting type: {type(insertion_location)}")

    return item_number


def creator(wrapper: RunContextWrapper, obj: BaseModel, overwrite: bool=False) -> Agent | str:
    """
    Create a new object in the database.   This function is used by all other creator tools
    to create objects in the database.
    
    Args:
        wrapper: The run context wrapper containing the application state.
        obj: The object to create
        overwrite: Overwrite the existing object?
    
    Returns:
        The created object or an error message if the object already exists.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    pk = obj.primary_key

    existing = storage.read_object(cls=obj.__class__, primary_key=pk)
    if existing is not None and not overwrite:
        logger.error(f"{obj.__class__.__name__} with key '{obj.primary_key}' already exists.")
        return f"{obj.__class__.__name__} with key '{obj.primary_key}' already exists."
    if existing is not None:
        # overwriting an existing asset: snapshot its JSON into the
        # wastebasket first — a re-created setting/prop/outfit must never
        # silently erase the prose and image locators of the old one
        try:
            import os
            from storage.filepath import obj_to_filepath
            from storage.trash import soft_backup
            fp = obj_to_filepath(existing, base_path=storage.base_path)
            if os.path.exists(fp):
                nm = getattr(existing, "name", None) or str(pk)
                soft_backup(str(storage.base_path), fp,
                            note=f"the {obj.__class__.__name__.lower()} '{nm}' before it was re-created")
        except Exception as e:
            logger.warning(f"pre-overwrite snapshot skipped: {e}")

    logger.info(f"The key '{obj.primary_key}' is available.")
    storage.create_object(data=obj, overwrite=overwrite)
    state.is_dirty = True
    return obj

@function_tool
def create_publisher(wrapper: RunContextWrapper[APPState], name: str, description: Optional[str]) -> Publisher | str | None:
    """
    Create a new publisher with the given name.
    
    Args:
        name: The name of the new publisher.
        description: A detailed description of this publisher written so that prospective
            comic book authors can evaluate their options. The summary should address the
            types of work the publisher focuses on, including genres and formats they
            typically accept. It should clearly explain the publisher’s policies on ownership and
            rights, noting whether creators retain control of their intellectual property or if
            the publisher requires full or partial rights. It should describe how the publisher
            handles distribution, both in print and digital formats, and whether their reach
            includes comic shops, bookstores, and international markets.

            The summary should also explain what kind of marketing and promotional support the
            publisher provides, including whether they expect creators to manage their own outreach.
            Details about editorial involvement—such as the level of guidance, feedback, or creative
            restrictions—should be included, along with any information about print quality and
            available formats. Payment terms should be described, including whether the publisher
            offers advances, royalties, or flat rates. Finally, the summary should include insight
            into the publisher’s reputation within the comics community, including any known strengths,
            weaknesses, or red flags that might influence an author’s decision.

            The tone should be professional, informative, and oriented toward helping an author make
            a well-informed choice.
    
    Returns:
        The created Publisher object or an error message if the publisher already exists.
    """
    from storage import registry as _registry
    if not name or name.strip().lower() in ("new publisher", "publisher",
                                            "new house", "untitled"):
        # never found a house on a placeholder — a repo is a real commitment
        return ("Every publisher is its own git repository, so it needs a real "
                "name before founding.  Ask the author what the house is called "
                "(or point them at the + on the publishers wall, which also "
                "lets them pick where the repo lives).")
    _storage = wrapper.context.storage
    if str(getattr(_storage, "base_path", "")) == _registry.DATA_DIR:
        # EVERY HOUSE ITS OWN REPO: on the mount rack, founding a publisher
        # founds a git repo (at ~/git/<slug>-comics by default) carrying the
        # studio's default styles — ESPECIALLY on an empty registry, where a
        # bare record would be invisible the moment a real house appears.
        # (A fixture/repo-rooted storage still gets a plain record below.)
        import os as _os
        import re as _re
        slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "new-house"
        target = _os.path.expanduser(_os.path.join("~", "git", f"{slug}-comics"))
        if _os.path.exists(target):
            return (f"A folder already exists at {target} — use the + on the "
                    f"publishers wall to pick where the house should live.")
        try:
            _registry.found_house(normalize_name(name), target)
        except Exception as ex:
            return (f"Could not found the house: {ex}")
        if description:
            from storage.local import LocalStorage as _LS
            pubs = _LS(base_path=target).read_all_objects(Publisher)
            if pubs:
                pubs[0].description = description
                _LS(base_path=target).update_object(pubs[0])
        wrapper.context.is_dirty = True
        return (f"Founded the house '{normalize_name(name)}' as its own repository at "
                f"{target}, with the studio's default styles copied in.")

    return creator(
        wrapper=wrapper,
        obj=Publisher(
            publisher_id=normalize_id(name),
            name=normalize_name(name),
            description=description,
            logo=None,
            image=None
        ))


def resolve_publisher_id(storage, publisher: Optional[str], selection=None) -> Optional[str]:
    """Resolve a publisher reference (id OR display name, any case) to the
    canonical publisher_id.  Falls back to the publisher in the current
    selection when no reference is given — a series created while looking
    at a publisher belongs to that publisher.  Returns None when nothing
    resolves; '' means a reference was given but matches no publisher."""
    if publisher:
        cand = normalize_id(publisher)
        from gui.home import all_house_publishers
        for p in all_house_publishers(storage):
            if publisher in (p.publisher_id, p.name) or cand == p.publisher_id \
                    or cand == normalize_id(p.name or ''):
                return p.publisher_id
        return ''
    for item in (selection or []):
        if item.kind.value == 'publisher' and item.id:
            return item.id
    return None


@function_tool
def create_comic_series(wrapper: RunContextWrapper[APPState], series_title: str, description: Optional[str], publisher: Optional[str]) -> Series:
    """
    Create a new comic series with the given title.
    
    Args:
        series_title: The title of the new comic series.
        description: An optional description of the comic series.   This should be 2-5 paragraphs about the series, its themes, characters and setting.  This is intended for writers and artists to understand the series and generate content for it.   IT IS NOT INTENDED FOR THE READER, OR MARKETING.
        publisher: The publisher for the comic series, by name or id.   Optional: when the
            user is working inside a publisher, that publisher is used automatically.
    
    Returns:
        The created Series object.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # THE SERIES BELONGS TO ITS PUBLISHER: resolve name-or-id in CODE (the
    # coauthor often passes the display name, which would never match the
    # publisher page's id filter), defaulting to the publisher on screen.
    pub_id = resolve_publisher_id(storage, publisher, state.selection)
    if pub_id == '':
        return (f"Publisher '{publisher}' not found — create it first with "
                f"create_publisher, or pick an existing one.")

    # THE SERIES LIVES IN ITS PUBLISHER'S REPO: route the write to that
    # house's mount; with no publisher in scope, ask instead of guessing
    from storage import registry as _reg
    if _reg.registered() and str(getattr(storage, 'base_path', '')) == _reg.DATA_DIR:
        if pub_id is None:
            return ("Which publishing house should carry this series?  "
                    "Name one (or open its page) and I'll create it there.")
        _slug = _reg.house_of_publisher(pub_id)
        if _slug:
            storage = _reg.storage_for(_slug)

    # check to see if the series already exists.
    series_id = normalize_id(series_title)
    if storage.read_object(Series, {"series_id": series_id}) is not None:
        logger.error(f"Series with title '{series_title}' already exists.")
        return f"Series with title '{series_title}' already exists."
    else:
        logger.info(f"The title '{series_title}' is available.")
    series = Series(series_id=series_id, name=series_title, description=description, publisher_id=pub_id)
    new_id = storage.create_object(data=series)
    # THE ONE TRAIL: the new series opens on the same canonical trail every
    # UI door builds — never appended to whatever room the chat was in
    from gui.routes import series_ancestry
    state.change_selection(new=series_ancestry(state.storage, new_id))
    state.is_dirty = True
    return series


@function_tool
def create_style(
    wrapper: RunContextWrapper[APPState],
    name: str, 
    description: str,
    art_style: ArtStyle,
    character_style: CharacterStyle,
    bubble_styles: BubbleStyles,
    ) -> ComicStyle | str | None:
    """
    Create a new style with the given name.   Use as much of the relevant information
    from the chat history as possible to fill in the details of the style.  Each field
    should be a short phrase or paragraph, except for the description which can be longer.
    focus on the visual and artistic aspects of the style that might be important for an
    artist to replicate the style.
    
    Args:
        name: The name of the new style.
        description: An optional description of the style.
        art_style: The art style to be used in the comic.
        character_style: The character style to be used in the comic.
        bubble_styles: The bubble styles to be used in the comic.

    Returns:
        The created Style object or an error message if the style already exists.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # check to see if the publisher already exists.
    style_id = name.lower().replace(" ", "-")
    style = storage.read_object(ComicStyle, {"style_id": style_id })
    if style is not None:
        logger.warning(f"The name '{name}' is already in use by another style.")
        return f"The name '{name}' is already in use by another style.  Please choose a different name."

    logger.info(f"The name '{name}' is available.")
    style = ComicStyle(
        name=name, 
        style_id=style_id,
        description=description, 
        art_style=art_style, 
        character_style=character_style, 
        bubble_styles=bubble_styles,
        image=None
    )
    style_id = storage.create_object(style)
    from gui.routes import style_ancestry
    state.change_selection(new=style_ancestry(state.storage, style_id))
    return style

@function_tool
def create_variant(wrapper: RunContextWrapper[APPState], 
        series_id: str,
        character_id: str,
        name: str,
        race: str,
        gender: str,
        age: str,
        height: str,
        general_description: str,
        physical_appearance: str,
        attire: str,
        behavior: str
    ) -> CharacterVariant:
    """
    Create a character's BASE look — the one fully-described variant that
    captures identity.   Use this ONCE per character.   For every additional
    look, DO NOT re-describe the character: compose it from the base plus an
    Outfit asset and props (compose_character_variant).
    
    Args:
        series_id: The id of the series to create the variant in.   This should be the currently selected series.
        character_id: The id of the character to create the variant for.   This should be the currently selected character.
        name: The name of the variant.   This should be unique within the character's variants and should be short (1-3 words).
        general_description: A short 3-5 sentence description of the variant.   What does this variant represent?  How does it differ from other variants?  
        race: 1-5 words describing the race of the character variant.
        gender: 1-2 words describing the gender of the character variant.
        age: 1-5 words describing the relative age of the character variant (e.g. 'child', 'teen', 'adult', 'middle age', 'old', "ancient", etc).
        height: 1-5 words describing the height of the character variant. (e.g. 'short', 'average', 'tall', 'very tall', etc).  Alternatively, compare to size of another character or species.
        physical_appearance: 1-2 paragraphs describing the physical appearance details this variant of the character.
        attire: 1-2 paragraphs describing the attire of the character variant
        behavior: 1-2 paragraphs describing the behavior of the character variant.
        
    NOTE: the descriptions should focus on attiributes that would help artists and writers accurately depict the character variant,
    and will serve as a reference template for depicting the character variant in comic book panels.   Include enough detail so that
    the character variant can be consistenlty represented, even by artists who have never seen the character before.
    
    Returns:
        The newly created CharacterVariant object.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    series: Series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if series is None:
        raise ValueError(f"Series with ID {series_id} not found.")

    character: CharacterModel = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    if character is None:
        raise ValueError(f"Character with ID {character_id} not found in series {series.name}.")
    
    variant = CharacterVariant(
        variant_id=normalize_id(name),
        series_id=character.series_id,
        character_id=character.character_id,
        name=name,
        race=race,
        gender=gender,
        age=age,
        height=height,
        description=general_description,
        appearance=physical_appearance,
        attire=attire,
        behavior=behavior,
        images = {}
    )
    storage.create_object(data=variant)
    state.is_dirty = True
    return variant


class _VariantAttributes(BaseModel):
    """Structured attributes extracted from a character reference image."""
    race: str
    gender: str
    age: str
    height: str
    general_description: str
    physical_appearance: str
    attire: str
    behavior: str


@function_tool
def create_variant_from_image(wrapper: RunContextWrapper[APPState],
        series_id: str,
        character_id: str,
        name: str,
        image_locator: str
    ) -> CharacterVariant | str:
    """
    Create a new character variant by analyzing an uploaded reference image.
    The image is examined to extract the variant's race, gender, age, height,
    appearance, attire and behavior descriptions, which are then used to create
    the variant exactly as if they had been supplied by hand.

    Args:
        series_id: The id of the series to create the variant in.   This should be the currently selected series.
        character_id: The id of the character to create the variant for.   This should be the currently selected character.
        name: The name of the variant.   This should be unique within the character's variants and should be short (1-3 words).
        image_locator: The filepath of the uploaded reference image to analyze.

    Returns:
        The newly created CharacterVariant object, or an error message.
    """
    import os
    from helpers.generator import invoke_generate_api

    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    series: Series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if series is None:
        return f"Series with ID {series_id} not found."

    character: CharacterModel = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    if character is None:
        return f"Character with ID {character_id} not found in series {series.name}."

    if not os.path.isfile(image_locator):
        return f"Image '{image_locator}' not found.  Ask the user to upload the image first."

    prompt = (
        f"You are a comic book character designer.  The attached image is a reference for "
        f"'{name}', a variant of the character '{character.name}' ({character.description}).  "
        "Extract a reusable character-model description from the image.  The descriptions "
        "should focus on attributes that would help artists and writers accurately depict the "
        "character variant, in sufficient detail that artists who have never seen the image "
        "could consistently reproduce the character.  Physical appearance and attire should "
        "each be 1-2 paragraphs; race, gender, age and height should each be a few words."
    )
    try:
        attrs: _VariantAttributes = invoke_generate_api(prompt, text_format=_VariantAttributes, image=image_locator)
    except Exception as e:
        logger.error(f"Failed to analyze reference image {image_locator}: {e}")
        return f"Failed to analyze the reference image: {e}"

    variant = CharacterVariant(
        variant_id=normalize_id(name),
        series_id=character.series_id,
        character_id=character.character_id,
        name=name,
        race=attrs.race,
        gender=attrs.gender,
        age=attrs.age,
        height=attrs.height,
        description=attrs.general_description,
        appearance=attrs.physical_appearance,
        attire=attrs.attire,
        behavior=attrs.behavior,
        images = {}
    )
    storage.create_object(data=variant)
    state.is_dirty = True
    return variant


@function_tool
def create_panel(
    wrapper: RunContextWrapper[APPState],
    name: str,
    beat: Optional[str],
    description: str,
    aspect: FrameLayout,
    characters: list[CharacterRef],
    narration: list[Narration],
    dialogue: list[Dialogue],
    insertion_location: InsertionLocation = AfterLast(kind="after_last"),
) -> str:
    """
Use this tool to create a single panel in a comic book. Choose this when you 
want to advance the visual narrative by showing a specific moment in time 
through composition, character action, and layout. This tool emphasizes
visual storytelling; prefer it over textual exposition when possible.

This tool is appropriate when:

* A character takes a meaningful action or reacts with clear emotion
* The scene changes in setting, time, or energy
* A visual contrast or beat needs to be captured (e.g., tension → release, zoom-in → zoom-out)

Avoid using this tool for:
* Panels that would duplicate prior visuals with no change
* Abstract narration or internal monologue that lacks visual grounding

Args:
name (str): A short label summarizing the panel’s core beat (e.g., “Tormond
Draws His Bow”).

beat (str): The narrative beat for this panel. Describe the change or action
in 1-3 sentences. This is the story moment the panel captures.

description (str): A clear visual description of the panel. Describe what
the reader sees: character positions, motion, facial expressions, and camera
framing. Think in cinematic or storyboard terms. Do not include narration or
dialog here.   This description will be used by artists to ink the panel

characters: Names of all character variants visibly present in the panel.

dialogue: Add only if spoken words enhance pacing, emotion, or story clarity.
It is valid and often preferable to leave this empty.

narration: Use only if the panel benefits from a narrative box (e.g., to
indicate time passing or internal thoughts). Do not repeat what the image
already conveys.

aspect_ratio: Select based on visual composition needs:
* Use portrait for vertical motion, isolation, or focus.
* Use landscape for wide action or multiple focal points.
* Use square for balance, neutrality, or symmetry.

insertion_location: Where to insert the new panel in the scene. Defaults to
AfterLast, which adds the panel to the end of the scene.

Storytelling Guidance
Favor image-driven storytelling. Strong panels do not rely on narration or
dialog. Use this tool to show change — in action, framing, or emotion — and
to maintain narrative rhythm. Dialogue and narration should be minimal and
purposeful.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    selection = state.selection

    scene_id = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id
    
    # Read the issue, scene and series from storage
    issue = storage.read_object(cls=Issue, primary_key={'issue_id': issue_id, 'series_id': series_id})
    scene = storage.read_object(cls=SceneModel, primary_key={'scene_id': scene_id, 'issue_id': issue_id, 'series_id': series_id})
    series = storage.read_object(cls=Series, primary_key={'series_id': series_id})


    if series is None:
        raise ValueError(f"Series with ID {series_id} not found.")
    elif issue is None:
        raise ValueError(f"Issue with ID {issue_id} not found in series {series.name}.")
    elif scene is None:
        raise ValueError(f"Scene with ID {scene_id} not found in issue {issue.name}.")
    series: Series = series
    issue: Issue = issue
    scene: SceneModel = scene

    panels: list[Panel] = storage.read_all_objects(cls=Panel, primary_key={'issue_id': issue_id, 'scene_id': scene_id, 'series_id': series_id}, order_by='panel_number')
    
    panel_number = insertion_index( 
        insertion_location = insertion_location, 
        item_count = len(panels)
        ) 

    if beat is None or beat == "":
        beat = description

    # Create the panel
    storage = state.storage
    new_panel = Panel(
        panel_id=normalize_id(name),
        issue_id=issue_id,
        series_id=series_id,
        scene_id=scene_id,
        name = normalize_name(name),
        beat=beat,
        description=description,
        aspect=aspect,
        panel_number = panel_number,
        character_references=characters,
        narration=narration,
        dialogue=dialogue,
        image=None,  # Image will be set later if needed
        reference_images=[]  # Reference images can be added later
    )

    storage.create_object(new_panel)

    panels.insert(panel_number - 1, new_panel)
    for i,p in enumerate(panels):
        if p.panel_number != i + 1:
            p.panel_number = i + 1
            storage.update_object(p)
    
    
    
    return f"Panel '{new_panel.name}' created successfully in issue '{issue.name}'."

@function_tool
def create_issue(wrapper: RunContextWrapper[APPState], series_id: str, title: str,  story: str) -> str:
    """
    Create a new issue in the currently selected comic series.
    
    Args:
        series_id: The ID of the comic series to create the issue in.
        title: The title of the issue to create
        story: The story of the issue to create
        issue_number: The issue number of the issue to create.  If not provided, it will be auto-generated.
    
    Returns:
        A confirmation message indicating the issue was created successfully.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    series_id = normalize_id(series_id)
    series = storage.read_object(cls=Series,primary_key = {"series_id": series_id})
    if series is None:
        return f"Comic series with ID '{series_id}' not found. Please select a valid series first."
    series: Series = series

    # Get next issue number
    issues: list[Issue] = storage.read_all_objects(cls=Issue, primary_key={"series_id": series.series_id}, order_by="issue_number")
    issue_number = 1
    for issue in issues:
        if issue.issue_number >= issue_number:
            issue_number = issue.issue_number + 1

    issue = Issue(
        issue_id = title.lower().replace(" ", "-"),
        style_id = "vintage-four-color",
        series_id = series.series_id,
        name = title,
        story = story,
        issue_number = issue_number,
        publication_date = None,  # This can be set later
        price = None,  # This can be set later
        writer = None,  # This can be set later
        artist= None,  # This can be set later
        colorist= None,  # This can be set later
        creative_minds = None,  # This can be set later
        cover = {},
        scenes = [],
        characters = [],
    )
    
    return creator(
        wrapper=wrapper,
        obj=issue
    )

@function_tool
def create_character(wrapper: RunContextWrapper[APPState], series_id: str, character_name: str, description: str) -> str:
    """
    Create a new character in the currently selected comic series.
    
    Args:
        series_id: The ID of the comic series to create the character in.
        character_name: The name of the character to create.
        description: A brief description (no more than 3 paragraphs) about the character.  This should serve
            as a summary of the character's background, and role in the comic series.
    
    Returns:
        A confirmation message indicating the character was created successfully.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    # Normalize the identifiers
    series = storage.read_object(cls=Series,primary_key = {"series_id": series_id})
    if not series:
        return "No comic series selected. Please select a series to add a character."
    
    character = CharacterModel(
        character_id = character_name.lower().replace(" ", "-"),
        series_id = series.id,
        name = character_name,
        description = description,
    )

    return creator(
        wrapper=wrapper,
        obj=character
    )

def create_cover_body(
    state: APPState,
    series_id: str,
    issue_id: str,
    location: CoverLocation,
    cover_id: Optional[str] = None,
    description: str = "",
    characters: Optional[list[CharacterRef]] = None,
) -> str:
    """Create a cover on an issue — callable from the GUI or via the tool."""
    characters = characters or []
    try:
        storage: GenericStorage = state.storage

        # Normalize the identifiers
        series_id = normalize_id(series_id)
        issue_id = normalize_id(issue_id)

        series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
        if not series:
            return f"Comic series with ID '{series_id}' not found. Please select a valid series first."
        series: Series = series

        issue = storage.read_object(cls=Issue, primary_key={"issue_id": issue_id, "series_id": series_id})
        if not issue:
            return f"Issue with ID '{issue_id}' not found in series '{series.name}'."
        issue: Issue = issue

        # Verify the character references
        for char in characters:
            character_model = storage.read_object(cls=CharacterModel, primary_key={"character_id": char.character_id, "series_id": series_id})
            if not character_model:
                # Get the names of all the existing characters in the series
                existing_characters = storage.read_all_objects(cls=CharacterModel, primary_key={"series_id": series_id})
                existing_names_and_ids = [(c.id, c.name) for c in existing_characters]
                return f"Character with ID '{char.character_id}' not found in series '{series.name}'.  The available characters (and their IDs) are: {existing_names_and_ids}."
            # Verify the variant exists if specified
            character_model: CharacterModel = character_model
            variant = storage.read_object(cls=CharacterVariant, primary_key={"character_id": char.character_id, "series_id": series_id, "variant_id": char.variant_id})
            if not variant:
                # Get the names of all the existing variants for this character
                existing_variants = storage.read_all_objects(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": char.character_id})
                existing_variant_names_and_ids = [(v.id, v.name) for v in existing_variants]
                return f"Character with ID '{char.character_id}' with Variant ID '{char.variant_id}' not found in series '{series.name}'.  The available variants (and their IDs) are: {existing_variant_names_and_ids}."


        # the first cover at a location gets the friendly id ('front');
        # extras get a suffix.  NOTE: the schema field is `location` — a
        # `setting=` kwarg here once broke every cover creation.
        if cover_id:
            new_cover_id = normalize_id(cover_id)
        elif storage.read_object(cls=Cover, primary_key={
                "series_id": series_id, "issue_id": issue_id, "cover_id": location.value}) is None:
            new_cover_id = location.value
        else:
            new_cover_id = normalize_id(f"{location.value}-{uuid4().hex[:8]}")
        cover = Cover(
            cover_id=new_cover_id,
            location=location,
            issue_id=issue_id,
            series_id=series_id,
            character_references=characters,
            style_id=issue.style_id or "vintage-four-color",
            aspect=FrameLayout.PORTRAIT,
            description=description,
            image=None,  # Image will be set later if needed
            reference_images=[]  # Reference images can be added later
        )

        class _W:  # creator() expects a wrapper-shaped object
            context = state
        result = creator(wrapper=_W(), obj=cover, overwrite=True)
        if isinstance(result, str):
            return result
        return f"Cover '{new_cover_id}' ({location.value}) created for issue '{issue.name}'."
    except Exception as e:
         # Get the full traceback
        tb = traceback.format_exc()
        logger.error(f"Error creating cover: {tb}")
        return f"Error creating cover: {str(e)}\n{tb}"


@function_tool
def create_cover(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    issue_id: str,
    location: CoverLocation,
    cover_id: Optional[str] = None,
    description: str = "",
    characters: Optional[list[CharacterRef]] = None,
) -> str:
    """
    Create a cover for the specified issue.    The description will be used by artists to
    create the cover image, and should be detailed enough that different artists would
    produce similar covers.   Focus on visual elements and composition; be specific.

    Args:
        series_id: The ID of the comic series to create the cover for.
        issue_id: The ID of the comic issue to create the cover for.
        location: Where the cover sits on the book: "front", "back", "inside-front" or "inside-back".
        cover_id: Optional unique identifier for the cover. If not provided, the location is used
            (or a unique suffix when that location already has a cover).
        description: A detailed description of the visual elements in the cover.
        characters: A list of character references to include on the cover.   These references should
            be characters that are in the series.   VERIFY that they exist to avoid errors.
    Returns:
        A confirmation message indicating the cover was created successfully.
    """
    return create_cover_body(wrapper.context, series_id, issue_id, location,
                             cover_id, description, characters)


def create_scene_body(state: APPState,
        name: str,
        story: Optional[str] = None,
        insertion_location: Optional[InsertionLocation] = None,
        setting_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        mood: Optional[str] = None,
        cast: Optional[list[CharacterRef]] = None,
        props: Optional[list[Prop]] = None,
        blocking: Optional[str] = None,
    ) -> str:
    """Create a scene on the issue in the current selection.  A bare name is
    enough: the story defaults to empty and the scene lands at the end."""
    logger.trace(f"inserting scene {name}")
    storage: GenericStorage = state.storage

    # resolve the issue from wherever in the chain the user is standing —
    # never assume the selection ends exactly [series, issue]
    issue_id = next((s.id for s in reversed(state.selection or []) if s.kind.value == 'issue'), None)
    series_id = next((s.id for s in reversed(state.selection or []) if s.kind.value == 'series'), None)
    if not issue_id or not series_id:
        return "Open an issue first — a scene belongs to an issue."
    pk = {"issue_id": issue_id, "series_id": series_id}

    issue: Issue = storage.read_object(cls=Issue, primary_key=pk)
    if issue is None:
        return f"Issue '{issue_id}' not found."
    scenes: list[SceneModel] = storage.read_all_objects(cls=SceneModel, primary_key=pk, order_by="scene_number")

    # cast references resolve by id OR display name and never store
    # danglers — the sheets must find these characters later
    from agentic.tools.updater import resolve_cast
    cast_problems: list[str] = []
    _resolved_cast = resolve_cast(storage, series_id, cast, cast_problems)

    scene = SceneModel(
        scene_id=normalize_id(name),
        issue_id=issue_id,
        series_id=series_id,
        name=name,
        story=story or "",
        style_id=issue.style_id or "vintage-four-color",
        aspect=FrameLayout.PORTRAIT,
        scene_number=insertion_index(
            insertion_location=insertion_location or AfterLast(kind="after_last"),
            item_count=len(scenes)
        ),
        setting_id=setting_id,
        time_of_day=time_of_day,
        mood=mood,
        cast=_resolved_cast,
        props=props or [],
        blocking=blocking,
    )
    storage.create_object(data=scene)

    # reindex the scenes to ensure they are in order
    scenes.insert(scene.scene_number - 1, scene)
    for i,p in enumerate(scenes):
        if i > scene.scene_number - 1:
            if p.scene_number != i + 1:
                p.scene_number = i + 1
                storage.update_object(p)


    state.is_dirty = True
    note = ("  CAST PROBLEMS: " + "; ".join(cast_problems)) if cast_problems else ""
    # speak the id THE STORAGE actually gave it — storage may reassign a
    # UUID on create, and every follow-up tool call needs the real one
    return (f"Scene created successfully for issue {issue.name} "
            f"(scene_id={scene.scene_id}, scene_number={scene.scene_number}).{note}")


@function_tool
def create_scene(wrapper: RunContextWrapper[APPState],
        name: str,
        story: Optional[str] = None,
        insertion_location: Optional[InsertionLocation] = None,
        setting_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        mood: Optional[str] = None,
        cast: Optional[list[CharacterRef]] = None,
        props: Optional[list[Prop]] = None,
        blocking: Optional[str] = None,
    ) -> str:
    """
    Create a new scene for the currently selected comic book issue.

    A scene is specified like a page of a comic script: it has a setting (setting + time of day),
    a cast with wardrobe (character variants), props, and blocking notes.   Providing these
    up front lets the panels be composed from consistent reference objects later.

    When the user asks for "a new scene" WITHOUT details, do not interrogate them:
    call this immediately with just a name (and, if the issue has a story, a 1-3
    sentence story continuing it) — every field can be filled in afterwards.

    Args:
        name (str): The name of the new scene: 2-5 words, letters/numbers/spaces
            (e.g. "Teapot ride", "Joey gets hungry").
        story (str, optional): A summary of the scene's content and purpose, detailed
            enough to guide the storyboard.  Defaults to empty — fill it in later.
        insertion_location (InsertionLocation, optional): Where the scene lands in the
            issue.  Defaults to after the last scene.  LIST ELEMENTS ARE ONES-BASED.
        setting_id (str, optional): The setting (set) where the scene takes place.  Create or look up
            settings first so scenes reuse the same sets.
        time_of_day (str, optional): Slugline time, e.g. 'day', 'night', 'dusk'.
        mood (str, optional): The emotional tone and lighting mood of the scene.
        cast (list[CharacterRef], optional): The characters in the scene with the variant (wardrobe) worn.
        props (list[Prop], optional): Scene-specific props beyond the setting's standing props.
        blocking (str, optional): How the characters are staged and move through the setting.

    Returns:
        A status message indicating the result of the scene creation.
    """
    return create_scene_body(wrapper.context, name, story, insertion_location,
                             setting_id, time_of_day, mood, cast, props, blocking)


@function_tool
def create_setting(wrapper: RunContextWrapper[APPState],
        series_id: str,
        name: str,
        description: str,
        interior: bool,
        props: Optional[list[Prop]] = None,
    ) -> Setting | str:
    """
    Create a new setting (a recurring place where scenes take place) for a series.
    Settings are dressed with props and later rendered as style-keyed master backgrounds
    that multiple panels share, so the setting stays visually consistent across the issue.

    Before creating a setting, check the existing ones (read_all_settings) so sets are
    reused rather than duplicated.

    Args:
        series_id: The id of the series the setting belongs to.
        name: A short (1-5 word) name for the setting, e.g. 'The Rusty Nail Saloon'.
        description: A detailed visual description: architecture, layout, lighting, era,
            palette.   Detailed enough that different artists would draw the same place.
        interior: True for interior (INT.) settings, False for exterior (EXT.).
        props: The props that dress the setting, each with a name and a visual description.

    Returns:
        The newly created Setting object, or an error message.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    series: Series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if series is None:
        return f"Series with ID {series_id} not found."

    setting = Setting(
        setting_id=normalize_id(name),
        series_id=series_id,
        name=name,
        description=description,
        interior=interior,
        props=props or [],
        images={},
    )
    # creator() verifies the key is free; overwrite=True preserves the slug id so
    # settings stay addressable by name across scenes.
    return creator(wrapper=wrapper, obj=setting, overwrite=True)


class PanelSpec(BaseModel):
    """One panel in a scene's panel layout, used by create_scene_panels."""
    name: str = Field(..., description="A short (3-5 word) name for the panel.")
    beat: str = Field(..., description="The narrative beat: what changes or happens in this moment (1-3 sentences).")
    description: str = Field(..., description="A detailed visual description of the panel: framing, point of view, foreground/background, character poses and expressions.  Use comics vocabulary (panel, frame, figure), never film vocabulary (shot, camera, footage).")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel: landscape, portrait or square.")
    characters: list[CharacterRef] = Field(default_factory=list, description="The characters in frame, with the variant (wardrobe) used as visual reference.")
    narration: list[Narration] = Field(default_factory=list, description="Narration boxes for the panel.")
    dialogue: list[Dialogue] = Field(default_factory=list, description="Dialogue balloons for the panel.")


@function_tool
def create_scene_panels(wrapper: RunContextWrapper[APPState],
        series_id: str,
        issue_id: str,
        scene_id: str,
        panels: list[PanelSpec],
    ) -> str:
    """
    Create the full panel layout for a scene in one call: turns a list of panel specs
    (beats already broken down) into panels appended to the scene in order.   Use this
    after the scene's story, cast and blocking are settled — it turns the thumbnailed
    layout into real panels.

    Args:
        series_id: The id of the series.
        issue_id: The id of the issue.
        scene_id: The id of the scene to panelize.
        panels: The ordered panel layout.  Favor image-driven storytelling: strong panels
            show change in action, framing, or emotion; dialogue and narration should be
            minimal and purposeful.

    Returns:
        A status message summarizing the created panels.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    scene: SceneModel = storage.read_object(cls=SceneModel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    if scene is None:
        return f"Scene with ID {scene_id} not found in issue {issue_id}."

    existing: list[Panel] = storage.read_all_objects(cls=Panel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}, order_by="panel_number")

    created = []
    for i, spec in enumerate(panels):
        panel = Panel(
            panel_id=normalize_id(spec.name),
            issue_id=issue_id,
            series_id=series_id,
            scene_id=scene_id,
            panel_number=len(existing) + i + 1,
            name=normalize_name(spec.name),
            beat=spec.beat or spec.description,
            description=spec.description,
            aspect=spec.aspect,
            character_references=spec.characters,
            narration=spec.narration,
            dialogue=spec.dialogue,
            image=None,
            reference_images=[],
        )
        storage.create_object(data=panel)
        created.append(panel.name)

    state.is_dirty = True
    return f"Created {len(created)} panels for scene '{scene.name}': " + ", ".join(created)


@function_tool
def create_story(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str,
                 title: str, text: Optional[str]) -> str:
    """
    Add a story to the issue.   Classic comics run more than one story in a
    book — a main feature and backups.   The story appears as a manuscript
    page in the issue view, in order, and breaks down into scenes.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        title: The story's title.
        text: The story's script text.  Optional; default to empty.

    Returns:
        A status message with the new story's id.
    """
    from schema import Story
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    existing = storage.read_all_objects(Story, {"series_id": series_id, "issue_id": issue_id})
    story = Story(story_id=normalize_id(title), issue_id=issue_id, series_id=series_id,
                  story_number=max((s.story_number for s in existing), default=0) + 1,
                  name=normalize_name(title), text=text or "")
    result = creator(wrapper=wrapper, obj=story)
    if isinstance(result, str):
        return result
    return f"Story '{story.name}' added to the issue (story_id: {story.story_id})."


@function_tool
def create_insert(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str,
                  name: str, kind: str, description: Optional[str],
                  after_scene_number: Optional[int]) -> str:
    """
    Add a FULL-PAGE INSERT to the book: a poster, an ad, a pin-up, the
    mailbag — a page that isn't story panels but belongs in the issue.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        name: A short name, e.g. 'Carnival poster'.
        kind: 'poster', 'ad', 'pin-up', 'mailbag' or 'title-page'.  Default to 'poster'.
        description: What the page shows, in enough detail to render it.
        after_scene_number: The insert appears after this scene number
            (0 = right after the script pages).  Default to 0.

    Returns:
        A status message with the new insert's id.
    """
    from schema import Insert
    state: APPState = wrapper.context
    # the anchor must be a real place in the book
    top = max((s.scene_number for s in state.storage.read_all_objects(
        SceneModel, {"series_id": series_id, "issue_id": issue_id})), default=0)
    anchor = max(0, min(top, after_scene_number or 0))
    insert = Insert(insert_id=normalize_id(name), issue_id=issue_id, series_id=series_id,
                    kind=kind or "poster", name=normalize_name(name),
                    description=description or "",
                    after_scene_number=anchor, image=None)
    result = creator(wrapper=wrapper, obj=insert)
    if isinstance(result, str):
        return result
    return (f"Insert '{insert.name}' ({insert.kind}) added after scene "
            f"{insert.after_scene_number} (insert_id: {insert.insert_id}).  "
            f"Render its art with generate_insert_art.")


@function_tool
def derive_character(wrapper: RunContextWrapper[APPState], series_id: str,
                     source_character_id: str, new_name: str,
                     what_changes: str) -> str:
    """
    Cast a NEW character built from an existing one — a sibling, a parent,
    a rival from the same clan, the same actor in a different role.  The new
    character inherits the source's look (its reference sheet anchors every
    future render) with the stated changes applied.

    Args:
        series_id: The ID of the series.
        source_character_id: The character to derive from.
        new_name: The new character's name.
        what_changes: What differs from the source — age, build, wardrobe,
            demeanor ('his older sister: taller, silver-streaked hair,
            a ranger's leathers, wary where he is warm').

    Returns:
        A status message with the new character's id and what anchors it.
    """
    import os
    from schema import CharacterVariant as _CV
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    src_ch = storage.read_object(cls=CharacterModel, primary_key={
        "series_id": series_id, "character_id": source_character_id})
    if src_ch is None:
        return f"Character '{source_character_id}' not found."
    src_variants = storage.read_all_objects(_CV, {"series_id": series_id,
                                                  "character_id": source_character_id})
    src_v = src_variants[0] if src_variants else None

    ch = CharacterModel(character_id=normalize_id(new_name), series_id=series_id,
                        name=normalize_name(new_name),
                        description=f"Derived from {src_ch.name}: {what_changes}\n\n"
                                    f"(Source: {src_ch.description})")
    result = creator(wrapper=wrapper, obj=ch)
    if isinstance(result, str):
        return result

    base = _CV(
        variant_id="base", series_id=series_id, character_id=ch.character_id,
        name="base",
        description=f"Same family/species/build as {src_ch.name}, but: {what_changes}",
        race=getattr(src_v, 'race', None) or "", gender=getattr(src_v, 'gender', None) or "",
        age=getattr(src_v, 'age', None) or "", height=getattr(src_v, 'height', None) or "",
        appearance=((getattr(src_v, 'appearance', None) or "") +
                    f"\nCHANGED from the source: {what_changes}").strip(),
        attire=getattr(src_v, 'attire', None) or "",
        behavior=getattr(src_v, 'behavior', None) or "",
        images={},
    )
    storage.create_object(data=base, overwrite=True)

    # THE ANCHOR: the source's best sheet rides the new variant's uploads,
    # so every render of the new character is held to the family look
    anchored = ""
    sheet = storage.find_variant_image(series_id=series_id,
                                       character_id=source_character_id,
                                       variant_id=getattr(src_v, 'variant_id', 'base') if src_v else 'base')
    if sheet and os.path.exists(sheet):
        import io as _io
        with open(sheet, 'rb') as fh:
            storage.upload_reference_image(base, f"family-look--{source_character_id}.png",
                                           _io.BytesIO(fh.read()), 'image/png')
        anchored = f"  {src_ch.name}'s sheet anchors the family look."

    state.is_dirty = True
    return (f"Cast {ch.name} (character_id: {ch.character_id}), derived from "
            f"{src_ch.name}.{anchored}  Ink their reference sheet from the "
            f"character's page (or create_styled_image) — the changes: {what_changes}")
