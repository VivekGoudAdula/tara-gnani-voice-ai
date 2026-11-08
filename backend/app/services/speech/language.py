"""Language code normalization for Gnani Speech-to-Text and Text-to-Speech models."""

from typing import Optional

LANGUAGE_CODE_MAP = {
    "telugu": "te-IN",
    "te": "te-IN",
    "te-in": "te-IN",
    "hindi": "hi-IN",
    "hi": "hi-IN",
    "hi-in": "hi-IN",
    "english": "en-IN",
    "en": "en-IN",
    "en-in": "en-IN",
    "en-us": "en-IN",
    "kannada": "kn-IN",
    "kn": "kn-IN",
    "kn-in": "kn-IN",
    "tamil": "ta-IN",
    "ta": "ta-IN",
    "ta-in": "ta-IN",
    "marathi": "mr-IN",
    "mr": "mr-IN",
    "mr-in": "mr-IN",
    "bengali": "bn-IN",
    "bn": "bn-IN",
    "bn-in": "bn-IN",
    "gujarati": "gu-IN",
    "gu": "gu-IN",
    "gu-in": "gu-IN",
    "malayalam": "ml-IN",
    "ml": "ml-IN",
    "ml-in": "ml-IN",
    "punjabi": "pa-IN",
    "pa": "pa-IN",
    "pa-in": "pa-IN",
    "assamese": "as-IN",
    "as": "as-IN",
    "as-in": "as-IN",
    "auto": "indic-auto",
    "indic-auto": "indic-auto",
}


def normalize_language_code(language_input: Optional[str]) -> str:
    """
    Normalize any language string (e.g. 'telugu', 'Telugu', 'te', 'te-IN') into Gnani BCP-47 code.

    Args:
        language_input: Spoken language name or code.

    Returns:
        BCP-47 language tag supported by Gnani Prisma and Timbre (e.g. 'te-IN').
    """
    if not language_input:
        return "te-IN"
    cleaned = str(language_input).strip().lower()
    return LANGUAGE_CODE_MAP.get(cleaned, LANGUAGE_CODE_MAP.get(cleaned.split("-")[0], "te-IN"))

