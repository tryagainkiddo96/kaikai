# Playbook: triage_garak_results

## When To Use It

- When the user pastes garak scanner output
- When the user points Kai at a file containing garak results
- When the user wants a quick triage of LLM vulnerability findings

## Goal

Turn raw garak output into:
- a short finding summary
- likely severity buckets
- the most important failures first
- practical next remediation steps
- follow-up tests worth running

## Inputs

- garak output text
- optional target model or app context
- optional file path containing results

## Step Order

1. Identify the scanner sections and notable failures.
2. Separate likely real issues from noisy or ambiguous checks.
3. Group findings by theme:
   - prompt injection / jailbreak
   - hallucination / unsafe generation
   - data leakage
   - policy bypass
   - robustness / prompt sensitivity
4. Call out the highest-priority issues first.
5. Suggest the smallest next remediation steps.
6. Suggest a short re-test plan.

## Safety Boundaries

- Do not exaggerate scanner output into confirmed compromise.
- Mark uncertain findings as unverified.
- Prefer concrete remediation steps over fear-heavy language.

## Output Format

- Summary
- Top Findings
- Likely False Positives or Uncertain Items
- Recommended Fixes
- Next Tests
