# Kai Playbooks Hub

## Current Playbooks

### triage_garak_results
- File: `KAI_PLAYBOOK_TRIAGE_GARAK.md`
- Use when: you want Kai to turn raw garak scanner output into a readable triage
- Trigger:
  - `triage garak results: ...`

### set_up_pyrit
- File: `KAI_PLAYBOOK_SETUP_PYRIT.md`
- Use when: you want help installing or configuring PyRIT
- Trigger:
  - `setup pyrit: ...`
  - `install pyrit: ...`

### summarize_art_findings
- File: `KAI_PLAYBOOK_SUMMARIZE_ART_FINDINGS.md`
- Use when: you want ART robustness output summarized into risks and next steps
- Trigger:
  - `summarize art findings: ...`

## Planned Major Upgrades

1. Playbooks Hub UI
- Browse and launch playbooks directly from the panel

2. Structured Logging
- Track requests, tool use, command proposals, executions, failures, and outcomes

3. Recovery Mode
- Automatically switch into a failure analysis and smallest-fix workflow when something breaks
