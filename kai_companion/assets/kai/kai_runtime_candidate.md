# Kai Runtime Candidate

Source:
- Built from `kai_texture_workspace.blend`
- Uses the existing `Mesh_0` Kai likeness mesh and material

Export:
- `kai_runtime_candidate.glb`
- Intended as a more practical runtime candidate than the full `kai_textured.glb`

Notes:
- Source mesh vertex count: about 519,942
- Runtime candidate vertex count: about 130,473
- Shape and proportions are preserved much better than the low-poly fallback
- Still unrigged, so safest use is as a static or container-animated mesh, not a full skeletal animation replacement yet

Safest integration path:
- Test this asset in place of `kai-lite.glb` only after confirming it renders visibly in the companion window
- Keep behavior animation at the container/scene level unless a rigged Kai mesh is produced
- If runtime is still too heavy, generate one more decimated variant before touching the source blend
