# README Rewrite Brief — infrahub-skills

This document captures the context, decisions, and requirements for rewriting the `infrahub-skills` README. It synthesizes discussions from multiple meetings and stakeholder input. Use this as the primary reference when iterating on the README.

## Background

The infrahub-skills repo is a Claude Code plugin (also usable with Copilot, Cursor, Windsurf) that provides 8 AI skills for Infrahub development. The current README is installation-focused and lists skills with verbose capability bullets. It needs to be rewritten to lead with workflows, serve three distinct user personas, and introduce speckit as the planning layer for complex work.

## Two Repos in Play

- **infrahub-skills** (`github.com/opsmill/infrahub-skills`) — the Claude Code plugin with 8 skills. This is the repo whose README we're rewriting.
- **infrahub-template** (`github.com/opsmill/infrahub-template`) — the project template users start from. It has speckit pre-configured with Infrahub-specific templates, a constitution (governance rules + skill routing table), and workflow-specific spec templates. The README should reference this repo for speckit setup.

## User Personas

From the March 13, 2026 meeting (Phillip, Yvonne, Mikhail) and Confluence product docs:

1. **Tire Kicker (Beginner)** — New to Infrahub, exploring capabilities. Installing the tool to ask questions, bootstrap a schema, understand what's possible. Won't invest a ton of time upfront. Needs the fastest possible path to value. Direct mode is their entry point.

2. **Implementer** — Building features, going from rough prototype to concrete data model and working infrastructure. Planning mode (speckit) is critical for this persona. They need the agent to reason before building so they don't end up debugging incorrect relationship cardinality or missing generator patterns.

3. **Existing User (Up and Running)** — Already in production. Primary use case is iterating on existing features, using planning mode for refinement or new feature requests. Also uses the skill for building integrations (e.g., writing a diffconfig to ingest data from external spreadsheets).

## The Two-Tier Workflow

From the March 16, 2026 sync (Phillip + Alex):

### Direct Mode — Simple requests go straight to Claude skills
User asks Claude to do something straightforward, the right skill handles it. No planning ceremony.

**Examples:**
- "Add a contract_start_date attribute to InfraCircuit"
- "Create a check that validates every device has a primary IP"
- "Add a menu section for IP address management"

### Speckit Mode — Complex work goes through speckit, which routes to Claude skills
For multi-step or architecturally significant work, use speckit's specify → plan → tasks → implement pipeline. The planning step validates design artifacts against Infrahub skills before any code is written.

**Examples:**
- Designing a new schema node with relationships to existing models
- Building a cascading generator chain
- Standing up a complete new domain (schema + objects + checks + generators)

**Key insight:** The boundary isn't about user skill level — it's about task complexity. An experienced user adding an attribute still uses direct mode. A beginner designing their first schema node with relationships should use speckit.

## README Structure (Agreed)

1. **Opening** — One-liner + quick start (plugin install, 3 lines) + first-action nudge
2. **How It Works** — Two subsections: Direct Mode and Speckit Mode, each with concrete examples. Decision table for when to use which.
3. **Skills** — Compact table, one line per skill. No verbose capability lists. Depth lives in the skill directories.
4. **Installation** — Three methods: plugin marketplace, git clone, copy skills.
5. **Other AI Tools** — Brief section on Copilot, Cursor, Windsurf.
6. **Project Structure** — Tree view.
7. **Resources + License** — Links, Apache 2.0.

## Key Requirements

- **Lead with workflows, not installation.** The two-tier model should be the first thing engineers understand.
- **Reference speckit by name.** Link to GitHub Spec Kit repo and infrahub-template repo.
- **Be substantive, not fluffy.** All personas are engineers. Unsubstantial descriptions make them look elsewhere. Every sentence should earn its place.
- **Balance simple and technical.** Easy to start, enough depth to understand the what and how.
- **README stays short.** It's a getting-started guide. Longer feature documentation can move to separate pages.
- **Schema-creator description** should emphasize "describe your use case and get best-practice guidance" rather than just listing features. Users should know they can describe what they need and the skill will recommend best practices.
- **Include the decision table** mapping scenarios to Direct vs. Speckit mode — this is the practical guide for engineers.
- **License is Apache 2.0**, consistent across OpsMill public repos.

## Meeting Context Summary

### March 13, 2026 — AI Skills Discussion (Phillip, Yvonne, Mikhail)
- Established the three personas (tire kicker, implementer, existing user)
- Planning mode identified as the key differentiator for complex workflows
- Planning mode is particularly beneficial for the tire kicker persona — lets them interrogate the LLM to understand resource usage and iterative solutions
- Schema creator documentation needs expansion to communicate value to new users (not just "create, validate, modify")
- README should remain short getting-started guide; longer docs can be separate
- Action items: Phillip to revisit README, add Planning Mode section, create demo videos

### March 16, 2026 — Alex / Phillip Sync on Claude Skill
- Defined the two-tier workflow: simple → direct skills, complex → speckit → skills
- Alex created the PR integrating speckit into the infrahub-template repo
- Phillip to record demo shorts using the template repo to build features
- README update in infrahub-skills is the primary deliverable; demo videos follow

### Confluence: AIDC Goals/Brief
- Two personas for the AI/DC bundle map to the same pattern: Evaluator/Learner (tire kicker) and Advanced Implementer
- Documentation should serve both without forcing one group through the other's workflow
- "Design-driven automation" is the conceptual frame — generators, cascading patterns, event-driven architecture

### Confluence: AI Skills Project
- Target announcement ~3-4 weeks from March 13
- README Planning Mode section: in progress (Phillip)
- Demo videos: in progress (Phillip)

## Draft README

A draft README has been written and reviewed. It is located at the root of the infrahub-skills repo as README.md (or provided alongside this brief). The draft has been validated against all requirements above and addresses all three personas, both workflow tiers, and the speckit integration.

### Review feedback addressed:
- Added first-action nudge after install block for tire kickers
- Updated schema-creator description to emphasize best-practice guidance
- Added note that direct mode is how most people start
