# Kai's Desktop Adventure 🦊🎮

A top-down action game starring Kai the Shiba Inu.

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
├── project.godot          # Godot project config
├── scenes/
│   ├── main.tscn          # Main level scene
│   └── bug_enemy.tscn     # Bug enemy prefab
├── scripts/
│   ├── kai_player.gd      # Player controller (movement, abilities)
│   ├── bug_enemy.gd       # Bug AI (wander, chase, attack, stun)
│   ├── kai_hud.gd         # HUD (HP bar, cooldowns)
│   └── main.gd            # Level manager (spawning, waves)
├── assets/
│   ├── sprites/           # Placeholder → real sprites
│   ├── audio/             # SFX and music
│   └── ui/                # UI textures
└── README.md
```

## Abilities

| Ability | Key | Cooldown | Effect |
|---------|-----|----------|--------|
| Paw Swipe | J | 0.4s | Melee attack, 10 dmg |
| Bark Signal | K | 3.0s | AoE stun in 150px radius |
| Sniff Out | L | 2.0s | Reveal hidden items in 200px |
| Paw Shield | H | 8.0s | Heal 20 HP over 1 second |

## Roadmap

- [ ] Sprite art for Kai (black & tan Shiba)
- [ ] Sprite art for bugs
- [ ] Procedural dungeon generation
- [ ] Multiple biomes (File Forest, Cache Desert, Network Ocean)
- [ ] Boss fights (Memory Leak, Kernel Panic)
- [ ] Loot system (code scrolls, refactor tools)
- [ ] XP system (linked to desktop companion game state)
- [ ] Sound effects and music
- [ ] Save/load system

## Notes

Uses placeholder textures for now — run the game and you'll see colored shapes.
Replace with real sprites when ready.
