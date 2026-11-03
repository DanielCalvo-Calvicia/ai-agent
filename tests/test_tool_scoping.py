# T-05.13: the tools a step may use are those every level allows (profile, flow, step); a tool outside is neither shown to
# the model nor callable. The levels are plain data here; the real ones are the `tools` objects of the files.
import dataclasses
import os
from types import SimpleNamespace

import pytest

from application.engine.assemble import Agent, assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.flow_file import flow_from_file
from application.engine.pipeline import Pipeline
from application.engine.profile_runner import ProfileRunner
from application.engine.support.mcp_servers import describe_servers, server_names
from application.engine.support.metrics import SessionMetrics
from application.outbound.ports.mcp_ports import McpToolsPort, ScopedTools, ToolScope, scoped
from domain.value_objects.llm_request.tool import ToolDefinition
from flow_files import FLOWS
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.tools import resolve_tools
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
from test_flow_golden import SCENARIOS, ScriptedLLM

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DYN, AWS = "dynamics_microservice", "aws_microservice"
MCP_LIST = [{"name": DYN, "type": "streamable_http", "config": {"url": "http://x"}},
            {"name": AWS, "type": "sse", "config": {"url": "http://y"}}]


def tool(name):
    return ToolDefinition(name=name, description=f"the tool {name}", parameters={"type": "object", "properties": {}})


class Port(McpToolsPort):
    TOOLS = {DYN: ["customer_orders", "order_status", "shared"], AWS: ["count_emails", "shared"]}

    def list_tools(self, server_name):
        return [tool(name) for name in self.TOOLS.get(server_name, [])]


def shown(mcp_list, port):
    """What a planner is told: server -> tool names."""
    return {s["name"]: [t["name"] for t in s["tools"]] for s in describe_servers(mcp_list, port)}


# ===============================================
#  THE RULE
# ===============================================

class TestTheScope:
    def test_nothing_set_is_no_limit(self):
        assert ToolScope.of(None, None).unlimited and ToolScope.of().allows(DYN, "anything")

    def test_a_whole_server(self):
        scope = ToolScope.of({"servers": [DYN]})
        assert scope.allows(DYN, "customer_orders") and not scope.allows(AWS, "count_emails")

    def test_one_tool_written_as_server_dot_tool(self):
        scope = ToolScope.of({"tools": [f"{DYN}.customer_orders"]})
        assert scope.allows(DYN, "customer_orders") and not scope.allows(DYN, "order_status") and not scope.allows(AWS, "customer_orders")

    def test_a_bare_name_is_the_tool_of_whichever_server_has_it(self):
        scope = ToolScope.of({"tools": ["count_emails"]})
        assert scope.allows(AWS, "count_emails") and not scope.allows(AWS, "shared")

    def test_a_server_and_a_tool_of_another_server_add_up_inside_one_level(self):
        scope = ToolScope.of({"servers": [DYN], "tools": [f"{AWS}.count_emails"]})
        assert scope.allows(DYN, "order_status") and scope.allows(AWS, "count_emails") and not scope.allows(AWS, "shared")

    def test_an_empty_level_is_no_tool_at_all(self):
        scope = ToolScope.of({"servers": []})
        assert not scope.allows(DYN, "customer_orders") and not scope.may_use(DYN)

    def test_the_levels_are_intersected_and_the_narrowest_wins(self):
        profile, flow, step = {"servers": [DYN, AWS]}, {"servers": [DYN]}, {"tools": [f"{DYN}.order_status"]}
        scope = ToolScope.of(profile, flow, step)
        assert [scope.allows(DYN, t) for t in ("customer_orders", "order_status")] == [False, True]
        assert not scope.allows(AWS, "count_emails")

    def test_a_level_that_names_a_tool_the_level_above_does_not_allow_gets_nothing_extra(self):
        scope = ToolScope.of({"tools": [f"{DYN}.customer_orders"]}, {"tools": [f"{DYN}.order_status", f"{DYN}.customer_orders"]})
        assert scope.allows(DYN, "customer_orders") and not scope.allows(DYN, "order_status")


# ===============================================
#  WHAT THE MODEL IS SHOWN
# ===============================================

class TestWhatTheModelSees:
    def test_a_profile_limited_to_one_tool_cannot_see_another(self):
        servers, port = scoped(MCP_LIST, Port(), ToolScope.of({"tools": [f"{DYN}.customer_orders"]}))
        assert shown(servers, port) == {DYN: ["customer_orders"]}
        assert server_names(servers, port) == [DYN]

    def test_no_limit_gives_back_the_same_objects(self):
        port = Port()
        assert scoped(MCP_LIST, port, ToolScope.of(None)) == (MCP_LIST, port)

    def test_a_server_none_of_whose_tools_is_allowed_is_left_out(self):
        servers, port = scoped(MCP_LIST, Port(), ToolScope.of({"tools": ["count_emails"]}, {"servers": [DYN]}))
        assert shown(servers, port) == {} and server_names(servers, port) == []       # a server with no tool left is not shown

    def test_the_server_descriptors_carry_the_scope_for_the_adapter(self):
        scope = ToolScope.of({"servers": [AWS]})
        servers, _ = scoped(MCP_LIST, Port(), scope)
        assert [s["name"] for s in servers] == [AWS] and servers[0]["scope"] is scope

    def test_the_adapter_exposes_only_the_allowed_tools_of_a_server(self):
        seen = []

        class Executor(Port):
            def execute(self, name, kwargs, scope=None):
                seen.append((name, scope))
                return {"result": "ok", "is_error": False}

        scope = ToolScope.of({"tools": [f"{DYN}.customer_orders"]})
        servers, _ = scoped(MCP_LIST, Port(), scope)
        exposed = resolve_tools(SimpleNamespace(tool_executor=Executor()), servers)
        assert [t.name for t in exposed] == ["customer_orders"]
        exposed[0].handler(customer_no="C-1")
        assert seen == [("customer_orders", scope)]

    def test_an_unlimited_server_is_exposed_whole_and_run_the_old_way(self):
        called = []

        class Executor(Port):
            def execute(self, name, kwargs):                    # no `scope` argument: nothing limited
                called.append(name)
                return {"result": "ok", "is_error": False}

        exposed = resolve_tools(SimpleNamespace(tool_executor=Executor()), [MCP_LIST[0]])
        assert [t.name for t in exposed] == ["customer_orders", "order_status", "shared"]
        exposed[0].handler()
        assert called == ["customer_orders"]


# ===============================================
#  WHAT CAN BE CALLED
# ===============================================

class Catalog:
    async def server_of(self, tool_name):
        return next((server for server, names in Port.TOOLS.items() if tool_name in names), None)


class TestWhatCanBeCalled:
    def executor(self):
        return MCPToolExecutor(client_manager=None, catalog=Catalog())     # a call that went out would fail: there is no manager

    def test_a_call_outside_the_scope_is_refused_and_no_server_is_called(self):
        scope = ToolScope.of({"tools": [f"{DYN}.customer_orders"]})
        answer = self.executor().execute("order_status", {"customer_no": "C-1"}, scope=scope)
        assert answer["is_error"] and "not allowed" in answer["error"]

    def test_a_tool_of_another_server_is_refused_too(self):
        answer = self.executor().execute("count_emails", {}, scope=ToolScope.of({"servers": [DYN]}))
        assert answer["is_error"] and "not allowed" in answer["error"]

    def test_the_refusal_is_a_tool_call_record_with_no_try_and_no_argument(self):
        from application.outbound.ports.mcp_ports import watch_tool_failures
        with watch_tool_failures() as failures:
            self.executor().execute("order_status", {"customer_no": "SECRET-7"}, scope=ToolScope.of({"servers": [AWS]}))
        assert [c.to_dict() for c in failures.calls] == [{"tool": "order_status", "outcome": "not_found", "duration_ms": failures.calls[0].duration_ms, "attempts": 0}]
        assert "SECRET-7" not in repr(failures.calls)

    def test_a_tool_that_exists_nowhere_is_still_not_found(self):
        answer = self.executor().execute("nope", {}, scope=ToolScope.of({"servers": [DYN]}))
        assert answer["is_error"] and "not found" in answer["error"]


# ===============================================
#  THE LEVELS OF THE FILES
# ===============================================

def flow_with(tools=None, step_tools=None):
    steps = [{"step": "triage_specialist"}, {"step": "project_manager", **({"tools": step_tools} if step_tools else {})},
             {"step": "editor_in_chief"}]
    return flow_from_file("t", {"steps": steps, "result_from": "editor_in_chief", **({"tools": tools} if tools else {})})


def pipeline(flow, levels=(), overrides=None):
    return Pipeline(ScriptedLLM(), MCP_LIST, SessionMetrics(), Port(), flow=flow, tool_levels=levels, tool_overrides=overrides)


class TestTheLevelsOfTheFiles:
    def test_the_flow_file_and_the_step_of_the_flow_file_narrow_the_profile(self):
        built = pipeline(flow_with({"servers": [DYN]}, {"tools": [f"{DYN}.order_status"]}), levels=({"servers": [DYN, AWS]},))
        assert built.scope_of("project_manager").allows(DYN, "order_status") and not built.scope_of("project_manager").allows(DYN, "customer_orders")
        assert built.scope_of("editor_in_chief").allows(DYN, "customer_orders") and not built.scope_of("editor_in_chief").allows(AWS, "count_emails")

    def test_a_step_that_names_a_tool_the_profile_does_not_allow_gets_nothing_extra(self):
        built = pipeline(flow_with(step_tools={"tools": [f"{AWS}.count_emails"]}), levels=({"servers": [DYN]},))
        assert not built.scope_of("project_manager").allows(AWS, "count_emails")

    def test_the_override_of_a_step_in_the_profile_is_a_level_too(self):
        built = pipeline(flow_with(), levels=({"servers": [DYN]},), overrides={"project_manager": {"tools": [f"{DYN}.customer_orders"]}})
        assert built.scope_of("project_manager").allows(DYN, "customer_orders") and not built.scope_of("project_manager").allows(DYN, "order_status")
        assert built.scope_of("editor_in_chief").allows(DYN, "order_status")

    def test_the_flow_file_keeps_the_tools_of_its_steps(self):
        assert flow_with({"servers": [DYN]}, {"servers": [AWS]}).step_tools == {"project_manager": {"servers": [AWS]}}
        assert all(flow.tools is None and flow.step_tools == {} for flow in FLOWS.values())


# ===============================================
#  A WHOLE PROFILE
# ===============================================

@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    built.raise_on_errors()
    return built


def limited(agent, **tools):
    """The `special` profile with the given `tools` object."""
    profile = agent.profile("special")
    return Agent({"special": dataclasses.replace(profile, definition={**profile.definition, "tools": tools})}, {}, agent.flows, agent.step_defs, agent.step_prompts)


class TestAProfileLimitedToOneTool:
    def planner_input(self, agent, port):
        scenario = SCENARIOS["no_actions"]
        llm = ScriptedLLM(**scenario["llm"])
        ProfileRunner(llm, MCP_LIST, SessionMetrics(), port, agent).run("special", scenario["message"])
        return next(c["user_message"] for c in llm.calls if c["format"].startswith("project_manager"))

    def test_the_planner_is_shown_the_one_tool_and_nothing_else(self, agent):
        text = self.planner_input(limited(agent, tools=[f"{DYN}.customer_orders"]), Port())
        assert "customer_orders" in text and "order_status" not in text and "count_emails" not in text and AWS not in text

    def test_the_servers_of_the_profile_are_those_with_an_allowed_tool(self, agent):
        runner = ProfileRunner(ScriptedLLM(), MCP_LIST, SessionMetrics(), Port(), limited(agent, tools=[f"{DYN}.customer_orders"]))
        assert runner.servers_of("special") == [DYN]

    def test_without_a_limit_the_planner_is_shown_every_tool(self, agent):
        text = self.planner_input(agent, Port())
        assert all(name in text for name in ("customer_orders", "order_status", "count_emails"))

    def test_the_real_profiles_keep_their_servers(self, agent):
        runner = ProfileRunner(ScriptedLLM(), MCP_LIST, SessionMetrics(), Port(), agent)
        assert runner.servers_of("special") == [DYN, AWS] and runner.servers_of("default") == []
