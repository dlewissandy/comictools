from loguru import logger
from typing import Optional
from uuid import uuid4
from agents import Agent, function_tool, Tool, RunContextWrapper
from pydantic import BaseModel
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
    Determine the insertion index based on the insertion location and item count.
    Args:
        item_number (int): The number of the item being inserted.
        insertion_location (InsertionLocation): The location where the item should be inserted.
        item_count (int): The current number of items in the list.
    """
    # Determine the panel number based on insertion location
    if isinstance(insertion_location, AfterLast):
        # Insert after the last panel
        item_number = item_count + 1
    elif isinstance(insertion_location, After):
        # Insert after a specific panel
        if insertion_location.index < 0 or insertion_location.index >= item_count:
            raise ValueError(f"Invalid index {insertion_location.index} for insertion location.")
        item_number = insertion_location.index + 2
    elif isinstance(insertion_location, BeforeFirst):
        # Insert before the first panel
        item_number = 1
    elif isinstance(insertion_location, Before):
        # Insert before a specific panel
        if insertion_location.index < 0 or insertion_location.index >= item_count:
            raise ValueError(f"Invalid index {insertion_location.index} for insertion location.")
        item_number = insertion_location.index + 1
    else:
        raise ValueError(f"Unknown insertion location type: {type(insertion_location)}")

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

    if storage.read_object(cls=obj.__class__, primary_key=pk) is not None and not overwrite:
        logger.error(f"{obj.__class__.__name__} with key '{obj.primary_key}' already exists.")
        return f"{obj.__class__.__name__} with key '{obj.primary_key}' already exists."

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

    return creator(
        wrapper=wrapper,
        obj=Publisher(
            publisher_id=normalize_id(name),
            name=normalize_name(name),
            description=description,
            logo=None,
            image=None
        ))


@function_tool
def create_comic_series(wrapper: RunContextWrapper[APPState], series_title: str, description: Optional[str], publisher: Optional[str]) -> Series:
    """
    Create a new comic series with the given title.
    
    Args:
        series_title: The title of the new comic series.
        description: An optional description of the comic series.   This should be 2-5 paragraphs about the series, its themes, characters and setting.  This is intended for writers and artists to understand the series and generate content for it.   IT IS NOT INTENDED FOR THE READER, OR MARKETING.
        publisher: An optional name of the publisher for the comic series.   If povided, YOU MUST verify that the publisher exists in the database.
    
    Returns:
        The created Series object.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # check to see if the series already exists.
    series_id = normalize_id(series_title)
    if storage.read_object(Series, {"series_id": series_id}) is not None:
        logger.error(f"Series with title '{series_title}' already exists.")
        return f"Series with title '{series_title}' already exists."
    else:
        logger.info(f"The title '{series_title}' is available.")
    series = Series(series_id=series_id, name=series_title, description=description, publisher_id=publisher)
    new_id = storage.create_object(data=series)
    selection = state.selection
    new_itm = SelectionItem(name=series.name, id=new_id, kind=SelectedKind.SERIES)
    new_sel = [s for s in selection]+[new_itm]
    state.change_selection(new=new_sel)
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
    selection = state.selection
    new_itm = SelectionItem(name=style.name, id=style_id, kind=SelectedKind.STYLE)
    new_sel = [s for s in selection]+[new_itm]
    state.change_selection(new=new_sel)
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
    Create a new character variant with the provided attributes.
    
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
    insertion_location: InsertionLocation = AfterLast,
) -> str:
    """
Use this tool to create a single panel in a comic book. Choose this when you 
want to advance the visual narrative by showing a specific moment in time 
through composition, character action, and layout. This tool emphasizes
visual storytelling; prefer it over textual exposition when possible.

This tool is appropriate when:

* A character takes a meaningful action or reacts with clear emotion
* The scene changes in location, time, or energy
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
        series_id = series.id,
        title = title,
        story = story,
        issue_number = issue_number,
        publication_date = None,  # This can be set later
        price = None,  # This can be set later
        author = None,  # This can be set later
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

@function_tool
def create_cover(
    wrapper: RunContextWrapper[APPState], 
    series_id: str,
    issue_id: str,
    location: CoverLocation,
    cover_id: Optional[str],
    description: str,
    characters: list[CharacterRef] = []
) -> str:
    """
    Create a cover for the specified issue.    The foreground and optional background descriptions
    will be used by artists to create the cover image, and should be detailed enough to ensure
    that the cover could be faithfully rendered by an artist.   Focus on visual elements, composition,
    and be specific.   Different artists given the same description should be able to produce
    similar covers, even if they are not identical.

    Args:
        series_id: The ID of the comic series to create the cover for.
        issue_id: The ID of the comic issue to create the cover for.
        location: The location metadata for the cover. MUST BE ONE OF "front", "back", "inside-front", "inside-back".
        cover_id: Optional unique identifier for the cover. If not provided, a unique ID will be generated.
        description: A detailed description of the visual elements in the cover.
        characters: A list of character references to include on the cover.   These references should
            be characters that are in the series.   VERIFY that they exist to avoid errors.
    Returns:
        A confirmation message indicating the cover was created successfully.
    """
    try:
        state: APPState = wrapper.context
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


        new_cover_id = normalize_id(cover_id) if cover_id else normalize_id(f"{location.value}-{uuid4().hex[:8]}")
        cover = Cover(
            cover_id=new_cover_id,
            location=location,
            issue_id=issue_id,
            series_id=series_id,
            character_references=characters,
            style_id=issue.style_id,
            aspect=FrameLayout.PORTRAIT,
            description=description,
            image=None,  # Image will be set later if needed
            reference_images=[]  # Reference images can be added later
        )

        return creator(
            wrapper=wrapper,
            obj=cover,
            overwrite=True,
        )
    except Exception as e:
         # Get the full traceback
        tb = traceback.format_exc()
        logger.error(f"Error creating cover: {tb}")
        return f"Error creating cover: {str(e)}\n{tb}"

@function_tool
def create_scene(wrapper: RunContextWrapper[APPState], name: str, story: str, insertion_location: InsertionLocation) -> str:
    """
    Create a new scene for the currently selected comic book issue.   This will create a new scene
    with the default properties and add it to the issue at the specified insertion location.

    Args:
        name (str): The name of the new scene.   This should be a unique identifier for the scene, and
            should be 2-5 words long, and should only contain letters, numbers and spaces (e.g. 
            "Teapot ride", "Joey gets hungry", etc).
        story (str): The story for the new scene.   This should be detailed enough to guide the 
            creative team (authors, artists, etc.) in creating the storyboard and artwork for the scene.
            This includes information about the setting, characters involved, and key actions or events.
            It should not be a full script, but rather a summary of the scene's content and purpose.
            Consider the key information that is required to ensure that this scene can be written and 
            maintains the narrative flow of the comic book issue.
        insertion_location (InsertionLocation): The location where the new scene should be inserted.
            NOTE: LIST ELEMENTS ARE ONES-BASED, SO THE FIRST ELEMENT IS AT INDEX 1.

    Returns:
        A status message indicating the result of the scene creation.
    """
    state: APPState = wrapper.context
    logger.trace(f"inserting scene {name} at {InsertionLocation}")
    storage: GenericStorage = state.storage

    issue_id = state.selection[-1].id
    series_id = state.selection[-2].id
    pk = {"issue_id": issue_id, "series_id": series_id}

    issue: Issue = storage.read_object(cls=Issue, primary_key=pk)
    scenes: list[SceneModel] = storage.read_all_objects(cls=SceneModel, primary_key=pk, order_by="scene_number")

    scene = SceneModel(
        scene_id=normalize_id(name),
        issue_id=issue_id,
        series_id=series_id,
        name=name,
        story=story,
        style_id=issue.style_id,
        aspect=FrameLayout.PORTRAIT,
        scene_number=insertion_index(
            insertion_location=insertion_location, 
            item_count=len(scenes)
        ),
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
    return f"Scene created successfully for issue {issue.name}."
