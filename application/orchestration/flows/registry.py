# ===============================================
#  FLOW REGISTRY
#  The flows this service hosts, by name. The composition root gives every flow its own
#  session service and its own routes. A new agent = its file in flows/ + one line below.
# ===============================================

from typing import Dict, Iterator, List

from application.orchestration.engine.flow import Flow
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.orchestration.flows.motion_flow import MOTION_FLOW


class FlowRegistry:
    def __init__(self, flows: List[Flow]) -> None:
        self._flows: Dict[str, Flow] = {}
        for flow in flows:
            self.register(flow)

    def register(self, flow: Flow) -> None:
        if flow.name in self._flows:
            raise ValueError(f"flow {flow.name!r} is already registered")
        self._flows[flow.name] = flow

    def get(self, name: str) -> Flow:
        if name not in self._flows:
            raise KeyError(f"unknown flow: {name!r}. Flows: {', '.join(self._flows)}")
        return self._flows[name]

    def names(self) -> List[str]:
        return list(self._flows)

    def __iter__(self) -> Iterator[Flow]:
        return iter(self._flows.values())


FLOWS = FlowRegistry([CONVERSATION_FLOW, MOTION_FLOW])
