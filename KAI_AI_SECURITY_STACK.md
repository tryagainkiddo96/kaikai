# Kai AI Security Stack

This stack is for evaluating and improving the safety of AI systems, especially LLMs and ML models.

## Best Fit For Kai

### PyRIT
- Full name: Python Risk Identification Tool
- Best fit: automating red teaming tasks against generative AI systems
- Good Kai role: explain setup, guide evaluations, summarize findings, compare prompt attack results
- Official sources:
  - https://github.com/Azure/PyRIT
  - https://azure.github.io/PyRIT/

### garak
- Best fit: broad LLM vulnerability scanning
- Good Kai role: help configure probes, interpret results, and turn scanner output into remediation steps
- Official sources:
  - https://github.com/NVIDIA/garak
  - https://garak.ai/

### Adversarial Robustness Toolbox (ART)
- Best fit: evaluating and defending ML systems against adversarial attacks
- Good Kai role: explain robustness workflows, suggest evaluation patterns, and summarize model-risk results
- Official sources:
  - https://adversarial-robustness-toolbox.org/
  - https://research.ibm.com/projects/adversarial-robustness-toolbox

## Maybe Later

### Mindgard
- Better as an external platform alongside Kai than a direct local integration
- Good Kai role: explain findings or workflows if you use the platform
- Official source:
  - https://mindgard.ai/

## Not Added Right Now

### PentestAI
- I did not find a strong enough official primary source to confidently add it as a Kai recommendation.
- If you have the exact official repo or docs link, we can review it and place it properly.

## Recommended Kai Direction

- Verified AI-security research from official docs
- Local playbooks for:
  - `triage_garak_results`
  - `set_up_pyrit`
  - `summarize_art_findings`
- Save only durable takeaways:
  - successful install steps
  - model-specific caveats
  - repeated failure modes
  - remediation patterns that worked
