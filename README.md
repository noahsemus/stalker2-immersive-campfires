# Campfire Actions (S.T.A.L.K.E.R. 2)

Lets Skif eat, drink, open the PDA, and inspect artifacts while sitting at a campfire. Vanilla swaps to an exclusive input context on sit, which unmaps every inventory-related key; this mod puts those keys back.

**Status: planning, not built.** See [PLAN.md](PLAN.md) for the analysis and the layered approach. The mod is built entirely in the official S.T.A.L.K.E.R. 2 Zone Kit and ships as a pak; no UE4SS. Layer 1 overrides the `IMC_PlayerCA` input mapping context; Layer 2, only if the game vetoes the mapped actions, adds a Blueprint override of the campfire sit actor that calls the player functions directly.

Toolchain and pipeline template: [stalker2-immersive-dialogue](https://github.com/noahsemus/stalker2-immersive-dialogue) v2.0.0 (`BUILD.md`, `zonekit/`).
