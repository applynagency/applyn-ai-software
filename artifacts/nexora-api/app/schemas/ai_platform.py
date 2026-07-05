"""Pydantic schemas for the AI Platform API (Sprint 61D)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# --- generation / gateway ---------------------------------------------------


class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system: str | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = Field(default=1024, ge=1, le=32000)
    feature: str = "api"


class CompletionResponse(BaseModel):
    text: str
    provider: str
    model: str
    mode: str
    usage: dict
    cost_usd: float
    cached: bool
    latency_ms: float


# --- providers / routing ----------------------------------------------------


class ProviderInfo(BaseModel):
    name: str
    configured: bool
    default_model: str


class ProvidersResponse(BaseModel):
    items: list[ProviderInfo]
    total: int


class RoutingConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    routing_policy: str
    enabled_providers: list | None = None
    preferred_models: list | None = None
    default_temperature: float
    default_max_tokens: int
    cache_enabled: bool


class RoutingConfigUpdate(BaseModel):
    routing_policy: str | None = None
    enabled_providers: list[str] | None = None
    preferred_models: list[list[str]] | None = None
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    cache_enabled: bool | None = None


# --- prompts ----------------------------------------------------------------


class PromptCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    template: str = Field(min_length=1)
    variables: list[str] | None = None
    description: str | None = None
    organization_scope: bool = True  # True => org override, False => global (superuser)


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str | None
    key: str
    version: int
    template: str
    variables: list | None
    description: str | None
    is_active: bool


class PromptListResponse(BaseModel):
    items: list[PromptResponse]
    total: int


class PromptRenderRequest(BaseModel):
    variables: dict = Field(default_factory=dict)


class PromptRollbackRequest(BaseModel):
    version: int = Field(ge=1)


# --- tools ------------------------------------------------------------------


class ToolSpecResponse(BaseModel):
    name: str
    kind: str
    description: str
    parameters: dict
    requires_approval: bool


class ToolExecuteRequest(BaseModel):
    args: dict = Field(default_factory=dict)
    approved: bool = False


# --- agents -----------------------------------------------------------------


class AgentStartRequest(BaseModel):
    agent_key: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1)
    steps: list[dict] | None = None


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_key: str
    goal: str
    status: str
    current_step: int
    plan: list | None
    checkpoints: list | None
    result: dict | None
    error: str | None
    pending_approval: dict | None
    tokens_used: int
    cost_usd: float


# --- memory -----------------------------------------------------------------


class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=1)
    scope: str = "semantic"
    namespace: str = "default"
    importance: float = 0.5
    metadata: dict | None = None


class MemoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope: str
    namespace: str
    content: str
    importance: float


class MemoryRecallRequest(BaseModel):
    query: str = Field(min_length=1)
    scope: str | None = None
    namespace: str | None = None
    top_k: int | None = None


# --- mcp --------------------------------------------------------------------


class MCPServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=500)
    transport: str = "http"
    auth_token: str | None = None


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    url: str
    transport: str
    is_active: bool
    discovered_tools: list | None


# --- evaluation / cost ------------------------------------------------------


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    feature: str
    provider: str | None
    model: str | None
    hallucination_risk: float
    grounding_score: float
    answer_quality: float
    tool_success: float
    latency_ms: float
    tokens_used: int
    cost_usd: float
    passed: bool


# --- playground -------------------------------------------------------------


class PlaygroundPromptRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system: str | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.2


class PlaygroundModelsRequest(BaseModel):
    prompt: str = Field(min_length=1)
    models: list[dict]
    system: str | None = None
    temperature: float = 0.2


class PlaygroundTempsRequest(BaseModel):
    prompt: str = Field(min_length=1)
    temperatures: list[float]
    provider: str | None = None
    model: str | None = None
    system: str | None = None


class PlaygroundProvidersRequest(BaseModel):
    prompt: str = Field(min_length=1)
    providers: list[str]
    system: str | None = None
    temperature: float = 0.2
