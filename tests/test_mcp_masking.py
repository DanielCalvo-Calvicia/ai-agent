# T-01.9, finding e: personal columns of a tool answer are hidden before any model sees them.
import pytest

from infrastructure.outbound.mcp.masking import HIDDEN, mask_personal_columns, masking_enabled

META = "returned: 2\ntotal: 2\ncoverage: x\n\n"


def test_the_customer_name_column_of_an_order_list_is_hidden():
    text = META + "No.|Status|Amount|Sell-to Customer Name\nSO-1|Open|10|ACME\nSO-2|Open|20|BETA"
    assert mask_personal_columns(text) == META + f"No.|Status|Amount|Sell-to Customer Name\nSO-1|Open|10|{HIDDEN}\nSO-2|Open|20|{HIDDEN}"


def test_the_card_hides_name_and_search_name_and_keeps_the_rest():
    text = "returned: 1\n\nNo.|Name|Search Name|Currency Code|Blocked\nC-1|ACME|ACME INC|EUR|No"
    assert mask_personal_columns(text) == f"returned: 1\n\nNo.|Name|Search Name|Currency Code|Blocked\nC-1|{HIDDEN}|{HIDDEN}|EUR|No"


@pytest.mark.parametrize("header", ["E-Mail", "Email", "Phone No.", "Mobile Phone No.", "Fax No.", "Address", "City", "Post Code",
                                    "Contact", "VAT Registration No.", "IBAN", "Bill-to Name", "Ship-to Name"])
def test_other_personal_headers_are_hidden(header):
    assert mask_personal_columns(f"\nNo.|{header}\nC-1|secret") == f"\nNo.|{header}\nC-1|{HIDDEN}"


@pytest.mark.parametrize("header", ["No.", "Status", "Document Date", "Amount", "Currency Code", "External Document No.", "Description", "Item No."])
def test_codes_dates_amounts_and_states_are_kept(header):
    text = f"\nNo.|{header}\nC-1|keep"
    assert mask_personal_columns(text) == text


def test_an_empty_cell_stays_empty_and_a_short_row_does_not_break():
    text = "\nNo.|Name|Amount\nC-1||5\nC-2"
    assert mask_personal_columns(text) == text


def test_each_table_has_its_own_header():
    text = "\nNo.|Name\nC-1|ACME\n\nNo.|Status\nC-1|Open"
    assert mask_personal_columns(text) == f"\nNo.|Name\nC-1|{HIDDEN}\n\nNo.|Status\nC-1|Open"


def test_text_without_a_table_is_unchanged():
    for text in ("status: running\njob_id: job-1\nnext_offset: 0", "error (input): bad customer", ""):
        assert mask_personal_columns(text) == text


@pytest.mark.parametrize("value, enabled", [(None, True), ("1", True), ("0", False), ("false", False), ("off", False), ("no", False)])
def test_the_switch(monkeypatch, value, enabled):
    if value is None:
        monkeypatch.delenv("AI_AGENT_MASK_PERSONAL_DATA", raising=False)
    else:
        monkeypatch.setenv("AI_AGENT_MASK_PERSONAL_DATA", value)
    assert masking_enabled() is enabled
