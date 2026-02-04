from agents import Tool

from agentic.tools import (
    read_all_characters,
    read_all_issues,
    read_all_panels,
    read_all_scenes,
    read_all_variants,
    read_all_publishers,
    read_all_styles,
    read_all_series,
    read_all_covers,

    read_character,
    read_issue,
    read_panel,
    read_publisher,
    read_scene,
    read_series,
    read_style,
    read_cover,
    read_variant,

    create_publisher,
    create_comic_series,
    create_style,
    create_panel,
    create_character,
    create_issue,
    create_scene,
    create_cover,

    delete_publisher,
    delete_style,
    delete_series,
    delete_character,
    delete_character_variant,
    delete_cover,
    delete_issue,
    delete_scene,
    delete_panel,

    select_publisher,
    select_series,
    select_comic_style,

    update_character_description,
    update_cover_description,
    update_style_description,

    update_variant_age,
    update_variant_appearance,
    update_variant_attire,
    update_variant_behavior,
    update_variant_description,
    update_variant_gender,
    update_variant_height,
    update_variant_race,

    generate_publisher_logo_reference_image,  
    generate_cover_image,
    delete_cover_image,
    create_character_style_example_image
)
from agentic.tools.creator import create_variant
from agentic.tools.imaging import (
    delete_character_style_example,
    delete_dialog_style_example,
    delete_publisher_logo_reference_image,
    create_styled_image_for_character_variant,
    create_art_style_example_image,
    create_dialog_style_example_image,
    delete_art_style_example

)
from agentic.tools.updater import (
    update_character_description,
    update_issue_story,
    update_issue_publication_date,
    update_issue_price,
    update_issue_writer,
    update_issue_artist,
    update_issue_colorist,
    update_issue_creative_minds,
    update_logo_description,
    update_publisher_description,
    update_series_description,
    update_cover_style,
    update_cover_aspect_ratio,
    update_art_style,
    update_dialog_style,
    update_character_style,
)

TOOLKITS: dict[str,list[Tool]] = {
    "all-publishers": [
        # Create
        create_publisher,
        # Read
        read_publisher,
        read_all_publishers,
        # Update

        # Delete
        delete_publisher,
        # Navigation
        select_publisher,
    ],
    "all-styles": [
        # Navigation
        select_comic_style,

        # Getters
        read_style,
        read_all_styles,

        create_style,
        delete_style,
    ],
    "all-series": [
        # Navigation
        select_series,

        # Getters
        read_series,
        read_publisher,
        read_all_series,
        read_all_publishers,

        # Creators
        create_comic_series,

        # Deleters
        delete_series
    ],
    "character": [
        # Navigation tools

        # Query Tools
        read_character,
        read_series,
        read_all_characters,
        read_all_variants,
    
        # describe_image,
        # TODO: update_character_name,
        update_character_description,

        delete_character,
        create_variant,
        # create_variant_from_image
        # TODO: Create variant from image
        # TODO: delete variant
    ],
    "cover": [
        # Create
        # Read
        read_cover,
        read_all_styles,
        # Update
        update_cover_description,
        update_cover_aspect_ratio,
        update_cover_style,
        # Delete
        delete_cover,
        # Navigation
        # Imaging
        generate_cover_image,
        delete_cover_image
    ],
    "issue": [
        # Create
        create_cover,
        create_scene,
        # Read
        read_issue,
        read_style,
        read_all_styles,
        read_cover,
        read_all_covers,
        read_scene,
        read_all_scenes,
        # Update
        # TODO: Update issue name
        update_issue_story,
        update_issue_publication_date,
        update_issue_price,
        update_issue_writer,
        update_issue_artist,
        update_issue_colorist,
        update_issue_creative_minds,
        # Delete
        delete_issue,
        delete_cover,
        delete_scene,
        # TODO Reorder scenes

    ],
    "panel": [
        # Create
        # Read
        read_panel,
        read_scene,
        # Update
        # Delete
        delete_panel,
        # Navigation
    ],
    "publisher": [
        # Create

        # Read
        read_publisher,
        # Update
        update_logo_description,
        update_publisher_description,
        # Delete
        delete_publisher,

        # Navigation

        # Imaging
        generate_publisher_logo_reference_image,
        delete_publisher_logo_reference_image
    ],
    "scene": [
        # Create
        create_panel,
        # Read
        read_scene,
        read_panel,
        read_all_panels,
        read_style,
        # Update
        # Delete
        delete_scene,
        delete_panel
    
    ],
    "series": [
        # Create
        create_character,
        create_issue,

        # Read
        read_series,
        read_publisher,
        read_all_publishers,
        read_character,
        read_all_characters,
        read_issue,
        read_all_issues,

        # Update
        update_series_description,

        # Delete
        delete_series,
        delete_issue,
        delete_character,
    ],
    "style": [
        # Navigation
        # Create
        # Read
        read_style,
        # Update
        update_style_description,
        update_art_style,
        update_dialog_style,
        update_character_style,
        # Delete
        delete_style,
        # Images
        create_character_style_example_image,
        delete_character_style_example,
        create_art_style_example_image,
        delete_art_style_example,
        create_dialog_style_example_image,
        delete_dialog_style_example

    ],
    "styled-variant": [
        # Navigation
        # Create
        create_styled_image_for_character_variant,
        # Read
        read_style,
        read_series,
        read_character,
        read_variant
    ],
    "variant": [
        # Navigation
        # Create
        # Read
        read_style,
        read_all_styles,
        read_variant,
        # Update
        update_variant_age,
        update_variant_appearance,
        update_variant_attire,
        update_variant_behavior,
        update_variant_description,
        update_variant_gender,
        update_variant_height,
        update_variant_race,

        # Delete
        delete_character_variant,
        # Imaging
        create_styled_image_for_character_variant,
    ],
}

TOOLKITS["front-cover"] = TOOLKITS["cover"]
TOOLKITS["back-cover"] = TOOLKITS["cover"]
TOOLKITS["inside-front-cover"] = TOOLKITS["cover"]
TOOLKITS["inside-back-cover"] = TOOLKITS["cover"]
