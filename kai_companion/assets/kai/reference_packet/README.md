# Kai Reference Packet

This folder is the canonical reference source for future Kai avatar rebuilds.

Current status:
- `non_canonical`
- The runtime avatar still depends on placeholder/adapted mesh lineage.
- This packet is the starting point for replacing that lineage with a Kai-derived build.

Required inputs for a canonical Kai rebuild:
- front standing photo
- left standing photo
- right standing photo
- rear standing photo
- 3/4 head close-up
- top/back reference if available
- resting pose reference
- short video clips with timestamps for gait and posture

Required derived artifacts:
- `proportions.md`
- `provenance.json`
- `markings_notes.md`

Acceptance gates before a model is considered canonical:
- silhouette overlays match front/side references
- coat marking placement matches notes and source photos
- exported runtime mesh comes from one master asset lineage
- runtime does not rely on forced global albedo override
- required animation clips exist on the canonical rigged asset
