Temporary avatar spec for the current Kai companion placeholder:

- realistic male Shiba Inu
- black and tan coat
- white or cream chest, muzzle, and paw markings
- clean silhouette suitable for desktop companion presentation

Current runtime asset order:

- `kai_textured_rigged.glb`
  Primary Godot runtime avatar.
- `kai_textured.glb`
  Unrigged fallback if the rigged export is unavailable.
- `kai-lite.glb`
  Lightweight emergency fallback.

`modelToUsed.glb` remains the source mesh for the texture workspace and Blender pipeline. It is not the preferred runtime companion asset anymore.

Available fallback:

- `kai-lite.glb` from Poly Pizza's Black Shiba Inu model, chosen because it is much lighter for desktop companion rendering.
