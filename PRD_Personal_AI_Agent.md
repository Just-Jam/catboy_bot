# Personal AI Agent - Product Requirements Document

**Version:** 1.0  
**Date:** 2026-04-22  
**Status:** Draft - For Review

---

## 1. Executive Summary

### 1.1 Product Vision
A personal AI agent system that automates software development workflows through a 3-layer microservice architecture. The system orchestrates specialized AI agents to complete complex tasks with human approval gates, learning from user preferences and project history over time.

### 1.2 Primary Use Case
**Priority 1:** Automating software development workflows (plan → code → test → deploy)  
**Future:** Business automation, personal productivity, investment/trading analysis

### 1.3 MVP Scope
A minimal orchestration layer that routes tasks to specialized agents with approval flows. Memory system and advanced features added in subsequent phases.

---

## 2. System Architecture

### 2.1 Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    TOP LAYER (Gateway)                       │
│  Discord Bot + Web Dashboard                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  MIDDLE LAYER (Orchestrator)                 │
│  Task Router + Approval Gateway + Memory + State Manager     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BOTTOM LAYER (Specialists)                 │
│  Research Agent │ Software Engineer Agent │ QA Agent         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

#### Top Layer (Gateway)
- **Channels:** Discord (primary), Web Dashboard (secondary)
- **Responsibilities:**
  - Receive user commands and task submissions
  - Display task status and progress
  - Present approval requests with summaries (Discord) and detailed views (Dashboard)
  - Optimize output format per channel (summarized for Discord, full detail for dashboard)

#### Middle Layer (Orchestrator / "CEO")
- **Runtime:** Node.js (Express/NestJS)
- **Deployment:** Home server (always online)
- **Responsibilities:**
  - Parse incoming requests and create task plans
  - Route tasks to appropriate specialist agents
  - Manage approval gates (send plan for approval, wait, execute, present results)
  - Store and retrieve from unified memory (user preferences, project context, task history)
  - Handle hybrid state persistence (critical state checkpointed to DB, transient in memory)
  - Manage concurrent task execution with configurable limits
  - Escalate failures to user with details and options

#### Bottom Layer (Specialists)
- **Agents (MVP):**
  1. **Research Agent:** Discovers documentation, patterns, best practices, API references
  2. **Software Engineer Agent:** Writes code, refactors, implements features
  3. **QA Agent:** Reviews code, writes tests, validates against requirements
- **Characteristics:**
  - No long-term memory (unless explicitly configured)
  - Invoked by Middle Layer or manually by user
  - Configurable LLM per agent with sensible defaults
  - Can call sub-agents 1-2 layers down (future capability)

---

## 3. Functional Requirements

### 3.1 Task Flow (Sequential Orchestration)
```
User Request → Research → Plan → Approval → Execute → QA → Results
```

**Detailed Flow:**
1. User submits request via Discord or dashboard
2. Middle Layer creates task and assigns to Research Agent
3. Research Agent returns findings (docs, patterns, constraints)
4. Middle Layer creates development plan based on research
5. Middle Layer sends plan to user for approval (Discord summary + dashboard link)
6. User approves/rejects via Discord reactions or dashboard
7. Upon approval, Middle Layer assigns execution to Software Engineer Agent
8. Engineer Agent produces code/implementation
9. QA Agent validates the implementation
10. Results presented to user with summary (Discord) and full report (dashboard)

### 3.2 Approval Gate
- **Trigger:** After plan creation, before execution
- **Discord:** Summary message with ✅/❌ reaction buttons + link to dashboard
- **Dashboard:** Full plan details, diff view, comment capability
- **Timeout:** Configurable (default: 24 hours), then task paused until user responds

### 3.3 Memory System

The orchestrator requires four distinct memory types, each with different storage, retrieval, and decay characteristics:

#### 3.3.1 Memory Architecture

| Type | Stores | Retrieval | Decay | Implementation |
|------|--------|-----------|-------|----------------|
| **Working** | Current task context, active conversation | Direct (in-context) | End of task | Agent context window |
| **Episodic** | Events, conversations, decisions with timestamps | Similarity + recency | Time-weighted pruning (90 days, salience < 0.4) | Mem0 (vector + semantic search) |
| **Semantic** | User preferences, facts, relationships with temporal validity | Graph traversal + exact match | Invalidation on contradiction | Graphiti (temporal knowledge graph) |
| **Procedural** | Learned action sequences, successful workflows, outcome scores | Situation matching + success filtering | Low-success pruning | PostgreSQL + pgvector (custom) |

#### 3.3.2 Component Responsibilities

**Mem0** (Episodic + general semantic memory):
- Stores conversation history, task outcomes, user interactions
- Handles contradictions via 4-operation cycle: ADD, UPDATE, DELETE, NOOP
- Vector + BM25 + entity matching for multi-signal retrieval
- Async writes (never block agent responses)

**Graphiti** (Temporal knowledge graph):
- Tracks *when* facts became true and when invalidated (bi-temporal model)
- 3-layer subgraph: Episodic (raw sessions) → Semantic (entities + facts) → Community (clusters)
- Multi-hop reasoning over user preferences and project constraints
- Custom entity/edge types via Pydantic models (e.g., `User`, `Project`, `Preferred`)

**Letta** (Agent state management):
- Core memory blocks: always-in-context state the orchestrator self-edits
- Archival memory: vector-backed long-term storage
- Sleep-time consolidation: background agents that refine memory during idle periods
- Agent decides what to remember, update, and forget via tool calls

**PostgreSQL + pgvector** (Procedural memory):
- Situation-action-outcome records for learned workflows
- Success scoring (0.0-1.0) to rank retrieval
- Filters on `outcome_type='success'` to retrieve only working approaches

#### 3.3.3 Memory Compaction & Maintenance
- **Session summarization:** 3-5 sentence summaries at session end; individual turns archived
- **Time-decay pruning:** Soft-delete events >90 days old with salience < 0.4
- **Fact consolidation:** Archive episodic traces that merely confirm existing semantic facts
- **Salience scoring:** All episodic entries scored 0.0-1.0; critical events (user corrections, preference statements, errors) receive higher scores
- **Async writes:** Queue events to in-process buffer, flush to persistent store in background (avoid 50-200ms latency per turn)

#### 3.3.4 Production Targets
- Retrieval precision@5: > 0.7
- Retrieval latency: < 200ms (remote vector store), < 100ms (local)
- Session continuity: > 80% application of stated preferences across sessions
- Context hit rate: > 40% of sessions where memory changed agent response

### 3.4 Task Management
- **Concurrency:** Parallel execution with configurable limit (N tasks max)
- **Queue:** Task queue with priority support (future enhancement)
- **State:** Hybrid persistence
  - Critical state (task status, approvals, results) checkpointed to DB
  - Transient state (agent progress, intermediate outputs) in memory

### 3.5 Error Handling
- **Strategy:** Immediate escalation to user
- **Format:** Detailed error message via Discord + dashboard with:
  - What failed (agent, task, step)
  - Why it failed (error details, logs)
  - Options (retry, skip, modify approach, abort)

### 3.6 Web Dashboard
**MVP Features:**
- Task list with status (pending, running, completed, failed)
- Agent status (idle, busy, error)
- Recent activity log
- Memory browser (search past decisions, project context)
- Agent configuration UI (LLM selection, prompts, parameters)

**Future:** Analytics (time per task, success rates, cost per agent/model)

---

## 4. Non-Functional Requirements

### 4.1 Availability
- Middle Layer: Always online (home server deployment)
- Recovery: Hybrid state persistence allows recovery from crashes

### 4.2 Performance
- Task response time: < 5 seconds for acknowledgment
- Approval notification: < 30 seconds
- Dashboard load time: < 2 seconds

### 4.3 Scalability
- Concurrent tasks: Configurable limit (start with 3-5)
- Memory: Support 10,000+ memory entries with sub-second retrieval

### 4.4 Security
- Home server deployment (local network)
- Discord bot token secured via environment variables
- Dashboard authentication (TBD: local auth, OAuth, etc.)

### 4.5 Observability
- Activity log for all task events
- Agent execution logs
- Error tracking and escalation audit trail

---

## 5. Technical Specifications

### 5.1 Tech Stack
| Component | Technology |
|-----------|------------|
| Middle Layer Runtime | Node.js (Express or NestJS) |
| Task Queue | Bull (Redis-based) or native JS queue |
| Memory - Episodic | Mem0 (self-hosted, Docker) |
| Memory - Semantic | Graphiti + Neo4j (self-hosted, Docker) |
| Memory - Agent State | Letta (self-hosted, Docker) |
| Memory - Procedural | PostgreSQL + pgvector |
| Database (Tasks, State) | PostgreSQL |
| Discord Integration | discord.js |
| Web Dashboard | React or Vue.js (TBD) |
| Deployment | Docker on home server |

### 5.2 Agent Configuration
- **LLM Selection:** Configurable per agent
- **Default Recommendations (TBD based on research):**
  - Research Agent: Claude Sonnet or GPT-4 (strong reasoning)
  - Software Engineer: Claude Sonnet 4.5+ (strong coding)
  - QA Agent: Claude Sonnet or GPT-4 (attention to detail)

### 5.3 APIs and Interfaces
- **Discord Bot Commands:**
  - `/task <description>` - Submit new task
  - `/status [task-id]` - Check task status
  - `/approve <task-id>` - Approve pending plan
  - `/reject <task-id>` - Reject pending plan
  - `/memory <query>` - Search memory

- **Dashboard API (REST):**
  - `GET /tasks` - List all tasks
  - `GET /tasks/:id` - Get task details
  - `POST /tasks/:id/approve` - Approve task plan
  - `POST /tasks/:id/reject` - Reject task plan
  - `GET /agents` - List agent status
  - `GET /memory?q=<query>` - Search memory
  - `PUT /agents/:id/config` - Update agent configuration

---

## 6. Open Questions & Research Items

### 6.1 Data Store & Memory Architecture (RESOLVED)
**Decision:** Layered memory architecture using specialized tools per memory type

Based on research into agentic AI memory systems (April 2026), the architecture uses a **layered approach** where different memory types use purpose-built storage:

| Memory Type | Tool | Storage Backend | Why |
|-------------|------|-----------------|-----|
| Episodic (events, conversations) | Mem0 | PostgreSQL + pgvector + Neo4j | Battle-tested, handles contradictions, multi-signal retrieval |
| Semantic (facts, preferences) | Graphiti | Neo4j | Temporal validity tracking, multi-hop reasoning, bi-temporal model |
| Agent State (working memory) | Letta | PostgreSQL (Docker) | Agent self-manages memory, sleep-time consolidation |
| Procedural (learned workflows) | Custom | PostgreSQL + pgvector | Situation-action-outcome with success scoring |
| Tasks, State, Config | PostgreSQL | PostgreSQL | Structured data, ACID, already in stack |

**Key tradeoffs considered:**
- Vector DB alone (Mem0) excels at retrieval but can't reason over relationships or track temporal validity
- Knowledge Graph alone (Graphiti) is great for structured facts but overkill for raw event storage
- Letta's agent-managed memory avoids manual memory engineering but is a heavier framework dependency
- Combining them increases infrastructure complexity but each handles what it's best at

**Infrastructure footprint (Docker Compose):**
- PostgreSQL (tasks + procedural memory + Mem0 backend)
- Neo4j (Graphiti knowledge graph)
- Letta server (agent state management)
- Redis (task queue + session buffer)

**MVP simplification:** Start with Mem0 + PostgreSQL only. Add Graphiti and Letta in Phase 2 when temporal reasoning and agent self-management become necessary.

**Alternatives evaluated:**
- **Mem0 alone** (simpler, but no temporal reasoning — facts can't track when they changed)
- **Zep managed** (less infra, but Zep Community Edition deprecated April 2025, self-hosting requires Graphiti + graph DB anyway)
- **LangGraph Store** (fine-grained control, but manual memory engineering — no agent self-management)
- **@presidio-dev/agent-memory** (TypeScript-native, cognitive sectors, Ebbinghaus decay — promising but less mature)
- **Hindsight** (highest benchmark scores at 91.4% LongMemEval, but newer system with less production track record)

### 6.2 LLM Selection (MEDIUM PRIORITY)
**Decision Needed:** Default model per agent

Research required on:
- Current model capabilities for coding (HumanEval scores, real-world performance)
- Cost per token for each agent's typical workload
- Latency considerations for real-time vs batch tasks

### 6.3 Dashboard Authentication (LOW PRIORITY)
**Decision Needed:** How to secure dashboard access

Options:
- Local username/password
- Discord OAuth (leverage existing Discord auth)
- API token-based
- Local network only (no auth, rely on network security)

---

## 7. MVP Milestones

### Phase 1: Core Orchestration (Weeks 1-3)
- [ ] Node.js Middle Layer skeleton
- [ ] Discord bot integration (basic commands)
- [ ] Task queue implementation
- [ ] Research Agent integration
- [ ] Software Engineer Agent integration
- [ ] QA Agent integration

### Phase 2: Approval Flow (Weeks 4-5)
- [ ] Approval gate logic
- [ ] Discord approval messages with reactions
- [ ] Basic web dashboard (task list, approval view)

### Phase 3: Memory System (Weeks 6-8)
- [ ] PostgreSQL + pgvector setup
- [ ] Mem0 self-hosted deployment (Docker)
- [ ] Episodic memory: store/retrieve conversations, task outcomes
- [ ] Semantic memory: extract and store user preferences, project facts
- [ ] Memory retrieval API for orchestrator
- [ ] Procedural memory: record successful action sequences
- [ ] Memory compaction: session summarization, salience scoring, time-decay pruning
- [ ] Async memory writes (non-blocking)
- [ ] Dashboard memory browser
- [ ] Phase 2 prerequisites: Neo4j + Graphiti for temporal reasoning, Letta for agent self-management

### Phase 4: Polish & Hardening (Weeks 9-10)
- [ ] Error handling and escalation
- [ ] Hybrid state persistence
- [ ] Concurrent task limits
- [ ] Agent configuration UI

---

## 8. Success Criteria

### MVP Acceptance Criteria
1. User can submit a software dev task via Discord
2. System routes task through Research → Plan → Approval → Execute → QA flow
3. User receives approval request on Discord with dashboard link
4. User can approve/reject via Discord reactions
5. System executes approved plan and reports results
6. Memory is stored and retrievable for future context

### Long-term Success Metrics
- Tasks completed without human intervention (after approval): > 80%
- Average time from request to completion: < 30 minutes for small tasks
- User satisfaction (subjective): System feels like having a junior dev team

---

## 9. Future Enhancements (Post-MVP)

- Telegram integration
- Additional specialist agents (DevOps, Security Review, Documentation)
- Priority-based task queuing
- Analytics dashboard (cost, time, success rates)
- Sub-agent hierarchies (agents calling agents)
- Voice interface integration
- Automated deployment pipeline integration

---

## 10. Appendix

### 10.1 Glossary
- **Middle Layer:** The orchestrator/"CEO" that manages tasks, memory, and approvals
- **Specialist Agent:** A role-configured AI agent (Research, Engineer, QA)
- **Approval Gate:** The checkpoint where user must approve before execution
- **Unified Memory:** Combined storage for preferences, context, and history

### 10.2 References
- Original architecture outline: `temp.md`
- Discord bot repo: `discord_bot_v1`

### 10.3 Memory Architecture Research (April 2026)

**Papers:**
- Agentic Memory (AgeMem) — arXiv:2601.01885: RL-trained agent learns what/when/how to store, retrieve, discard. 6 memory tools (ADD, UPDATE, DELETE, RETRIEVE, SUMMARY, FILTER).
- TeleMem — arXiv:2601.06037: Narrative extraction prevents hallucinated memories. Batched write pipeline. 19% higher accuracy, 43% fewer tokens than Mem0.
- Hippocampus — arXiv:2602.13594: Compressed binary signatures replace dense vectors. 31x faster retrieval, 14x fewer tokens.
- CraniMem (ICLR 2026) — arXiv:2603.15642: Brain-inspired dual-store (episodic buffer + knowledge graph) with gated consolidation and forgetting. Lowest noise susceptibility.

**Frameworks evaluated:**
- Mem0 (53.7K stars, Apache 2.0): Vector-first + optional graph. Best for episodic/personalization. Self-hostable.
- Graphiti/Zep (25.2K stars, Apache 2.0): Temporal knowledge graph. Best for tracking when facts changed. Self-hostable (Graphiti core).
- Letta/MemGPT (22.2K stars, Apache 2.0): Agent-managed 3-tier memory (core/archival/recall). Best for self-improving agents.
- @presidio-dev/agent-memory: 5 cognitive sectors, Ebbinghaus decay. TypeScript-native. Less mature.
- Hindsight: 4-network architecture. Highest benchmark (91.4% LongMemEval). Newer system.

**Key production lessons:**
1. Never block agent responses on memory writes — queue async (50-200ms overhead otherwise)
2. Compaction is mandatory — session summarization, time-decay deletion, fact consolidation
3. Salience scoring prevents noise — not all events are equal
4. Temporal validity tracking is essential — "user moved to Berlin" must invalidate "user lives in London"
5. Forgetting is a feature — RIF scoring + Ebbinghaus curves can prune 40-60% after 30 days
