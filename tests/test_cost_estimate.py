"""The estimate of what one message costs, per step, for a plan of a given size."""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.model_selection import STEP_NAMES
from cost_estimate import (ACTION_REPR, ANSWER_TOKENS, PARENT_ANSWER_TOKENS, PROMPT, THINKING, THINKING_FACTOR,
                           choice_single, choice_strongest, markdown, price, rows_for, total_row, usage)
from model_table import load_models

DOC = os.path.join(PROJECT_ROOT, "docs", "models", "cost_of_a_full_plan.md")


def by_step(usages):
    return {u.step: u for u in usages}


class TestTheSizeOfThePlan:
    def test_five_actions_of_five_subactions_are_thirty_actions(self):
        u = by_step(usage(5, 5, 5))
        assert u["cognitive_worker"].calls == 25            # 30 actions, 5 of them use a tool
        assert u["mcp_operator"].calls == 5 and u["data_engineer"].calls == 5
        assert sum(x.calls for x in u.values()) == 40       # 1 + 1 + 1 + 25 + 5 + 5 + 1 + 1

    def test_without_tools_the_tool_steps_cost_nothing(self):
        u = by_step(usage(5, 5, 0))
        assert u["cognitive_worker"].calls == 30
        assert u["mcp_operator"].calls == u["data_engineer"].calls == 0 and u["mcp_operator"].input_tokens == 0

    def test_tools_run_in_subactions_only(self):
        u = by_step(usage(2, 1, 99))                        # 4 actions: 2 parents, 2 leaves
        assert u["mcp_operator"].calls == 2 and u["cognitive_worker"].calls == 2

    def test_the_questions_to_the_user_are_not_part_of_a_plan(self):
        u = by_step(usage())
        assert u["answer_checker"].calls == 0 and u["user_clarification"].calls == 0

    def test_a_bigger_plan_costs_more_tokens_in_every_growing_step(self):
        small, big = by_step(usage(2, 2, 0)), by_step(usage(5, 5, 0))
        for step in ("project_manager", "safety_quality_gatekeeper", "cognitive_worker", "draft_writer"):
            assert big[step].input_tokens + big[step].output_tokens > small[step].input_tokens + small[step].output_tokens

    def test_the_gate_and_the_draft_read_every_action(self):
        u = by_step(usage(5, 5, 5))
        assert u["safety_quality_gatekeeper"].input_tokens == PROMPT["safety_quality_gatekeeper"] + ACTION_REPR * 30
        assert u["draft_writer"].input_tokens == PROMPT["draft_writer"] + ACTION_REPR * 30 + 30 * ANSWER_TOKENS

    def test_a_parent_reads_the_outputs_of_its_subactions(self):
        u = by_step(usage(1, 5, 0))                         # 1 parent, 5 leaves
        expected_in = 5 * (PROMPT["cognitive_worker"] + ANSWER_TOKENS) + (PROMPT["cognitive_worker"] + 5 * ANSWER_TOKENS)
        assert u["cognitive_worker"].input_tokens == expected_in
        assert u["cognitive_worker"].output_tokens == 5 * ANSWER_TOKENS + PARENT_ANSWER_TOKENS


class TestThePrice:
    MODEL = {"id": "gemini-2.5-flash", "input": 0.30, "output": 2.50, "price_note": ""}

    def test_visible_cost(self):
        u = by_step(usage())["cognitive_worker"]
        expected = (u.input_tokens * 0.30 + u.output_tokens * 2.50) / 1e6
        assert price(self.MODEL, u, with_thinking=False) == pytest.approx(expected)

    def test_thinking_adds_output_tokens_per_call(self):
        u = by_step(usage())["cognitive_worker"]
        extra = THINKING["cognitive_worker"] * THINKING_FACTOR["gemini-2.5-flash"] * u.calls * 2.50 / 1e6
        assert price(self.MODEL, u, True) - price(self.MODEL, u, False) == pytest.approx(extra)

    def test_a_model_that_does_not_think_adds_nothing(self):
        lite = {"id": "gemini-2.5-flash-lite", "input": 0.10, "output": 0.40, "price_note": ""}
        u = by_step(usage())["project_manager"]
        assert price(lite, u, True) == price(lite, u, False)

    def test_only_the_models_with_a_price_change_double_in_2027(self):
        u = by_step(usage())["cognitive_worker"]
        promo = {"id": "gemini-3.8-flash", "input": 0.75, "output": 3.75,
                 "price_note": "until 2026-12-31. From 2027-01-01: 1.50 in"}
        assert price(promo, u, False, True) == pytest.approx(2 * price(promo, u, False, False))
        assert price(self.MODEL, u, False, True) == price(self.MODEL, u, False, False)

    def test_a_step_with_no_calls_costs_nothing(self):
        assert price(self.MODEL, by_step(usage())["answer_checker"], True) == 0


class TestTheScenarios:
    data = load_models()

    def test_every_step_and_model_has_a_thinking_guess(self):
        assert set(THINKING) == set(STEP_NAMES)
        assert {m["id"] for m in self.data["models"]} <= set(THINKING_FACTOR)

    def test_the_strongest_choice_is_the_last_best_model_of_each_step(self):
        choice = choice_strongest(self.data)
        assert choice["project_manager"]["id"] == "gemini-3.1-pro-preview"
        assert choice["cognitive_worker"]["id"] == "gemini-3.8-flash"
        assert choice["data_engineer"]["id"] == "gemini-3.1-flash-lite"

    def test_the_strongest_model_everywhere_costs_more_than_the_strongest_per_step(self):
        usages = usage()
        strongest = total_row(rows_for(choice_strongest(self.data), usages))
        pro = total_row(rows_for(choice_single(self.data, "gemini-3.1-pro-preview"), usages))
        flash = total_row(rows_for(choice_single(self.data, "gemini-2.5-flash"), usages))
        assert flash["visible"] < strongest["visible"] < pro["visible"]
        assert all(t["thinking"] >= t["visible"] for t in (strongest, pro, flash))

    def test_the_total_is_the_sum_of_the_steps(self):
        rows = rows_for(choice_strongest(self.data), usage())
        assert total_row(rows)["visible"] == pytest.approx(sum(r["visible"] for r in rows))

    def test_the_document_is_up_to_date(self):
        assert open(DOC, encoding="utf-8").read() == markdown(self.data), \
            "run: windows\\Scripts\\python.exe tests\\manual\\estimate_cost.py --write"

    def test_the_document_shows_every_step_in_every_scenario(self):
        text = open(DOC, encoding="utf-8").read()
        for title in ("## A. The strongest model of each step", "## B. `gemini-3.1-pro-preview` on every step",
                      "## C. For comparison"):
            section = text.split(title)[1].split("\n## ")[0]
            assert all(f"| {step} |" in section for step in STEP_NAMES), title
            assert "**Total for one message**" in section and "1,000 messages" in section
