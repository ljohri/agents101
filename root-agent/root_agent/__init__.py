"""Root planner agent package.

A standalone process that fronts the agent_stack runtime. It uses an LLM to
either pick an existing workflow (LLM-as-judge) or synthesize a new plan
(LLM-as-planner), enriches every request with Claude-style memory, and can run
guarded local CLI commands. All downstream agents are reached over A2A.
"""

__version__ = "0.1.0"
