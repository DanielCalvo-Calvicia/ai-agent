# Stray model markup (a closing parameter tag seen once on Claude, T-01.9) must never reach the reply, which is spoken aloud.
# The tags are built from pieces so that this file holds no literal markup.
import pytest

from application.orchestration.state.flow_state import FlowState, strip_markup
from domain.value_objects.llm_response.user_goal.user_goal import create_user_goal

OPEN, CLOSE = "<", "</"
END_PARAMETER = CLOSE + "parameter>"
INVOKE = OPEN + 'invoke name="count_stock">'
NAMESPACED = CLOSE + "antml:parameter>"


@pytest.mark.parametrize("text, clean", [
    ("There are 17 orders." + END_PARAMETER, "There are 17 orders."),
    (END_PARAMETER + "There are 17 orders.", "There are 17 orders."),
    ("Done." + INVOKE, "Done."),
    ("Two  " + NAMESPACED + "  words", "Two words"),
    ("Plain text stays.", "Plain text stays."),
    ("Is 3 < 5 and 7 > 4? Yes.", "Is 3 < 5 and 7 > 4? Yes."),
    ("I <3 clear answers.", "I <3 clear answers."),
    ("", ""),
])
def test_strip_markup(text, clean):
    assert strip_markup(text) == clean


def test_the_final_text_of_a_flow_has_no_stray_markup():
    state = FlowState(message="hi")
    state.user_goal = create_user_goal("s", "Seventeen orders." + END_PARAMETER)
    assert state.final_text() == "Seventeen orders."


def test_the_final_text_is_empty_without_a_goal():
    assert FlowState(message="hi").final_text() == ""
