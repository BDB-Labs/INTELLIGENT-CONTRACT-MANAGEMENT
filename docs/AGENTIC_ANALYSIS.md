# Agentic Intelligence vs. Prompt-Based Ensemble: Analysis & Migration Plan

## Executive Summary

The current ESE system uses a **prompt-based ensemble** architecture: each role is a single LLM call with a carefully crafted prompt, chained sequentially or in parallel. An **agentic** approach would replace individual roles with autonomous agents that can plan, execute multiple LLM calls, use tools, self-correct, and iterate until a quality threshold is met.

This document analyzes the trade-offs and provides a phased migration plan.

---

## Current Architecture: Prompt-Based Ensemble

```
User Input → Config → Pipeline → [Role 1] → [Role 2] → [Role 3] → ... → Output
                ↓          ↓          ↓          ↓
            Single LLM   Single LLM   Single LLM   Single LLM
            Call         Call         Call         Call
            + Prompt     + Prompt     + Prompt     + Prompt
```

Each role = 1 LLM call. Quality depends entirely on prompt engineering and model capability. Self-reflection is opt-in and limited to 1 regeneration round.

---

## Proposed Architecture: Agentic Ensemble

```
User Input → Config → Pipeline → [Agent 1] → [Agent 2] → [Agent 3] → ... → Output
                ↓          ↓           ↓           ↓
            Planner     Planner     Planner     Planner
            ↓           ↓           ↓           ↓
            LLM Call → Tool Use → LLM Call → Tool Use
            ↓           ↓           ↓           ↓
            Evaluator ← Result ←  Evaluator ← Result
            ↓                       ↓
            Iterate if needed      Iterate if needed
            ↓                       ↓
            Final Output           Final Output
```

Each agent = autonomous loop: plan → execute → evaluate → iterate → deliver. Agents can use tools (search, file read, knowledge base queries, CRM lookups) and self-correct until quality thresholds are met.

---

## Pros of Agentic Approach

### 1. **Dramatically Higher Output Quality**
- Current: Single attempt, quality varies by model and prompt
- Agentic: Multiple iterations with self-evaluation, quality converges upward
- Evidence: Research shows agentic workflows (ReAct, Reflexion) outperform single-shot prompting by 15-40% on complex reasoning tasks
- Impact: Contract analysis findings would be more thorough, accurate, and actionable

### 2. **Autonomous Tool Use**
- Current: Context is pre-assembled and static; roles can't fetch additional information
- Agentic: Agents can query the knowledge base, look up CRM history, read additional files, search regulations
- Impact: `relationship_advisor` could autonomously pull entity history; `contract_risk_analyst` could search for relevant case law

### 3. **Dynamic Reasoning Depth**
- Current: Every role gets the same computational budget (1 call)
- Agentic: Simple tasks resolve quickly; complex tasks get more iterations
- Impact: Cost-efficient — easy contracts use fewer tokens, hard contracts get deeper analysis

### 4. **Built-in Self-Correction**
- Current: Self-reflection is opt-in, single round, generic
- Agentic: Evaluation is role-specific, multi-round, with concrete improvement criteria
- Impact: The certainty assessment we built becomes the agent's internal quality gate

### 5. **Adaptive Context Gathering**
- Current: All roles receive the same upstream artifacts regardless of need
- Agentic: Each agent decides what context it needs and fetches it
- Impact: Reduces context window waste; agents focus on relevant information

### 6. **Parallel Agent Collaboration**
- Current: Parallel roles work in isolation; no cross-communication
- Agentic: Agents can delegate sub-tasks, ask other agents for clarification, resolve contradictions
- Impact: `negotiation_strategist` could ask `relationship_advisor` for clarification on ambiguous findings

### 7. **Auditability of Reasoning**
- Current: Only the final output is visible; reasoning is opaque
- Agentic: Full reasoning trace is captured (plan → steps → evaluations → decisions)
- Impact: Users can see WHY an agent reached a conclusion, not just WHAT it concluded

### 8. **Graceful Degradation**
- Current: If a role fails, the pipeline stops or produces garbage
- Agentic: Agents can recognize when they can't complete a task and escalate or simplify
- Impact: More resilient to edge cases and unusual contract types

---

## Cons of Agentic Approach

### 1. **Significantly Higher Cost**
- Current: 13 roles × 1 LLM call = ~13 calls per analysis
- Agentic: 13 agents × 3-5 iterations average = ~40-65 calls per analysis
- Cost increase: 3-5× token usage, directly proportional to API costs
- Mitigation: Dynamic iteration limits, early termination on quality threshold, caching

### 2. **Higher Latency**
- Current: ~30-60 seconds for demo mode, ~5-15 minutes for live mode
- Agentic: 2-5× longer due to iterative loops and tool calls
- Impact: User experience degrades for interactive use
- Mitigation: Streaming progress updates, async execution, pre-computation

### 3. **Complexity Explosion**
- Current: Simple pipeline, easy to understand, debug, and test
- Agentic: State machines, tool registries, evaluation criteria, iteration limits, escalation paths
- Impact: Development and maintenance burden increases significantly
- Risk: Agent loops can become unpredictable; debugging is harder

### 4. **Non-Deterministic Behavior**
- Current: Same input → same output (mostly, given same model/temperature)
- Agentic: Same input → different reasoning paths → different outputs
- Impact: Harder to test, validate, and certify for production use
- Risk: Regulatory/compliance environments may require deterministic outputs

### 5. **Tool Dependency Risks**
- Current: No external tool dependencies during execution
- Agentic: Agents depend on knowledge base, CRM, file system, search APIs
- Impact: If a tool fails, the agent may fail or produce incomplete results
- Risk: Cascading failures across the system

### 6. **Prompt Engineering Becomes Agent Design**
- Current: Prompt engineering is well-understood and iterative
- Agentic: Requires designing agent architectures, tool interfaces, evaluation criteria, escalation policies
- Impact: New skill set required; existing prompt investments partially wasted
- Risk: Poor agent design is worse than good prompt engineering

### 7. **Security Concerns**
- Current: Prompts are static; no dynamic code execution
- Agentic: Agents with tool access could potentially be manipulated via prompt injection in contract documents
- Impact: Malicious contract text could influence agent behavior
- Risk: Data exfiltration, unauthorized file access, infinite loops

### 8. **Testing Overhead**
- Current: 150 tests, mostly deterministic, fast execution
- Agentic: Tests need to handle non-determinism, mock tools, validate reasoning traces
- Impact: Test suite becomes slower, more complex, harder to maintain

---

## Hybrid Recommendation: Gradual Agentic Migration

**Do NOT replace the entire ensemble at once.** Instead, use a **tiered approach**:

### Tier 1: Keep as Prompt-Based (No Change)
Roles that are well-defined, deterministic, and don't benefit from iteration:
- `document_intake_analyst` — Classification is straightforward
- `insurance_requirements_analyst` — Rule-based pattern matching
- `funding_compliance_analyst` — Regulatory checklist
- `obligation_register_builder` — Extraction task
- `procurement_structure_analyst` — Pattern detection

**Why:** These roles produce consistent, high-quality output with single calls. Agentic overhead would add cost without meaningful quality improvement.

### Tier 2: Add Self-Reflection (Low-Cost Agentic)
Roles that benefit from quality checking but don't need full agents:
- `contract_risk_analyst` — Add multi-round self-reflection with role-specific criteria
- `adversarial_reviewer` — Already adversarial; add structured critique loop
- `context_intelligence_analyst` — Add evidence verification loop

**Why:** The self-reflection infrastructure already exists. Just needs to be enabled by default for these roles with role-specific evaluation criteria.

### Tier 3: Full Agentic (High-Value Targets)
Roles where autonomous reasoning and tool use provide clear value:
- `relationship_advisor` — Should query CRM, knowledge base, and iterate on relationship assessment
- `negotiation_strategist` — Should synthesize iteratively, test strategies against historical data
- `bid_decision_analyst` — Should weigh evidence, consider alternatives, and justify decisions

**Why:** These roles are inherently judgment-based, benefit from historical context, and produce high-stakes recommendations where quality matters most.

---

## Migration Plan

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Build the agent framework infrastructure without changing existing roles.

1. **Create `ese/agents/` package:**
   - `agent.py` — Base agent class with plan → execute → evaluate → iterate loop
   - `tools.py` — Tool registry (knowledge base query, CRM lookup, file read, search)
   - `evaluator.py` — Role-specific evaluation criteria and scoring
   - `tracer.py` — Reasoning trace capture for auditability

2. **Define Agent Interface:**
   ```python
   class Agent(Protocol):
       def execute(self, task: str, context: dict) -> AgentResult:
           ...

   @dataclass
   class AgentResult:
       output: str
       reasoning_trace: list[Step]
       quality_score: float
       iterations: int
       tools_used: list[str]
   ```

3. **Build Tool Implementations:**
   - `KnowledgeBaseTool` — Query RAG knowledge base
   - `CRMTool` — Query CRM for entity history
   - `FileReadTool` — Read project documents
   - `SearchTool` — Search contract terms database

4. **Write Tests:**
   - Unit tests for each tool
   - Integration tests with mock LLM
   - Deterministic seed-based testing for reproducibility

### Phase 2: Tier 2 Migration — Self-Reflection (Weeks 3-4)
**Goal:** Enable multi-round self-reflection for 3 roles without full agent infrastructure.

1. **Enhance existing self-reflection:**
   - Make it role-specific (different evaluation criteria per role)
   - Increase max rounds from 1 to 3
   - Add quality threshold gating (don't regenerate if score > 0.8)

2. **Roles to upgrade:**
   - `contract_risk_analyst`
   - `adversarial_reviewer`
   - `context_intelligence_analyst`

3. **Configuration:**
   ```yaml
   reflection:
     enabled: true
     roles:
       contract_risk_analyst:
         max_rounds: 3
         min_score: 0.7
         criteria: ["completeness", "evidence", "specificity", "severity_accuracy"]
       adversarial_reviewer:
         max_rounds: 3
         min_score: 0.7
         criteria: ["contradiction_detection", "missed_risks", "assumption_challenge"]
       context_intelligence_analyst:
         max_rounds: 2
         min_score: 0.6
         criteria: ["evidence_anchoring", "signal_detection", "gap_identification"]
   ```

4. **Testing:**
   - Verify quality improvement on evaluation corpus
   - Measure cost/latency impact
   - Ensure no regression on existing tests

### Phase 3: Tier 3 Migration — Full Agents (Weeks 5-8)
**Goal:** Replace 3 high-value roles with full agentic implementations.

1. **Implement `RelationshipAdvisorAgent`:**
   - Tools: CRM lookup, knowledge base search, entity pattern analysis
   - Evaluation: Relationship impact accuracy, recommendation actionability, entity-specific relevance
   - Iteration: Max 4 rounds, quality threshold 0.75

2. **Implement `NegotiationStrategistAgent`:**
   - Tools: Knowledge base search, historical outcome comparison, trade-off analysis
   - Evaluation: Strategy coherence, priority accuracy, phase realism, trade-off balance
   - Iteration: Max 5 rounds, quality threshold 0.8

3. **Implement `BidDecisionAgent`:**
   - Tools: All upstream artifact analysis, risk aggregation, confidence calibration
   - Evaluation: Recommendation justification, risk coverage, confidence calibration
   - Iteration: Max 3 rounds, quality threshold 0.7

4. **Pipeline Integration:**
   - Agents drop into existing pipeline as drop-in replacements
   - Same input/output interface as current roles
   - Backward compatible: if agent fails, falls back to prompt-based role

5. **Testing:**
   - A/B testing: agent vs. prompt-based output quality
   - Cost analysis: per-role token usage comparison
   - Latency measurement: end-to-end pipeline timing

### Phase 4: Optimization & Monitoring (Weeks 9-10)
**Goal:** Optimize agent performance and add production monitoring.

1. **Dynamic Iteration Limits:**
   - Start with max iterations, reduce based on convergence patterns
   - Learn optimal iteration count per role from historical data

2. **Caching Layer:**
   - Cache agent results for identical inputs
   - Cache tool responses (knowledge base queries, CRM lookups)
   - TTL-based cache invalidation

3. **Monitoring Dashboard:**
   - Per-agent quality scores over time
   - Cost per analysis breakdown
   - Latency percentiles
   - Iteration distribution histograms
   - Tool usage frequency

4. **Fallback Mechanism:**
   - If agent exceeds cost/latency budget, fall back to prompt-based role
   - If agent quality score doesn't converge, escalate to human review

### Phase 5: Evaluation & Decision (Week 11)
**Goal:** Measure results and decide on further migration.

1. **Quality Metrics:**
   - Compare agent output quality vs. prompt-based on evaluation corpus
   - Human reviewer blind assessment
   - Finding accuracy against known contract issues

2. **Cost Metrics:**
   - Token usage per analysis (before/after)
   - API cost per analysis
   - Cost per quality point (cost / quality_score)

3. **Latency Metrics:**
   - P50, P95, P99 latency
   - Per-role timing breakdown

4. **Decision Gate:**
   - If quality improvement > 20% AND cost increase < 3× → Expand to more roles
   - If quality improvement < 10% OR cost increase > 5× → Revert Tier 3, keep Tier 2
   - If mixed results → Optimize agents, re-evaluate

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Cost explosion | Dynamic iteration limits, caching, early termination, budget caps |
| Latency increase | Async execution, streaming progress, pre-computation, parallel agents |
| Non-determinism | Seeded testing, reasoning trace capture, output validation gates |
| Security | Tool sandboxing, input sanitization, prompt injection detection, rate limiting |
| Complexity | Clean agent interface, comprehensive testing, gradual migration, fallback paths |
| Tool failures | Graceful degradation, tool health checks, fallback to prompt-based roles |
| Testing difficulty | Mock LLM, deterministic seeds, evaluation corpus, A/B testing framework |

---

## Cost-Benefit Summary

| Metric | Current | After Full Migration | Change |
|--------|---------|---------------------|--------|
| LLM calls per analysis | ~13 | ~40-65 | +3-5× |
| Analysis time (live) | 5-15 min | 15-45 min | +3× |
| Output quality (estimated) | Baseline | +20-40% | Significant |
| Development effort | — | 10-12 weeks | Investment |
| Maintenance burden | Low | Medium-High | Increased |
| Auditability | Output only | Full reasoning trace | Improved |
| Flexibility | Static prompts | Dynamic tool use | Improved |

---

## Recommendation

**Proceed with Phases 1-3 only.** The hybrid approach gives you 80% of the quality benefit at 40% of the cost and complexity of a full agentic migration. Keep the 5 deterministic roles as prompt-based (they work well), add self-reflection to 3 roles (low-cost, high-value), and build full agents only for the 3 judgment-heavy roles where autonomous reasoning provides clear differentiation.

**Do NOT proceed to full agentic migration** until Phase 5 evaluation demonstrates clear ROI. The current prompt-based ensemble is a strong foundation — agentic intelligence should augment it, not replace it entirely.
