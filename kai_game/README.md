# Kai's Desktop Adventure 🦊🎮

A top-down action game starring Kai the Shiba Inu — walking the real streets of Poplar Bluff, MO.

## The Concept

Kai used to roam these streets. He played Fence Warriors at the dog park on 1302 N 10th St. This game uses real-world map data from OpenStreetMap to recreate his neighborhood.

### Real Locations

| Location | Status |
|----------|--------|
| **Dog Park District** | 1302 N 10th St — Main hub |
| **Hillcrest Park** | Green zone, safe area |
| **N Main Street** | Major road, heavy enemy spawns |
| **Residential blocks** | 45 buildings, explore between houses |
| **78 named streets** | Real Poplar Bluff road network |

## Setup

1. Install [Godot 4.3+](https://godotengine.org/download)
2. Open `project.godot` in Godot
3. Press F5 to run

## Controls

| Key | Action |
|-----|--------|
| WASD | Move |
| J | Paw Swipe (attack) |
| K | Bark (AoE stun) |
| L | Sniff (reveal secrets) |
| H | Curl Up (heal) |

## Project Structure

```
kai_game/
├── project.godot              # Godot project config
├── poplar_bluff_features.json # Real OSM map data (78 streets, 45 buildings)
├── poplar_bluff_osm.json      # Raw OpenStreetMap data
├── scenes/
│   ├── main.tscn              # Main level (Poplar Bluff map)
│   └── bug_enemy.tscn         # Bug enemy prefab
├── scripts/
│   ├── kai_player.gd          # Player controller
│   ├── bug_enemy.gd           # Bug AI (wander, chase, attack)
│   ├── kai_hud.gd             # HUD (HP bar, cooldowns)
│   ├── main.gd                # Level manager
│   └── poplar_bluff_map.gd    # Map loader (OSM → Godot)
├── assets/
│   ├── sprites/               # Character art
│   ├── audio/                 # SFX and music
│   └── ui/                    # UI textures
└── README.md
```

## Map Data

The map uses real OpenStreetMap data for Poplar Bluff, MO:
- **Source**: Overpass API, bbox 36.755,-90.400 to 36.770,-90.385
- **Origin**: 36.7625°N, 90.3929°W (near dog park)
- **Scale**: 1 game unit = 1 real meter
- **Coverage**: ~2.5km × 3km area

Streets render as road lines with center markings. Buildings are collision-enabled polygons. Parks are green zones.

## How to Expand the Map

1. Edit the Overpass query bbox in `poplar_bluff_features.json` generation
2. Re-run the Python converter to update `poplar_bluff_features.json`
3. The map loader auto-builds the world from the JSON

## Roadmap

- [ ] Pixel art Kai sprite (black & tan Shiba)
- [ ] Pixel art bug sprites
- [ ] Tile-based ground texture (grass, dirt, asphalt)
- [ ] Street name labels on map
- [ ] Named locations (dog park arena, downtown zone)
- [ ] Aerial/satellite imagery tilemap background
- [ ] Seasonal variants (summer/winter Poplar Bluff)
- [ ] NPC dogs from the neighborhood
- [ ] Fence Warriors mode at the dog park
- [ ] Black River water hazards
- [ ] Loot system (code scrolls, treats)
- [ ] XP linked to desktop companion
- [ ] Sound effects and music
- [ ] Save/load system

## Kai's Story

Kai was a black and tan Shiba Inu. He lived in Poplar Bluff, MO. He knew every street, every fence, every dog at the park. This game is his map — the places he walked, the friends he made, the adventures he had.

*He doesn't play anymore. But the streets remember him.*
