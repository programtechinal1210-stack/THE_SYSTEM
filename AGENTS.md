# AGENTS.md — THE_SYSTEM Project Management Rules

Before modifying Project Management code, read:

1. `docs/pm/00_PM_READ_FIRST.md`
2. `docs/pm/01_PM_FINAL_DOMAIN_ANALYSIS.md`
3. `docs/pm/03_PM_SOURCE_OF_TRUTH.md`
4. `docs/pm/05_PM_INTEGRATION_BOUNDARIES.md`
5. `docs/pm/06_PM_EXECUTION_PLAN.md`

## Mandatory rules

- Preserve Core boundaries.
- `module_daily_work` is not inside PM.
- `module_continuous_improvement` is not inside PM.
- WEP and Work Orders are inside PM.
- Planned, Weekly Committed, Daily Committed, and Actual are different truths.
- Do not create a second Actual source.
- Use UUID/FK internally and preserve Business Keys.
- Do not copy legacy tables 1:1 without the migration map.
- Do not let Core depend on PM business code.
- Apply permission + scope + audit from the first endpoint.
- Every batch follows Discovery → Backup → Implementation → Targeted Tests → Full Regression → Certification.
- Stop on a red gate. Do not stack speculative patches.

## Current certified state

- EX-00: complete / green.
- PM-00: complete / green (implementation and isolated migration/restore certified; see evidence/PM-00/certification.json; not live deployment).
- CORE-01: complete / green (Core contracts — currency service, soft-delete, permission catalog; isolated test certified; see evidence/CORE-01/certification.json; not live deployment).
- PM-01: complete / green (planning core — projects/phases/tasks/activities/requirements, Decimal/FX snapshots, scoped owner-dispatched recycle; isolated test certified; see evidence/PM-01/certification.json; not live deployment).
- PM-02: complete / green (master plan baseline snapshots + activity dependencies with cycle prevention; project members and change requests deferred; isolated test certified; see evidence/PM-02/certification.json; not live deployment).
- PM-03: complete / green (governance/control — risks, deviations, cash flow, communications, daily reports; lifecycle + Decimal FX snapshots + scoped owner-dispatched recycle; isolated test certified; see evidence/PM-03/certification.json; not live deployment).
- PM-04: complete / green (execution — work orders + consumptions + immutable quantity events + derived actual cost; WO state machine; isolated test certified; see evidence/PM-04/certification.json; not live deployment).
- PM-05: implementation present; source-contract hardening validated (see evidence/PM-05/hardening/). Original certification is historical: full acceptance remains pending readiness, Daily Work fallback, unplanned flow and item dates. Operational UI: see evidence/PM-UI/.
- PM-06: reporting remediation and UI implemented in part; see evidence/PM-06/remediation/REPORT.md and certification.json. Do not assume full reporting or release certification from regression success.
- MIG: experimental legacy data migration deferred explicitly by the user; prioritize complete interfaces. Historical discovery in evidence/MIG-00 is not a blocker for UI work. No import or guessed ownership.
- Confirm repository evidence before assuming later batches are complete.


- CORE-01-hardening: Decimal currency and scoped owner-dispatched recycle contracts certified; see evidence/CORE-01-hardening/certification.json. Currency JSON decimals are strings; modules must register recycle handlers before exposing deleted entities.

- PM-UI: nine operational sections and scoped section project selectors implemented; HTTP acceptance and 93-test regression pass. Browser visual review unavailable, not certified. See evidence/PM-UI/REPORT.md. Full plan capability gaps remain explicit.

- PM-UI-REFERENCE: source-layout adaptation implemented (cards, planning hierarchy, execution header, weekly panes, reporting KPIs, form dialogs). 93-test regression and HTTP E2E pass. Full reference parity NOT certified: missing backend workflow contracts and unavailable browser visual verification; see evidence/PM-UI-REFERENCE/REPORT.md.
