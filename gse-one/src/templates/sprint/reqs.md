---
gse:
  type: requirement
  sprint: 1                            # numeric sprint number
  branch: gse/sprint-01/integration     # sprint branch
  elicitation_summary: ""              # Step 0 output: user's needs in their own words + agent reformulation
  traces:
    implements: []                     # e.g., [TASK-001] — requirements this doc implements
  status: draft                        # draft | reviewed | approved
  created: ""
  updated: ""
---

# Requirements — Sprint {sprint}

## Functional Requirements

### R01 — {title}

- **Actor:** {who}
- **Capability:** {what}
- **Rationale:** {why}
- **Priority:** Must | Should | Could
- **Acceptance Criteria:**
  1. {measurable criterion 1}
  2. {measurable criterion 2}
- **Traces:** Design: D01 | Tests: T01, T02

### R02 — {title}

- **Actor:** {who}
- **Capability:** {what}
- **Rationale:** {why}
- **Priority:** Must | Should | Could
- **Acceptance Criteria:**
  1. {measurable criterion 1}
  2. {measurable criterion 2}
- **Traces:** Design: — | Tests: —

## Non-Functional Requirements

### NFR01 — Performance

- **Metric:** {e.g., response time}
- **Target:** {e.g., < 200ms at p95}
- **Measurement:** {how it will be verified}
- **Priority:** Must | Should | Could

### NFR02 — Security

- **Metric:** {e.g., OWASP compliance}
- **Target:** {e.g., no critical vulnerabilities}
- **Measurement:** {how it will be verified}
- **Priority:** Must | Should | Could

### NFR03 — Accessibility

- **Metric:** {e.g., WCAG level}
- **Target:** {e.g., WCAG 2.1 AA}
- **Measurement:** {how it will be verified}
- **Priority:** Must | Should | Could

## Traceability Matrix

| Req ID | Design | Tests | Status   |
|--------|--------|-------|----------|
| R01    |        |       | draft    |
| R02    |        |       | draft    |
| NFR01  |        |       | draft    |
| NFR02  |        |       | draft    |
| NFR03  |        |       | draft    |

## Quality Coverage Matrix

_Results of the ISO 25010-inspired quality assurance checklist (Step 7 of `/gse:reqs`)._

| Quality Dimension | Covered? | Requirements | Gaps / Deferred |
|-------------------|----------|--------------|-----------------|
| Performance       |          |              |                 |
| Security          |          |              |                 |
| Reliability       |          |              |                 |
| Usability         |          |              |                 |
| Maintainability   |          |              |                 |
| Accessibility     |          |              |                 |
| Compatibility     |          |              |                 |

## Open Questions

_Questions that need resolution before requirements are finalized._

1. {question}
