# ===============================================
#  PROMPT OVERRIDES
#  What a profile may do to the prompt of one step (`overrides.<step>.prompt_replace` / `prompt_append`, PR-005 sections 3.4 and 5):
#  replace the step's prompt or add text after it. The text comes from a file of the repository or is written in the profile; it is
#  never built from a request. The answer schema is the step's and a profile cannot change it, so a replacement never
#  changes the format the answer is read in. The generic rules, the capabilities and the date stay in front of every prompt.
# ===============================================

from dataclasses import dataclass
from typing import Optional

SOURCE_KEYS = ("file", "text")


@dataclass(frozen=True)
class PromptOverride:
    replace: Optional[str] = None       # the text that takes the place of the step's prompt file
    append: Optional[str] = None        # the text that goes after the step's prompt

    def apply(self, step_prompt: Optional[str]) -> Optional[str]:
        """The step's part of the system prompt, with the override applied (replace first, then append)."""
        text = self.replace if self.replace is not None else step_prompt
        if self.append:
            text = f"{text}\n\n{self.append}" if text else self.append
        return text
