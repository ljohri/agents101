"""Global command registry: how to do a task with local CLI utilities.

Recipes (YAML) describe a task, the binaries it needs, typed params, and an
argv template. Each available recipe is exposed as a guarded ``command.<name>``
capability the planner can use. Execution never goes through a shell: args are
passed as an argv array built from validated params.
"""

from root_agent.commands.exec import CommandExecutor, CommandResult
from root_agent.commands.registry import CommandRegistry
from root_agent.commands.schema import CommandParam, CommandSpec

__all__ = ["CommandExecutor", "CommandResult", "CommandRegistry", "CommandParam", "CommandSpec"]
