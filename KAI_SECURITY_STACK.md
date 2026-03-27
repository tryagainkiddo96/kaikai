# Kai-Compatible Security Stack

This stack is for defensive work, learning, troubleshooting, and explicitly authorized lab environments only.

## Safe To Add

### Wireshark
- Best fit: packet analysis, filters, protocol explanation, troubleshooting
- Good Kai role: explain captures, suggest filters, summarize traffic patterns
- Official docs:
  - https://www.wireshark.org/docs/
  - https://www.wireshark.org/docs/wsug_html/

### OWASP ZAP
- Best fit: setup help, passive scanning, interpreting findings on owned or authorized web apps
- Good Kai role: guide safe lab workflows and explain findings
- Official docs:
  - https://www.zaproxy.org/docs/
  - https://www.zaproxy.org/getting-started/

### Ghidra
- Best fit: reverse engineering education, binary analysis, malware lab workflows you are authorized to run
- Good Kai role: setup help, workflow explanation, project organization
- Official docs:
  - https://www.nsa.gov/ghidra/
  - https://ghidradocs.com/

### IBM ART
- Best fit: AI/ML robustness and adversarial testing, not standard network/web pentesting
- Good Kai role: explain model robustness workflows and testing concepts
- Official docs:
  - https://adversarial-robustness-toolbox.org/
  - https://research.ibm.com/projects/adversarial-robustness-toolbox

## Maybe Later

### PentestGPT
- Good as an architecture reference for planning, execution, and reasoning loops
- Not the best choice to merge directly into Kai
- Official source:
  - https://github.com/GreyDGL/PentestGPT

### Pentera
- Enterprise platform, better treated as a separate product than a Kai plugin
- Official source:
  - https://pentera.io/

### Aikido Security
- More AppSec platform than local Kai tool
- Useful as product inspiration, not a direct local integration target
- Official source:
  - https://www.aikido.dev/

## Not Appropriate To Wire Into Kai

- Offensive MCP servers
- Autonomous exploit frameworks
- Tools built around arbitrary attack execution against targets

## Recommended Kai Security Direction

- Official-docs knowledge packs
- Verified web research
- Recovery mode
- Structured logging
- Safe lab playbooks
- Clear authorization checks for higher-risk actions
