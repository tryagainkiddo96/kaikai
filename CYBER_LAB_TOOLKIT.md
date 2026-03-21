# Kai Authorized Cyber Lab Toolkit

This reference is for defensive learning, lab work, and explicitly authorized security testing only.

## Core Tools

### Nmap
- Role: host discovery and service enumeration in authorized environments
- Best fit for Kai: explain scan types, suggest low-impact discovery first, summarize output, propose the next safe command
- Official docs:
  - https://nmap.org/docs.html
  - https://nmap.org/book/

### Wireshark
- Role: packet capture analysis and protocol troubleshooting
- Best fit for Kai: explain captures, filters, protocol flows, and troubleshooting steps from pcaps or screenshots
- Official docs:
  - https://www.wireshark.org/docs/
  - https://www.wireshark.org/docs/wsug_html/

### OWASP ZAP
- Role: web app security testing in owned or authorized applications
- Best fit for Kai: help with setup, passive scanning, interpreting findings, and safe lab workflows
- Official docs:
  - https://www.zaproxy.org/docs/
  - https://www.zaproxy.org/getting-started/

### Ghidra
- Role: reverse engineering and binary analysis
- Best fit for Kai: setup help, project organization, and interpreting analysis workflow in malware labs or software research you are allowed to perform
- Official docs:
  - https://www.nsa.gov/ghidra/
  - https://ghidradocs.com/

## Kai Guidance

- Start with explanation and low-impact observation before active actions.
- Prefer official documentation for technical questions.
- Treat scans or probes as higher-risk actions that need explicit authorization.
- Save only durable takeaways:
  - successful install steps
  - common fixes
  - preferred lab workflows
  - safe command patterns

## Suggested Future Skills

- `summarize_nmap_output`
- `explain_wireshark_capture`
- `triage_zap_setup`
- `ghidra_project_setup`
- `authorized_lab_scope_check`
