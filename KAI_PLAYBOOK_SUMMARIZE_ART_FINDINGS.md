# Playbook: summarize_art_findings

## When To Use It

- When the user pastes or points Kai at ART results
- When the user wants a readable summary of ML robustness findings
- When the user needs help separating signal from noise in adversarial evaluation output

## Goal

Turn ART output into:
- a concise summary
- likely affected model areas
- the most meaningful findings first
- practical next remediation or validation steps

## Inputs

- ART output text or file path
- optional model type and task
- optional evaluation context such as dataset or attack class

## Step Order

1. Identify the tested model, attack family, and key metrics if present.
2. Highlight the most relevant degradation or failure points.
3. Distinguish confirmed measured changes from interpretation.
4. Group findings by theme:
   - evasion robustness
   - extraction or inference risks
   - poisoning or training risks
   - privacy or membership-inference risks
5. Propose the smallest useful next validation or hardening step.

## Safety Boundaries

- Do not overstate robustness from a narrow test.
- Do not confuse one metric drop with total model failure.
- Say when important experiment context is missing.

## Output Format

- Summary
- Key Metrics or Signals
- Top Risks
- Uncertain or Missing Context
- Recommended Next Steps
