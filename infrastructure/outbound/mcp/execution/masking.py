"""
Keeps the personal columns of a tool answer from reaching the model provider (T-01.9, finding e).

An answer of dynamics_microservice is a table: metadata lines, a blank line, a header and rows with the cells separated by `|`.
A cell whose column header names a customer, an e-mail, a phone, an address, a contact or a tax or bank number is replaced by
HIDDEN before the answer goes to any model, so it also never reaches the provider's logs or Langfuse. The codes (customer and
order numbers), dates, amounts and states are kept: they are what a reply is about.

`AI_AGENT_MASK_PERSONAL_DATA=0` turns it off (default on). Nothing here logs or reports a cell.
"""
import os
import re
from typing import List

VARIABLE = "AI_AGENT_MASK_PERSONAL_DATA"
HIDDEN = "[hidden]"

# Headers of the columns to hide, compared in lower case. "Name" alone is the customer card's name column.
_PERSONAL_HEADER = re.compile(
    r"^(search )?name$"
    r"|customer name"
    r"|(sell|bill|ship)-to .*name"
    r"|e-?mail"
    r"|phone|fax|mobile"
    r"|address|street|city|post code|zip"
    r"|contact"
    r"|\bvat\b|tax (id|no)|\biban\b|bank account"
)


def masking_enabled() -> bool:
    return os.environ.get(VARIABLE, "1").strip().lower() not in ("0", "false", "no", "off")


def mask_personal_columns(text: str) -> str:
    """The answer with the cells of personal columns replaced; a text with no table, or no personal column, comes back unchanged."""
    if "|" not in text:
        return text
    lines = text.split("\n")
    hidden: List[int] = []
    after_blank = True
    for i, line in enumerate(lines):
        if not line.strip():
            after_blank, hidden = True, []
            continue
        if "|" not in line:
            after_blank = False
            continue
        cells = line.split("|")
        if after_blank:
            # a header: remember which columns are personal; the header itself stays so the model knows the column exists
            hidden = [n for n, cell in enumerate(cells) if _PERSONAL_HEADER.search(cell.strip().lower())]
            after_blank = False
        elif hidden:
            for n in hidden:
                if n < len(cells) and cells[n].strip():
                    cells[n] = HIDDEN
            lines[i] = "|".join(cells)
    return "\n".join(lines)
