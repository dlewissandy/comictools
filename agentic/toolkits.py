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
from agentic.tools.creator import create_variant, create_variant_from_image, create_setting, create_scene_panels
from agentic.tools.reader import read_setting, read_all_settings
from agentic.tools.deleter import delete_setting, undo_last_delete
from agentic.tools.updater import (
    update_scene_setting,
    update_scene_cast,
    update_panel_cast,
    update_panel_dialogue,
    update_scene_blocking,
    update_scene_props,
    update_setting_description,
    update_setting_props,
    update_cover_setting,
)
from agentic.tools.imaging import generate_setting_background, generate_series_title_art, generate_panel_image, generate_figure_acetate, split_layer, export_issue_pdf, preflight_issue, layout_issue_pages, render_missing_panels
from agentic.tools.library import list_library_assets, import_character, import_setting, import_prop, import_outfit
from agentic.tools.assets import (
    create_prop, read_all_props, update_prop_description, delete_prop,
    create_outfit, read_all_outfits, update_outfit_description, delete_outfit,
    compose_character_variant, extract_outfit_from_variant,
)
from agentic.tools.imaging import generate_prop_reference, generate_outfit_reference
from agentic.tools.imaging import (
    delete_character_style_example,
    delete_dialog_style_example,
    delete_publisher_logo_reference_image,
    create_styled_image_for_character_variant,
    create_art_style_example_image,
    create_dialog_style_example_image,
    delete_art_style_example,
    inpaint_image_region,
    outpaint_image_region

)
from agentic.tools.updater import (
    update_character_description,
    update_character_name,
    update_issue_story,
    update_issue_name,
    update_issue_publication_date,
    update_issue_price,
    update_issue_writer,
    update_issue_artist,
    update_issue_colorist,
    update_issue_creative_minds,
    update_logo_description,
    update_publisher_description,
    update_series_description,
    update_series_name,
    update_style_name,
    update_scene_name,
    update_scene_story,
    update_panel_name,
    update_panel_beat,
    update_panel_description,
    move_scene,
    move_panel,
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
        undo_last_delete,
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
        update_character_name,
        update_character_description,

        delete_character,
        delete_character_variant,
        create_variant,
        create_variant_from_image,
        compose_character_variant,
        extract_outfit_from_variant,
        read_all_outfits,
        read_all_props,
        create_outfit,
        create_prop,
    ],
    "cover": [
        # Create
        # Read
        read_cover,
        read_all_styles,
        read_setting,
        read_all_settings,
        # Update
        update_cover_description,
        update_cover_aspect_ratio,
        update_cover_style,
        update_cover_setting,
        # Delete
        undo_last_delete,
        delete_cover,
        # Navigation
        # Imaging
        generate_cover_image,
        generate_setting_background,
        generate_series_title_art,
        delete_cover_image
    ],
    "issue": [
        # Create
        create_cover,
        create_scene,
        create_scene_panels,
        create_setting,
        # Imaging
        generate_series_title_art,
        # Library
        list_library_assets,
        import_character,
        import_setting,
        # Read
        read_issue,
        read_style,
        read_all_styles,
        read_cover,
        read_all_covers,
        read_scene,
        read_all_scenes,
        read_setting,
        read_all_settings,
        read_all_characters,
        read_all_variants,
        # Update
        update_issue_name,
        update_issue_story,
        update_scene_setting,
        update_scene_cast,
        update_scene_blocking,
        update_issue_publication_date,
        update_issue_price,
        update_issue_writer,
        update_issue_artist,
        update_issue_colorist,
        update_issue_creative_minds,
        # Reorder
        move_scene,
        # Publish
        render_missing_panels,
        layout_issue_pages,
        preflight_issue,
        export_issue_pdf,
        # Delete
        undo_last_delete,
        delete_issue,
        delete_cover,
        delete_scene,
    ],
    "panel": [
        # Create
        create_prop,
        create_setting,
        # Read
        read_panel,
        read_scene,
        read_setting,
        read_all_settings,
        read_all_characters,
        read_all_variants,
        read_all_props,
        # Update
        update_panel_name,
        update_panel_beat,
        update_panel_description,
        update_panel_cast,
        update_panel_dialogue,
        update_scene_setting,
        update_scene_props,
        # Delete
        undo_last_delete,
        delete_panel,
        # Imaging
        generate_setting_background,
        generate_panel_image,
        generate_figure_acetate,
        split_layer,
        render_missing_panels,
        inpaint_image_region,
        outpaint_image_region,
        # Navigation
    ],
    "publisher": [
        # Create
        create_comic_series,
        # Read
        read_publisher,
        read_all_series,
        select_series,
        # Update
        update_logo_description,
        update_publisher_description,
        # Delete
        undo_last_delete,
        delete_publisher,

        # Navigation

        # Imaging
        generate_publisher_logo_reference_image,
        delete_publisher_logo_reference_image
    ],
    "scene": [
        # Create
        create_panel,
        create_scene_panels,
        create_setting,
        # Library
        list_library_assets,
        import_character,
        import_setting,
        # Read
        read_scene,
        read_panel,
        read_all_panels,
        read_style,
        read_setting,
        read_all_settings,
        read_all_characters,
        read_all_variants,
        # Update
        update_scene_name,
        update_scene_story,
        update_scene_setting,
        update_scene_cast,
        update_scene_blocking,
        update_scene_props,
        # Reorder
        move_panel,
        # Delete
        undo_last_delete,
        delete_scene,
        delete_panel,
        # Imaging
        generate_setting_background,
        generate_panel_image,
        render_missing_panels,

    ],
    "series": [
        # Create
        create_character,
        create_issue,
        create_setting,
        # Imaging
        generate_series_title_art,

        # Read
        read_series,
        read_publisher,
        read_all_publishers,
        read_character,
        read_all_characters,
        read_issue,
        read_all_issues,
        read_setting,
        read_all_settings,

        # Library
        list_library_assets,
        import_character,
        import_setting,
        import_prop,
        import_outfit,
        # Assets
        create_prop,
        read_all_props,
        update_prop_description,
        delete_prop,
        create_outfit,
        read_all_outfits,
        update_outfit_description,
        delete_outfit,
        generate_prop_reference,
        generate_outfit_reference,
        # Update
        update_series_name,
        update_series_description,
        update_setting_description,
        update_setting_props,

        # Delete
        undo_last_delete,
        delete_series,
        delete_issue,
        delete_character,
        delete_setting,
    ],
    "style": [
        # Navigation
        # Create
        # Read
        read_style,
        # Update
        update_style_name,
        update_style_description,
        update_art_style,
        update_dialog_style,
        update_character_style,
        # Delete
        undo_last_delete,
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
        undo_last_delete,
        delete_character_variant,
        # Imaging
        create_styled_image_for_character_variant,
        extract_outfit_from_variant,
        generate_outfit_reference,
        generate_prop_reference,
        read_all_outfits,
        read_all_props,
    ],
    "image-editor": [
        inpaint_image_region,
        outpaint_image_region,
    ],
    "image-editor-choices": [
        inpaint_image_region,
        outpaint_image_region,
    ],
}

TOOLKITS["library"] = [
    # Browse
    list_library_assets,
    read_all_series,
    read_all_publishers,
    read_character,
    read_setting,
    # Import
    import_character,
    import_setting,
]

TOOLKITS["prop"] = [
    read_all_props,
    update_prop_description,
    delete_prop,
    generate_prop_reference,
    read_all_styles,
]

TOOLKITS["outfit"] = [
    read_all_outfits,
    update_outfit_description,
    delete_outfit,
    generate_outfit_reference,
    read_all_styles,
]

TOOLKITS["setting"] = [
    # Read
    read_setting,
    read_all_settings,
    read_all_styles,
    # Update
    update_setting_description,
    update_setting_props,
    # Delete
    delete_setting,
    # Imaging
    generate_setting_background,
]

TOOLKITS["front-cover"] = TOOLKITS["cover"]
TOOLKITS["back-cover"] = TOOLKITS["cover"]
TOOLKITS["inside-front-cover"] = TOOLKITS["cover"]
TOOLKITS["inside-back-cover"] = TOOLKITS["cover"]
