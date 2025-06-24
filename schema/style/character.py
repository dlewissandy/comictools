from pydantic import BaseModel, Field

class CharacterStyle(BaseModel):
    """
    Character appearance and form style guidelines for a comic series or title.
    """
    # Proportions & Anatomy
    head_to_body_ratio: str = Field(
        ...,
        description="Proportional relationship between head height and overall body height (e.g., '1:6 realistic', '1:3 cartoony')."
    )
    limb_proportions: str = Field(
        ...,
        description="Relative length and thickness of arms and legs (e.g., 'long/slender', 'short/stubby') for consistent character shape."
    )
    anatomy_detail: str = Field(
        ...,
        description=(
            "Level of muscular or structural detail in anatomy,"
            " including stylized anatomy choices such as finger count per hand, etc."
        )
    )

    # Facial Features & Expressions
    eye_style: str = Field(
        ...,
        description="Basic construction of eyes (e.g., 'dot', 'circle', 'detailed iris', 'half-lid') for uniform character expression."
    )
    nose_style: str = Field(
        ...,
        description="Rendering approach for noses (e.g., 'line', 'button', 'realistic') matching the series’ aesthetic."
    )
    mouth_style: str = Field(
        ...,
        description="Shape and complexity of mouths (e.g., 'simple curve', 'multi-line', 'teeth detail') for consistent emotional portrayal."
    )
    expression_exaggeration: str = Field(
        ...,
        description="Degree of facial expression amplification guiding emotional intensity."
    )

    # Silhouette & Readability
    silhouette_clarity: str = Field(
        ...,
        description="Degree to which a character’s outline stands out from the background (e.g., 'very high', 'high', 'medium')."
    )
    silhouette_shape_language: str = Field(
        ...,
        description="Dominant geometric styling of character silhouettes (e.g., 'angular', 'rounded', 'organic curves')."
    )

    # Detail & Texture
    detail_complexity: str = Field(
        ...,
        description="Amount of ornamental or structural detail on characters (e.g., 'flat shapes', 'folds & creases')."
    )
    texture_accents: str = Field(
        ...,
        description="List of surface embellishments (e.g., 'hair-strands', 'fabric weave', 'freckles') for added visual interest.  Default to empty string."
    )

    # Dynamic & Expression Lines
    motion_line_style: str = Field(
        ...,
        description="Style of motion indicators (e.g., 'speed lines', 'blur trails') to convey movement.  Default to empty string."
    )
    expression_line_style: str = Field(
        ...,
        description="Types of emotional accent lines (e.g., 'sweat drops', 'stress lines', 'vein marks') used around characters.  Default to empty string."
    )

    # Signature Motifs
    signature_motifs: str = Field(
        ...,
        description="Key identifying shapes or icons unique to the series.  Default to empty string."
    )
    recurring_flourishes: str = Field(
        ...,
        description="Small, repeated stylistic details (e.g., 'Garfield’s half-lids', 'Blondie’s hair curls') for brand consistency.  Default to empty string."
    )

    def format(self):
        self_json = self.model_dump()
        result = "## Character Style\n  The character style defines the visual language of the characters, including proportions, anatomy, and expressions.   It should apply to all characters unless specified otherwise.\n\n"
        for key, value in self_json.items():
            if value is None or value == "":
                continue
            result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
        return result
