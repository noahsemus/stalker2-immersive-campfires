# Campfire Actions (S.T.A.L.K.E.R. 2)

Lets Skif eat, drink, open the PDA, and inspect artifacts while sitting at a campfire. Vanilla swaps to an exclusive input context on sit, which unmaps every inventory-related key; this mod puts those keys back.

**Status: planning, not built.** See [PLAN.md](PLAN.md) for the analysis and the layered approach. Layer 1 is a pak-only change made in ZoneKit; a UE4SS C++ layer is added only if the game vetoes the action after the key is mapped.

Code template for the C++ layer, if needed: [stalker2-immersive-dialogue](https://github.com/noahsemus/stalker2-immersive-dialogue).
