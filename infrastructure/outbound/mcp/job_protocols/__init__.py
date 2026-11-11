"""The job protocols that are built in: importing this package registers them (job_protocol.py does it the first time a name is asked)."""

from infrastructure.outbound.mcp.job_protocol import register_protocol
from infrastructure.outbound.mcp.job_protocols.dynamics_pending import DynamicsPending
from infrastructure.outbound.mcp.job_protocols.dynamics_v1 import DynamicsV1

for _protocol in (DynamicsPending(), DynamicsV1()):
    register_protocol(_protocol)
