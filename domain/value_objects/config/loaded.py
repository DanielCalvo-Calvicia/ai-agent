from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Loaded:
    """What one source gave for one kind of file: the files that could be read, and why the others could not."""
    items: Dict[str, dict] = field(default_factory=dict)      # name (the file name without .json) -> the parsed object
    errors: Dict[str, str] = field(default_factory=dict)      # name -> what is wrong with that file
