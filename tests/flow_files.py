# The flows of the repository, built from flows/*.json the way the service builds them. The tests that used the Python flows
# (before T-05.12) take them from here: same names, same objects of the same kind.
import os

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from infrastructure.outbound.config.file_source import FileConfigSource

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

FLOWS = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT))).flows        # name -> Flow

IDENTIFICATION_FLOW = FLOWS["identification"]
CONVERSATION_FLOW = FLOWS["conversation"]
SPECIAL_FLOW = FLOWS["special"]
MOVEMENT_FLOW = FLOWS["movement"]
EXPRESSION_FLOW = FLOWS["expression"]
