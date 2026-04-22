"""Digital Twin module for bmad-assist.

The Digital Twin provides two capabilities:
- Reflect: Post-execution review of LLM output, detecting drift and producing wiki updates
- Guide: Pre-execution compass generation from wiki experience knowledge

Twin is NOT an agent with tools — each operation is a single LLM call
→ parse YAML → code executes file I/O.
"""

from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord, build_execution_record, format_self_audit
from bmad_assist.twin.twin import Twin, TwinResult

__all__ = [
    "Twin",
    "TwinResult",
    "TwinProviderConfig",
    "ExecutionRecord",
    "build_execution_record",
    "format_self_audit",
]
