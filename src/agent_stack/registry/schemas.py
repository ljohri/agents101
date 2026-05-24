"""Pydantic schemas for the three registry files.

Authoritative contract for:
- agents.yaml         (see docs/architecture/01-config-and-registries.md sec 3.1)
- workflows.yaml      (see docs/architecture/03-workflows.md)
- mcp_servers.yaml    (see docs/architecture/04-mcp-integration.md sec 3.1)

Schema versions are validated by registry.config.load_all; unknown versions
fail fast per the migration policy in 01-config-and-registries.md sec 7.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CURRENT_AGENTS_VERSION = 1
CURRENT_WORKFLOWS_VERSION = 1
CURRENT_MCP_SERVERS_VERSION = 1


class StrictModel(BaseModel):
    """Reject unknown keys so typos in YAML fail loudly."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# agents.yaml
# ---------------------------------------------------------------------------


class Owner(StrictModel):
    organization: str | None = None
    contact: str | None = None


class RuntimeBlock(StrictModel):
    default_host: str = "127.0.0.1"
    default_port: int = 8086
    default_base_url: str = "http://127.0.0.1:8086"
    default_a2a_prefix: str = "/a2a"
    generated_card_paths: list[str] = Field(
        default_factory=lambda: [".well-known/agent-card.json", ".well-known/agent.json"]
    )


class ServerBlock(StrictModel):
    base_url: str
    a2a_endpoint: str
    card_paths: list[str] | None = None


class AuthBlock(StrictModel):
    mode: Literal["local_bearer", "none"]
    env_token_name: str | None = None
    allow_none_for_dev: bool = False


class AgentCapabilities(StrictModel):
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False
    file_upload: bool = False
    artifacts: bool = False


class Skill(StrictModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    input_modes: list[str] = Field(default_factory=list)
    output_modes: list[str] = Field(default_factory=list)


class BehaviorBlock(StrictModel):
    instruction_file: str | None = None
    generated_root_instruction_file: str | None = None
    rules: list[str] = Field(default_factory=list)


class FilesystemPolicy(StrictModel):
    allowed_roots: list[str] = Field(default_factory=list)
    deny_patterns: list[str] = Field(default_factory=list)


class NetworkPolicy(StrictModel):
    allow_domains: list[str] = Field(default_factory=list)


class PolicyBlock(StrictModel):
    filesystem: FilesystemPolicy | None = None
    network: NetworkPolicy | None = None


class McpEmbeddedServer(StrictModel):
    """Per-agent MCP server hint; the authoritative registry lives in
    mcp_servers.yaml. This is kept for legacy declarations only.
    """

    name: str
    command: str | None = None
    args: list[str] = Field(default_factory=list)


class McpEmbeddedBlock(StrictModel):
    enabled: bool = False
    servers: list[McpEmbeddedServer] = Field(default_factory=list)


class AgentRuntimeLocal(StrictModel):
    kind: Literal["local"]
    module: str
    factory: str
    state_schema: str | None = None
    openclaw_agent_id: str | None = None
    sandbox: str | None = None
    fallback_graph: dict[str, Any] | None = None
    graph: dict[str, Any] | None = None


class RemoteAuth(StrictModel):
    mode: Literal["bearer", "none"]
    token_env: str | None = None
    propagate_inbound: bool = False


class RetrySpec(StrictModel):
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    jitter: bool = True


class CircuitBreakerSpec(StrictModel):
    failure_threshold: int = 5
    reset_seconds: float = 30.0


class ResilienceSpec(StrictModel):
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 30.0
    retry: RetrySpec = Field(default_factory=RetrySpec)
    circuit_breaker: CircuitBreakerSpec = Field(default_factory=CircuitBreakerSpec)


class RemoteSpec(StrictModel):
    base_url: str
    a2a_endpoint: str
    auth: RemoteAuth
    resilience: ResilienceSpec = Field(default_factory=ResilienceSpec)


class AgentRuntimeRemote(StrictModel):
    kind: Literal["remote"]
    remote: RemoteSpec


AgentRuntime = Annotated[
    AgentRuntimeLocal | AgentRuntimeRemote, Field(discriminator="kind")
]


class Agent(StrictModel):
    id: str
    name: str
    display_name: str | None = None
    version: str
    description: str
    owner: Owner | None = None
    runtime: AgentRuntime
    server: ServerBlock | None = None
    auth: AuthBlock | None = None
    capabilities: AgentCapabilities | None = None
    skills: list[Skill]
    behavior: BehaviorBlock | None = None
    mcp: McpEmbeddedBlock | None = None
    policy: PolicyBlock | None = None


class AgentsYaml(StrictModel):
    schema_version: Literal[1]
    runtime: RuntimeBlock
    agents: dict[str, Agent]

    @model_validator(mode="after")
    def _unique_endpoints(self) -> AgentsYaml:
        seen: dict[str, str] = {}
        for agent_id, agent in self.agents.items():
            if agent_id != agent.id:
                raise ValueError(
                    f"agents.{agent_id}.id must equal the map key (got {agent.id!r})"
                )
            if agent.server is not None:
                ep = agent.server.a2a_endpoint
                if ep in seen:
                    raise ValueError(
                        f"a2a_endpoint {ep!r} collides between {seen[ep]!r} and {agent_id!r}"
                    )
                seen[ep] = agent_id
        return self


# ---------------------------------------------------------------------------
# mcp_servers.yaml
# ---------------------------------------------------------------------------


class McpHealth(StrictModel):
    ready_timeout_seconds: float = 10.0
    probe: str = "tools/list"


class McpFilter(StrictModel):
    allow_tools: list[str] = Field(default_factory=list)
    deny_tools: list[str] = Field(default_factory=list)


class McpServerPolicy(StrictModel):
    max_concurrent_calls: int = 4
    per_call_timeout_seconds: float = 30.0
    retry: dict[str, Any] = Field(
        default_factory=lambda: {"max_attempts": 2, "backoff_seconds": 1.5}
    )


class McpServer(StrictModel):
    id: str
    transport: Literal["stdio", "http", "sse"]
    # stdio
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    # http / sse
    url: str | None = None
    headers_env: dict[str, str] = Field(default_factory=dict)
    # all transports
    env_passthrough: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    autostart: bool = True
    health: McpHealth = Field(default_factory=McpHealth)
    capabilities_filter: McpFilter = Field(default_factory=McpFilter)
    policy: McpServerPolicy = Field(default_factory=McpServerPolicy)

    @model_validator(mode="after")
    def _transport_fields(self) -> McpServer:
        if self.transport == "stdio":
            if not self.command:
                raise ValueError(f"mcp server {self.id!r}: stdio transport requires 'command'")
            if self.url:
                raise ValueError(f"mcp server {self.id!r}: stdio transport must not set 'url'")
        else:
            if not self.url:
                raise ValueError(
                    f"mcp server {self.id!r}: {self.transport} transport requires 'url'"
                )
            if self.command or self.args:
                raise ValueError(
                    f"mcp server {self.id!r}: non-stdio transport must not set 'command'/'args'"
                )
        return self


class McpServersYaml(StrictModel):
    schema_version: Literal[1]
    servers: dict[str, McpServer]

    @model_validator(mode="after")
    def _id_matches_key(self) -> McpServersYaml:
        for key, server in self.servers.items():
            if key != server.id:
                raise ValueError(
                    f"mcp_servers.{key}.id must equal the map key (got {server.id!r})"
                )
        return self


# ---------------------------------------------------------------------------
# workflows.yaml
# ---------------------------------------------------------------------------


class WorkflowInputSpec(StrictModel):
    type: Literal["string", "integer", "number", "boolean", "object", "array", "enum"]
    required: bool = False
    default: Any | None = None
    enum: list[Any] | None = None
    items: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None


class ExposedSkill(StrictModel):
    id: str
    tags: list[str] = Field(default_factory=list)
    input_modes: list[str] = Field(default_factory=list)
    output_modes: list[str] = Field(default_factory=list)


class StepRetry(StrictModel):
    max_attempts: int = 1
    backoff_seconds: float = 0.0
    on: list[str] = Field(
        default_factory=lambda: [
            "capability.timeout",
            "capability.unavailable",
            "capability.upstream_error",
        ]
    )


class StepOnError(StrictModel):
    action: Literal["fail", "continue", "goto"] = "fail"
    goto: str | None = None
    capture_as: str | None = None

    @model_validator(mode="after")
    def _goto_required(self) -> StepOnError:
        if self.action == "goto" and not self.goto:
            raise ValueError("on_error.action=goto requires 'goto' target step id")
        return self


class _StepCommon(StrictModel):
    """Fields shared by every step kind. Concrete kinds inherit from this."""

    id: str
    description: str | None = None
    when: str | None = None
    timeout_seconds: float | None = None
    retry: StepRetry | None = None
    on_error: StepOnError | None = None
    output: str | None = None


class StepCall(_StepCommon):
    call: str
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    idempotency_key: str | None = None
    stream: bool = False

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StepAssign(_StepCommon):
    type: Literal["assign"]
    values: dict[str, Any]


class BranchCase(StrictModel):
    when: str
    goto: str


class StepBranch(_StepCommon):
    type: Literal["branch"]
    cases: list[BranchCase]
    default: str | None = None


class StepParallel(_StepCommon):
    """Either a fixed-fanout `branches` block OR a `for_each` over a collection."""

    type: Literal["parallel"]
    branches: list[dict[str, Any]] | None = None
    for_each: str | None = None
    as_: str | None = Field(default=None, alias="as")
    max_concurrency: int | None = None
    call: str | None = None
    with_: dict[str, Any] | None = Field(default=None, alias="with")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _exclusive(self) -> StepParallel:
        has_branches = self.branches is not None
        has_for_each = self.for_each is not None
        if has_branches == has_for_each:
            raise ValueError(
                f"parallel step {self.id!r}: provide exactly one of 'branches' or 'for_each'"
            )
        if has_for_each and not self.as_:
            raise ValueError(f"parallel step {self.id!r}: for_each requires 'as' binding")
        if has_for_each and not self.call:
            raise ValueError(f"parallel step {self.id!r}: for_each requires 'call'")
        return self


class StepHumanApproval(_StepCommon):
    type: Literal["human_approval"]
    message: str | None = None
    approve_action: str | None = None
    deny_action: str | None = None


class StepEmitArtifact(_StepCommon):
    type: Literal["emit_artifact"]
    path: str
    mime_type: str | None = None
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# Discriminator: kinds other than `call` set `type`. `call` is distinguished by
# the presence of the `call` key. We model the union as `Annotated[..., Field()]`
# without a discriminator and resolve manually below.
Step = (
    StepCall
    | StepAssign
    | StepBranch
    | StepParallel
    | StepHumanApproval
    | StepEmitArtifact
)


def _parse_step(raw: dict[str, Any]) -> Step:
    """Resolve a raw step dict to the right subclass."""
    if "type" in raw:
        kind = raw["type"]
        cls_by_kind = {
            "assign": StepAssign,
            "branch": StepBranch,
            "parallel": StepParallel,
            "human_approval": StepHumanApproval,
            "emit_artifact": StepEmitArtifact,
        }
        cls = cls_by_kind.get(kind)
        if cls is None:
            raise ValueError(f"unknown step type {kind!r}")
        return cls.model_validate(raw)
    if "call" in raw:
        return StepCall.model_validate(raw)
    raise ValueError(
        f"step {raw.get('id', '<?>')}: must have either 'call' or 'type'"
    )


class Workflow(StrictModel):
    version: str
    name: str
    description: str | None = None
    exposed_as_skill: ExposedSkill | None = None
    inputs: dict[str, WorkflowInputSpec] = Field(default_factory=dict)
    steps: list[Step]
    output: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_steps(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        steps = data.get("steps")
        if isinstance(steps, list):
            data["steps"] = [
                _parse_step(s) if isinstance(s, dict) else s for s in steps
            ]
        return data

    @model_validator(mode="after")
    def _unique_step_ids(self) -> Workflow:
        seen: set[str] = set()
        for s in self.steps:
            if s.id in seen:
                raise ValueError(f"duplicate step id {s.id!r}")
            seen.add(s.id)
        return self


class WorkflowsYaml(StrictModel):
    schema_version: Literal[1]
    workflows: dict[str, Workflow]
