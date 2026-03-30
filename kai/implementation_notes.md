# Kai Separation Notes

The imported `W0rm-Gpt-main` app is now isolated under `external/W0rm-Gpt-main/`.

Kai-specific UI concepts that had briefly been added to that app were extracted and preserved here instead:

- `companion_model.py`
  - top-level Kai intents
  - capability groups for a "What Kai Can Do" panel
  - rotating discovery prompts
  - starter prompt mappings

## Recommended Kai interaction structure

- `Left click`
  - open a small chat/help bubble
- `Right click`
  - open a compact menu with `Build`, `Learn`, `Focus`, `Relax`, `Customize`, and `More`
- `More`
  - open a full capabilities panel with concrete example actions

## Why this structure

- keeps Kai companion-like instead of button-heavy
- showcases abilities through examples instead of dumping everything at the top level
- preserves room for outfits, vibes, and contextual prompts without overcrowding the shell

## Next implementation step

Build Kai as its own shell inside `kai/`, then consume `companion_model.py` from that code instead of embedding Kai behavior in imported projects.
