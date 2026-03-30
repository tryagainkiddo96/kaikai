# Kai Runtime Candidate

Status:
- Deprecated transition note only.
- Do not use this asset as the active Kai runtime identity.

Source:
- Built from `kai_texture_workspace.blend`
- Uses the existing `Mesh_0` Kai likeness mesh and material

Export:
- `kai_runtime_candidate.glb`
- Historical decimation experiment retained for comparison only

Notes:
- Source mesh vertex count: about 519,942
- Runtime candidate vertex count: about 130,473
- Shape and proportions are preserved much better than the low-poly fallback
- Still unrigged, so safest use is as a static or container-animated mesh, not a full skeletal animation replacement yet

Historical integration note:
- This candidate is archived for comparison only.
- Keep the active runtime on `kai_textured.glb` until `kai_textured_rigged.glb` is validated.
- If performance work is needed again, treat this file as a reference branch rather than a live fallback.
