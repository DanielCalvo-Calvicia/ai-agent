
from dataclasses import dataclass
from enum import Enum


ErrConstraintFormatNotInList = ValueError("format must be one of json, markdown, plain_text, code, table")
ErrConstraintLanguageNotInList = ValueError("language must be one of english, spanish, portuguese, french, german")
ErrConstraintToneNotInList = ValueError("tone must be one of formal, neutral, informal")
ErrConstraintLengthMax = ValueError("length must be a number between 1 and 1000")


class Formats(str, Enum):
    EMPTY = ""  
    JSON = "json"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    CODE = "code"
    TABLE = "table"

class Languages(str, Enum):
    EMPTY = "" 
    ENGLISH = "english"
    SPANISH = "spanish"
    PORTUGUESE = "portuguese"
    FRENCH = "french"
    GERMAN = "german"

class Tones(str, Enum):
    EMPTY = "" 
    FORMAL = "formal"
    NEUTRAL = "neutral"
    INFORMAL = "informal"

@dataclass(frozen=True)
class Constraints:
    format: Formats
    language: Languages
    tone: Tones
    length: str

    def __post_init__(self):
        self.validate()

    def validate(self):
        self._validate_format()
        self._validate_language()
        self._validate_tone()

    def _validate_format(self):
        if self.format not in Formats:
            raise ValueError(ErrConstraintFormatNotInList)
        
    def _validate_language(self):
        if self.language not in Languages:
            raise ValueError(ErrConstraintLanguageNotInList)

    def _validate_tone(self):
        if self.tone not in Tones:
            raise ValueError(ErrConstraintToneNotInList)

def create_constraints(format: str, language: str, tone: str, length: str):
    format_enum = get_format_from_string(format)
    language_enum = get_language_from_string(language)
    tone_enum = get_tone_from_string(tone)
    constraints = Constraints(format=format_enum, language=language_enum, tone=tone_enum, length=length)
    return constraints
        
def get_format_from_string(format_string: str):
    return Formats(format_string.lower())

def get_language_from_string(language_string: str):
    return Languages(language_string.lower())

def get_tone_from_string(tone_string: str):
    return Tones(tone_string.lower())
