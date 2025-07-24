from .context import read_context

from .updater import (
    update_character_description,
    update_logo_description,
    update_publisher_description,
    update_series_description,
    update_variant_age,
    update_variant_appearance,
    update_variant_attire,
    update_variant_behavior,
    update_variant_description,
    update_variant_gender,
    update_variant_height,
    update_variant_race,

)

from .creator import (
    create_publisher,
    create_comic_series,
    create_style,
    create_variant,
    create_panel,
    create_character,
    create_issue,
    create_cover,
)

from .reader import (
    read_character,
    read_issue,
    read_panel,
    read_publisher,
    read_scene,
    read_series,
    read_style,
    read_cover,
    read_variant,
    read_all_characters,
    read_all_issues,
    read_all_panels,
    read_all_scenes,
    read_all_variants,
    read_all_publishers,
    read_all_styles,
    read_all_series,
    read_all_covers,
)


from .deleter import (
    delete_series,
    delete_style,
    delete_character,
    delete_publisher,
    delete_issue,
    delete_scene,
    delete_panel,
    delete_cover,
    delete_character_variant,
)

from .normalization import (
    normalize_id,
    normalize_name,
)

from .navigation import (
    select_publisher,
    select_series,
    select_comic_style,
)

from .imaging import (
    generate_publisher_logo_image,
    delete_publisher_logo_image,
    generate_cover_image,
    delete_cover_image
)


# RE-EXPORTING
__all__ = [
    # CONTEXT
    "read_context",

    # CREATE
    "create_comic_series",
    "create_publisher",
    "create_style",
    "create_variant",
    "create_panel",
    "create_character",
    "create_issue",


    # READ
    "read_character",
    "read_issue",
    "read_panel",
    "read_publisher",
    "read_scene",
    "read_series",
    "read_style",
    "read_cover",
    "read_variant",
    "read_all_characters",
    "read_all_issues",
    "read_all_panels",
    "read_all_scenes",
    "read_all_variants",
    "read_all_publishers",
    "read_all_styles",
    "read_all_series",
    "read_all_covers",

    # UPDATE
    "update_character_description",
    "update_issue_story",
    "update_issue_publication_date",
    "update_issue_price",
    "update_issue_writer",
    "update_issue_artist",
    "update_issue_colorist",
    "update_issue_creative_minds",
    "update_logo_description",
    "update_publisher_description",
    "update_series_description",
    "update_variant_age",
    "update_variant_appearance",
    "update_variant_attire",
    "update_variant_behavior",
    "update_variant_description",
    "update_variant_gender",
    "update_variant_height",
    "update_variant_race",

    # DELETE
    "delete_publisher",
    "delete_style",
    "delete_series",
    "delete_character",
    "delete_character_variant",
    "delete_cover",
    "delete_issue",
    "delete_scene",
    "delete_panel",
    
    # NAVIGATION
    "select_publisher",
    "select_series",
    "select_comic_style",

    # NORMALIZATION
    "normalize_id",
    "normalize_name",

    # IMAGES
    "generate_publisher_logo_image",
    "delete_publisher_logo_image",
    "generate_cover_image",
    "delete_cover_image"

]