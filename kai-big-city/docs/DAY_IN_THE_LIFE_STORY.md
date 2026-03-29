# Day In The Life Of Kai

## Core Tone

A playful, sentimental, neighborhood adventure inspired by real Shiba behavior and memories.

## Chapter Flow

1. Morning: Home Turf
- Kai starts near home block.
- Goal: complete the home routine, then begin the N Tenth route.
- Routine sequence:
  - check window
  - eat breakfast
  - grab leash
  - head to front door
- Mood: calm routine, leash energy, first bark of the day.

2. Midday: Neighborhood Walk
- Goal: help the neighbor (missing lunch) and continue to dog park gate.
- Includes route landmarks from the memory path.
- Mood: social, curious, local.

3. Dog Park Saga
- Goal: trigger a fence-line stand-off or win squirrel chase.
- Companions show personality:
  - Kai: chaotic jukes.
  - Yuki: flank and scavenge.
  - Saiya: sentry and pursuit.
- Mood: loud, funny, unpredictable.

4. Evening Return
- Goal: return home after park events.
- Day resolves with earned calm and companionship.
- Mood: warm closure.

## Dynamic Event: "Come Inside"

- Randomly triggers near home area.
- Human appears and calls Kai inside.
- Kai can fake out, juke, and loop.
- Outcomes:
  - caught: snap back to home.
  - evade timer: human gives up.

## Narrative Design Rules

- Keep map inspired by real places, but stylized and privacy-safe.
- Make objectives dog-motivated, not human-task-only.
- Let mechanics tell story: barking, sniffing, flanking, fence rallies, chase loops.
- Preserve light humor and emotional authenticity in hints and event text.

## Runtime Systems (Current Build)

- Encounter Director:
  - global pacing tier (`calm`, `active`, `hot`, `chaos`)
  - drives event rates for fence stand-offs and home-call chases
- Encounter Director v2 mission arcs:
  - `Peace Walk` (no bark calm challenge)
  - `Sentry Hold` (guard-mode discipline challenge)
  - `Patrol Loop` (route checkpoint challenge)
  - earns operations points and influences park reputation
- Dog Park Reputation:
  - shifts between `Friendly`, `Neutral`, `Tense`, `Rival`
  - changes rival-dog fence behavior and park pressure feel
- End-of-Day Recap:
  - summarizes treats, chases, rare finds, reputation, and companion affinity

## House Slice (Current Build)

- Stylized playable home interior is now generated at runtime around the home-start area:
  - floor/ceiling/walls with front-door opening
  - couch, table, bed, counter, rug, photo wall
- Morning routine anchors are integrated inside this space:
  - window watch
  - breakfast bowl
  - leash hook
  - front door threshold
