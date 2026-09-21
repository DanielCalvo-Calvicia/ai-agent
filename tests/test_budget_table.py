"""The multi-provider table and the monthly budget."""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.model_selection import STEP_NAMES
from budget_table import (DOC_PATH, MEASURED_PATH, WORKS_TEXT, budget_usd_per_message, combined, eur, load_budget,
                          markdown, measured_cost, profile_choice, read)
from cost_estimate import rows_for, total_row, usage
from model_table import blended, read_config

DATA = combined()
BUDGET = load_budget()
CONFIG = read_config()


def big_total(name):
    b = BUDGET["big_plan"]
    return total_row(rows_for(profile_choice(DATA, CONFIG, name), usage(b["actions"], b["subactions"], b["tools"])))["thinking"]


class TestTheModelList:
    def test_ids_are_unique(self):
        ids = [m["id"] for m in DATA["models"]]
        assert len(ids) == len(set(ids))

    def test_sorted_from_cheapest_to_dearest(self):
        costs = [blended(m) for m in DATA["models"]]
        assert costs == sorted(costs)

    def test_every_model_rates_every_step_with_a_known_level(self):
        for m in DATA["models"]:
            assert set(m["ratings"]) == set(STEP_NAMES), m["id"]
            assert all(r[0] in DATA["_levels"] for r in m["ratings"].values()), m["id"]

    def test_works_today_is_a_known_value(self):
        assert {m["works_today"] for m in DATA["models"]} <= set(WORKS_TEXT)

    def test_more_than_one_provider(self):
        assert {m["provider"] for m in DATA["models"]} >= {"google", "openai", "anthropic", "mistral", "groq", "deepseek"}


class TestTheBudget:
    def test_50_euro_for_1000_messages(self):
        assert BUDGET["eur_per_month"] == 50 and BUDGET["messages_per_month"] == 1000
        assert budget_usd_per_message(BUDGET) == pytest.approx(50 * BUDGET["usd_per_eur"] / 1000)

    def test_eur_conversion_round_trips(self):
        assert eur(budget_usd_per_message(BUDGET) * 1000, BUDGET) == pytest.approx(50)

    def test_the_budget_profiles_fit_with_the_worst_plan(self):
        limit = budget_usd_per_message(BUDGET)
        for name in ("budget", "budget50", "budget50_groq"):
            assert big_total(name) <= limit, name

    def test_the_default_profile_does_not_fit(self):
        assert big_total("proven") > budget_usd_per_message(BUDGET)

    def test_a_small_plan_costs_less_than_a_big_one(self):
        b, s = BUDGET["big_plan"], BUDGET["small_plan"]
        choice = profile_choice(DATA, CONFIG, "budget50")
        small = total_row(rows_for(choice, usage(s["actions"], s["subactions"], s["tools"])))["thinking"]
        assert small < big_total("budget50")

    def test_measured_cost_uses_sent_answered_and_thinking(self):
        prices = {"m": {"input": 1.0, "output": 2.0}}
        run = {"id": "m", "sent": 1_000_000, "answered": 500_000, "thinking": 500_000}
        assert measured_cost(run, prices) == pytest.approx(3.0)

    def test_every_measured_run_has_a_price(self):
        ids = {m["id"] for m in DATA["models"]}
        assert all(r["id"] in ids for r in read(MEASURED_PATH)["runs"])


class TestTheDocument:
    def test_it_is_up_to_date(self):
        assert open(DOC_PATH, encoding="utf-8").read() == markdown(DATA, CONFIG, BUDGET, read(MEASURED_PATH)), \
            "run: windows\\Scripts\\python.exe tests\\manual\\show_models.py --budget"

    def test_every_step_has_a_table(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        assert all(f"### {step}\n" in text for step in STEP_NAMES)
