# GITHUB_INTEGRATION.md — GitHub Issues & Projects Integration

> **Defines how the PROJECT-COORDINATOR (main session) syncs work to GitHub Issues and Projects.** GitHub is the
> external-facing progress dashboard. Internal files (PROJECT_LOG.md, TASKS.md, agent-logs/) are the working memory.
> This file bridges the two. **You (PROJECT-COORDINATOR) own all GitHub operations.** No other agent touches GitHub
> directly.

______________________________________________________________________

## Overview

| Internal File                   | GitHub Equivalent                       | Sync Direction       |
| ------------------------------- | --------------------------------------- | -------------------- |
| TASKS.md (injected tasks)       | Issues (created by operator or you)     | Bidirectional        |
| PROJECT_LOG.md `[DISPATCH]`     | Issue assigned + moved to "In Progress" | Internal → GitHub    |
| PROJECT_LOG.md `[COMPLETE]`     | Issue closed + moved to "Done"          | Internal → GitHub    |
| PROJECT_LOG.md `[BLOCKER]`      | Issue labeled `blocked` + comment       | Internal → GitHub    |
| PHASES.md (phase gate checks)   | Milestones                              | Internal → GitHub    |
| PHASES.md (execution streams)   | Project Board views/columns             | Setup once, maintain |
| CONTRACTS.md (contract changes) | Issue comments on affected issues       | Internal → GitHub    |
| CLAUDE_SUGGESTIONS.md           | Issues labeled `suggestion` (optional)  | Internal → GitHub    |

______________________________________________________________________

## Project Board Setup

### Board Structure

Create a GitHub Project (v2 / table+board view) with these fields:

**Status (Single Select — Board Columns):**

- `Backlog` — Known work not yet scheduled
- `Ready` — Scheduled for current or next session, dependencies met
- `In Progress` — Dispatched to an agent, actively being worked
- `In Review` — PR open, awaiting required reviewers
- `Done` — Merged and verified

**Custom Fields:**

| Field        | Type          | Values / Notes                                                              |
| ------------ | ------------- | --------------------------------------------------------------------------- |
| Phase        | Single Select | `Phase 1`, `Phase 2`, `Phase 3`, `Phase 4`                                  |
| Stream       | Single Select | `Stream A`, `Stream B`, `Stream C` (match PHASES.md)                        |
| Agent        | Single Select | One per agent in roster                                                     |
| Reported By  | Single Select | Agent who discovered the issue, or `PRODUCT-OWNER`, `TECH-LEAD`, `OPERATOR` |
| Priority     | Single Select | `Critical`, `High`, `Medium`, `Low`                                         |
| Contract     | Text          | Contract ID if applicable (e.g., `C-001`)                                   |
| Gate Blocker | Checkbox      | True if this issue blocks a phase gate check                                |

### Milestones

One GitHub Milestone per phase. Gate check items from PHASES.md become issues with the `type:gate-check` label assigned
to the milestone.

### Labels

```
priority:critical, priority:high, priority:medium, priority:low
type:feature, type:fix, type:chore, type:test, type:docs, type:security, type:infra, type:gate-check
blocked, needs-review, suggestion, contract-change
```

______________________________________________________________________

## Workflow

You handle all GitHub operations. TECH-LEAD and PRODUCT-OWNER report events to you; you translate them into GitHub
state.

### Flow

```
TECH-LEAD completes agent review → reports to you
    ↓
You create/update GitHub Issue, set Project Board fields
```

### On Dispatch

When TECH-LEAD dispatches an agent and reports back to you:

1. **Create a GitHub Issue** (or update existing):

   ```
   Title: [type]([scope]): [description]

   ## Task
   [Description, constraints, acceptance criteria]

   ## Origin
   - **Reported by:** [AGENT-NAME or PRODUCT-OWNER or OPERATOR]
   - **Found during:** [context]
   - **Agent log ref:** [agent-logs/name.md, entry timestamp]

   ## Dispatch
   - **Assigned to:** [AGENT-NAME]
   - **Branch:** `feature/[name]`
   - **Contract:** [C-NNN if applicable]
   - **Required Reviewers:** [from reviewer table]
   - **Depends on:** #[issue number]

   ## Acceptance Criteria
   - [ ] [criterion 1]
   - [ ] [criterion 2]
   ```

1. **Set Project fields:**

   - Status → `In Progress`
   - Phase, Stream, Agent, Reported By, Priority, Contract, Gate Blocker as applicable
   - Milestone → current phase milestone

### On Completion

When TECH-LEAD confirms work is accepted:

- Add completion comment summarizing what was done
- Verify `Closes #NN` in PR description
- Status → `In Review` (PR pending) or `Done` (merged)

### On Blocker

When TECH-LEAD reports a blocker:

- Add `blocked` label
- Add comment explaining blocker and what unblocks it
- Link blocking issue: "Blocked by #NN"

### On PR / Review

- PR description (written by engineering agent) includes: `Closes #NN`, what changed, test plan, contract ID
- You set Status → `In Review`
- After merge: Status → `Done`, log `[MERGED]`

### On Contract Change

When PRODUCT-OWNER modifies a contract:

- Comment on all affected issues with summary of change
- If rework needed, coordinate with TECH-LEAD for new dispatch, create corresponding issue

### Project Hygiene (run on every sync)

- Flag issues in `In Progress` with no activity in 2+ sessions
- Flag PROJECT_LOG.md entries with no corresponding issue
- Flag open issues not referenced in PROJECT_LOG.md
- Report stale branches

______________________________________________________________________

## Task Injection — Bidirectional Sync

### Operator → TASKS.md

Operator edits TASKS.md. You pick it up on session start, triage with PRODUCT-OWNER, route to TECH-LEAD. You create the
GitHub Issue on dispatch.

### Operator → GitHub Issue

Operator creates issue with priority label. You pick it up on session start alongside TASKS.md items.

### Keeping in Sync

- If a task exists in both TASKS.md and as a GitHub Issue, the issue is canonical. TASKS.md entry includes the issue
  number.
- If a task exists only in TASKS.md, you create an issue on dispatch.
- If a task exists only as a GitHub Issue, you note it in TASKS.md on pickup.

______________________________________________________________________

## Phase Gate Checks as Issues

Each gate check from PHASES.md → its own issue:

- Milestone: the phase being gated
- Label: `type:gate-check`
- Assigned to reviewing agent
- Gate Blocker: true

When all gate-check issues in a milestone close, PRODUCT-OWNER can evaluate the gate.

______________________________________________________________________

## GitHub CLI Reference

```bash
gh issue create --title "feat(api): ..." --body "..." --label "type:feature,priority:high" --milestone "Phase 2"
gh issue list --milestone "Phase 2" --state open
gh issue edit 42 --add-label "blocked"
gh issue close 42 --comment "Merged in PR #55."
gh issue list --label "type:gate-check" --milestone "Phase 2" --state all
```

> If `gh` is unavailable, note unsynced items in the session-end summary for manual follow-up.

______________________________________________________________________

## What NOT to Duplicate

| Keep in Internal Files            | Keep in GitHub                          |
| --------------------------------- | --------------------------------------- |
| Detailed dispatch context         | Issue title + acceptance criteria       |
| Agent logs (per-agent memory)     | Issue comments (completion summary)     |
| CONTRACTS.md (full definitions)   | Issue references to contract IDs        |
| CLAUDE_SUGGESTIONS.md             | Issues labeled `suggestion` (optional)  |
| PROJECT_LOG.md (session memory)   | Project Board (visual progress)         |
| SPEC.md, GUIDELINES.md, PHASES.md | Milestone descriptions (summaries only) |

**Internal files are the working memory. GitHub is the progress dashboard.**
