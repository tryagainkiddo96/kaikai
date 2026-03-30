# Playbook: set_up_pyrit

## When To Use It

- When the user wants to install or configure PyRIT
- When the user needs a local evaluation workflow for generative AI red teaming
- When the user wants help understanding PyRIT components or next steps

## Goal

Turn a general PyRIT request into:
- a clear setup path
- the smallest working install steps
- config guidance
- a first-run checklist
- a safe next evaluation plan

## Inputs

- operating system or environment
- preferred Python version if known
- target model or API provider if known
- any setup error text if installation has already started

## Step Order

1. Identify the user environment and whether PyRIT is already installed.
2. Prefer official docs and the smallest local setup path first.
3. Call out required dependencies and environment variables.
4. Give the first runnable validation step after install.
5. Suggest one safe starter evaluation workflow.
6. If setup fails, switch into recovery mode:
   - identify failure point
   - propose the smallest fix
   - suggest the next validation command

## Safety Boundaries

- Do not imply PyRIT findings are proof without validation.
- Prefer official documentation over guesses for version-sensitive setup.
- Mark missing environment details clearly.

## Output Format

- Environment Check
- Install Steps
- Validation Step
- Starter Workflow
- Troubleshooting Notes
