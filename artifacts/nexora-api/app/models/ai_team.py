"""Sprint 37A — Custom AI Teams (Customer AI Workforce).

Additive, customer-facing models that let an organization define its own AI
Teams and the AI Agents that belong to them. These are **configuration only**
(no execution) and are completely independent of the internal APPYLN software
generation pipeline (Product Owner / Business Analyst / Architect / Developer /
QA / DevOps / Deployment / Approval / Lifecycle), which is left untouched.

Note: the internal agent-builder feature already owns the ``AIAgent`` class and
the ``ai_agents`` table, so the customer-facing agent here is named
``AITeamAgent`` (table ``ai_team_agents``) to remain strictly additive.
"""

import enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class AITeamStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AITeamAgentRunStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AITeamRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AITeamDocumentStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class AITeamWorkflowRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AITeamWorkflowApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AITeamWorkflowExecutionSource(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class AITeamWorkflowScheduleType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM_CRON = "CUSTOM_CRON"


class AITeamAgentMemoryType(str, enum.Enum):
    """Sprint 39A — categories of persistent agent memory."""

    MEMORY_DECISION = "MEMORY_DECISION"
    MEMORY_LESSON = "MEMORY_LESSON"
    MEMORY_CONVERSATION = "MEMORY_CONVERSATION"
    MEMORY_PROJECT_CONTEXT = "MEMORY_PROJECT_CONTEXT"


class AITeamToolProvider(str, enum.Enum):
    """Sprint 39B — supported read-only tool providers."""

    KUBERNETES = "KUBERNETES"
    AZURE = "AZURE"
    AWS = "AWS"
    GITHUB = "GITHUB"
    JIRA = "JIRA"
    POSTGRESQL = "POSTGRESQL"
    PROMETHEUS = "PROMETHEUS"
    GRAFANA = "GRAFANA"
    DATADOG = "DATADOG"
    SLACK = "SLACK"


class AITeamToolRunStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DENIED = "DENIED"


class AITeam(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_teams"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AITeamStatus] = mapped_column(
        SAEnum(AITeamStatus, name="aiteamstatus"),
        default=AITeamStatus.ACTIVE,
        nullable=False,
    )
    # Sprint 54B.1 — the organization's default team used when an incident
    # investigation is started without an explicit team_id. Auto-provisioned
    # during onboarding completion ("SRE Team").
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization")  # noqa: F821
    agents: Mapped[list["AITeamAgent"]] = relationship(
        "AITeamAgent",
        back_populates="team",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AITeamAgent.created_at",
    )


class AITeamAgent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_team_agents"

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised from the parent team so tenant scoping/queries never require a
    # join and a tampered team_id cannot cross organizations.
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-5")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    team: Mapped["AITeam"] = relationship("AITeam", back_populates="agents")
    runs: Mapped[list["AITeamAgentRun"]] = relationship(
        "AITeamAgentRun",
        back_populates="agent",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AITeamAgentRun.created_at.desc()",
    )


class AITeamAgentRun(Base, UUIDMixin, TimestampMixin):
    """Sprint 37B — a single, synchronous execution of one Team Agent.

    Stores the customer prompt, the produced response, status, and timing.
    No collaboration / memory / orchestration — single-agent execution only.
    """

    __tablename__ = "ai_team_agent_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AITeamAgentRunStatus] = mapped_column(
        String(20), nullable=False, default=AITeamAgentRunStatus.COMPLETED
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["AITeamAgent"] = relationship("AITeamAgent", back_populates="runs")


class AITeamRun(Base, UUIDMixin, TimestampMixin):
    """Sprint 37C — one orchestrated multi-agent collaboration over a team.

    All active agents execute sequentially, each receiving the original prompt
    plus the outputs of all prior agents. This is orchestrated collaboration
    only: no autonomy, no memory, no team chat, no continuous execution.
    """

    __tablename__ = "ai_team_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AITeamRunStatus] = mapped_column(
        String(20), nullable=False, default=AITeamRunStatus.RUNNING
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["AITeamRunStep"]] = relationship(
        "AITeamRunStep",
        back_populates="run",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AITeamRunStep.step_order",
    )


class AITeamRunStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_team_run_steps"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL (not CASCADE) so collaboration history survives agent deletion;
    # agent_name is a denormalized snapshot for display.
    agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AITeamAgentRunStatus] = mapped_column(
        String(20), nullable=False, default=AITeamAgentRunStatus.COMPLETED
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["AITeamRun"] = relationship("AITeamRun", back_populates="steps")


class AITeamDocument(Base, UUIDMixin, TimestampMixin):
    """Sprint 37D — a customer document attached to a team's knowledge base.

    Documents are chunked + embedded so agents can ground their answers in the
    customer's own content (RAG). This is retrieval only: no long-term memory,
    no autonomous learning, no external browsing.
    """

    __tablename__ = "ai_team_documents"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[AITeamDocumentStatus] = mapped_column(
        String(20), nullable=False, default=AITeamDocumentStatus.PROCESSING
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunks: Mapped[list["AITeamDocumentChunk"]] = relationship(
        "AITeamDocumentChunk",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AITeamDocumentChunk.chunk_index",
    )


class AITeamDocumentChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_team_document_chunks"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as a JSON array of floats (portable; no pgvector required).
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped["AITeamDocument"] = relationship("AITeamDocument", back_populates="chunks")


class AITeamWorkflow(Base, UUIDMixin, TimestampMixin):
    """Sprint 38A — a reusable, ordered workflow template over an AI Team.

    A workflow captures which team executes, in what agent order, with optional
    per-step instruction overrides and an optional default prompt — so a
    customer can save the flow once and execute it many times. This is a
    template only: no scheduling, autonomous execution, memory, or approval
    gates. Execution reuses the Sprint 37C collaboration engine.
    """

    __tablename__ = "ai_team_workflows"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    steps: Mapped[list["AITeamWorkflowStep"]] = relationship(
        "AITeamWorkflowStep",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AITeamWorkflowStep.step_order",
    )


class AITeamWorkflowStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_team_workflow_steps"

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL so a workflow survives agent deletion; a null agent step is
    # skipped at execution time.
    agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint 38C — when set, the workflow pauses after this step for human review.
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approver_role: Mapped[str | None] = mapped_column(String(120), nullable=True)

    workflow: Mapped["AITeamWorkflow"] = relationship("AITeamWorkflow", back_populates="steps")


class AITeamWorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_team_workflow_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AITeamWorkflowRunStatus] = mapped_column(
        String(20), nullable=False, default=AITeamWorkflowRunStatus.RUNNING
    )
    # Sprint 38B — distinguishes a user-triggered run from an automatic one.
    execution_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AITeamWorkflowExecutionSource.MANUAL.value
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint 38C — execution state captured so an approval-paused run can resume.
    # ``plan`` is the JSON snapshot of the ordered steps taken at run start (so a
    # later workflow edit cannot corrupt an in-flight run); ``completed_steps``
    # holds the JSON list of {agent_name, response} produced so far; and
    # ``resume_index`` is the next plan index to execute on resume.
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AITeamWorkflowApproval(Base, UUIDMixin, TimestampMixin):
    """Sprint 38C — a human approval checkpoint for a paused workflow run.

    Created when an executed step's ``requires_approval`` flag is set; the run
    pauses (WAITING_FOR_APPROVAL) until a human approves (resume) or rejects
    (fail). Purely a human checkpoint: no autonomous/auto-approval logic, email,
    or escalation chains.
    """

    __tablename__ = "ai_team_workflow_approvals"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_team_workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_name: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AITeamWorkflowApprovalStatus.PENDING.value
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped["DateTime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)


class AITeamWorkflowSchedule(Base, UUIDMixin, TimestampMixin):
    """Sprint 38B — a recurring trigger for a saved workflow.

    Every minute a background scheduler finds active schedules whose
    ``next_run_at`` is due, executes the workflow through the existing 38A
    engine (no duplicated execution logic), and advances ``next_run_at`` using
    the cron expression evaluated in the schedule's timezone. This is purely
    time-based triggering: no autonomous decisions, loops, memory, or approval
    gates.
    """

    __tablename__ = "ai_team_workflow_schedules"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Canonical schedule time; for DAILY/WEEKLY/MONTHLY the UI builds the cron,
    # for CUSTOM_CRON the customer supplies it directly.
    cron_expression: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped["DateTime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped["DateTime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class AITeamAgentMemory(Base, UUIDMixin, TimestampMixin):
    """Sprint 39A — persistent memory for a single AI Team Agent.

    Turns a stateless agent into a persistent "AI employee" that recalls past
    decisions, lessons, conversations, and project context across executions.
    Memories are user-curated (explicit "Save to Memory" — never auto-stored)
    and embedded so the most relevant ones can be retrieved and injected into a
    prompt at execution time. Strictly additive: the internal APPYLN pipeline,
    deployment, QA, approval, and lifecycle engines are untouched.
    """

    __tablename__ = "ai_team_agent_memory"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=AITeamAgentMemoryType.MEMORY_DECISION.value
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 1–10; nudges retrieval ranking (similarity stays dominant).
    importance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # Provenance: the run a memory was saved from (SET NULL keeps memory if the
    # run is later pruned). Free-form id, no FK so it can reference agent/team/
    # workflow runs interchangeably.
    created_from_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Embedding stored as a JSON array of floats (portable; no pgvector required).
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)


class AITeamTool(Base, UUIDMixin, TimestampMixin):
    """Sprint 39B — a registered, read-only integration an org can connect.

    A tool is a named connection to an external engineering/infra system
    (Kubernetes, Azure, GitHub, …). This sprint is investigation-only: tools
    expose a fixed allow-list of read operations and can never mutate, deploy,
    scale, or execute shell commands. Strictly additive: existing AI Team,
    execution, knowledge, memory, workflow, and approval behavior is untouched.
    """

    __tablename__ = "ai_team_tools"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AITeamAgentTool(Base, UUIDMixin, TimestampMixin):
    """Sprint 39B — assigns a tool to an agent (many-to-many).

    One tool may serve many agents; one agent may hold many tools. Only an
    explicitly assigned, active tool can be executed by an agent.
    """

    __tablename__ = "ai_team_agent_tools"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_tools.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AITeamToolRun(Base, UUIDMixin, TimestampMixin):
    """Sprint 39B — an audited record of a single read-only tool execution.

    Stores a sanitized request payload (never credentials/secrets) and a
    customer-safe response summary. No live mutation is ever performed.
    """

    __tablename__ = "ai_team_tool_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_team_tools.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AITeamToolRunStatus.COMPLETED.value
    )
    # Sanitized JSON of the request inputs (secret-like keys are redacted).
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AITeamToolCredential(Base, UUIDMixin, TimestampMixin):
    """Sprint 39C — links a read-only tool to a Sprint 35A encrypted credential.

    This table NEVER stores secrets. It only references a credential in
    ``deployment_credentials`` (which holds the AES-256-GCM ciphertext). At
    execution/verification time the credential is resolved + decrypted in-process
    via ``SecretManagerService`` and used transiently by the tool connector.
    """

    __tablename__ = "ai_team_tool_credentials"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_team_tools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credential_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployment_credentials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
