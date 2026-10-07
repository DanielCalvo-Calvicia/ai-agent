# ===============================================
#  FLOW REGISTRY
#  The flows this service hosts, by name: identification (classifies), conversation (plain reply),
#  special (plans and executes) and movement (arm movements). A new agent = its file in flows/ + one line below
#  (+ a line in router.py to say which domain reaches it).
# ===============================================

from typing import Dict, Iterator, List

from application.orchestration.engine.flow import Flow
from application.orchestration.flows.conversation import CONVERSATION_FLOW
from application.orchestration.flows.identification import IDENTIFICATION_FLOW
from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.special import SPECIAL_FLOW


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


FLOWS = FlowRegistry([IDENTIFICATION_FLOW, CONVERSATION_FLOW, SPECIAL_FLOW, MOVEMENT_FLOW])
