# Kai Completion Checklist

## Core Stability

- [ ] Transparent desktop window is stable with no tracers, ghosting, duplicate layovers, or visible boxed viewport.
- [x] Only one visible avatar/render path is active at runtime.
- [ ] Native Windows window handling is verified and kept only if it improves stability.
- [ ] Launch/relaunch behavior is consistent and does not leave stale Kai windows or helper processes behind.

## Realistic 3D Avatar

- [ ] Restore the most realistic Kai-shaped 3D model that can run stably on desktop.
- [ ] Keep the model fully in frame at the shipped window size.
- [ ] Eliminate patchy or obviously broken coat/material rendering.
- [ ] Match Kai’s black-and-tan Shiba silhouette more closely than the low-poly fallback.

## Likeness

- [ ] Tighten head, muzzle, ear, and chest silhouette toward Kai’s photo/video references.
- [ ] Prioritize face shape, posture, and body language over perfect texture detail.
- [ ] Keep Shiba-specific expression and behavior at the center of every animation/state.

## Behavior

- [ ] Remove unnatural bouncing or floating motion.
- [ ] Keep idle, alert, curious, thinking, and resting states readable and dog-like.
- [ ] Fix bark timing so audio only happens on clear actions/events.
- [ ] Keep mouse attention and desktop interaction feeling intentional, not chaotic.

## Presentation

- [ ] Bubble/chat UI remains usable without breaking the avatar presentation.
- [ ] Dragging the companion works cleanly.
- [ ] Companion feels like it lives on the desktop rather than inside a visible app window.

## Verification

- [x] Headless parse/load validation passes.
- [ ] Live Windows launch check passes.
- [ ] Peer review confirms the task state before calling Kai complete.
