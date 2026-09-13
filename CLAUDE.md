# Campfire Actions — project context for Claude

Purpose: S.T.A.L.K.E.R. 2 (UE5.5) mod that lets the player eat, drink, open the PDA, and inspect artifacts while seated at a campfire. Sibling of `stalker2-immersive-dialogue`; that repo is the code template for any UE4SS C++ work here.

Current state: **planning, nothing built.** Read `PLAN.md` first.

## Key facts (verified against ZoneKit on 2026-09-12)
- Campfire sit = `PlayerContextualAction` actor + `PC.contextual_action` bool + input context `IMC_PlayerCA` at priority Exclusive.
- `InputMappingContextPrototypes.cfg:294-298` (under `G:\Epic Games\STALKER2ZoneKit\Stalker2\Content\GameLite\GameData\`) is the IMC entry. Do not lower its priority; add mappings to the `IMC_PlayerCA` asset instead.
- `PC` class members: `G:\Epic Games\STALKER2ZoneKit\bp_api_dump2.txt` from line 5141. Gate candidates: `can_use_inventory` (5153), `contextual_action` (5163), `is_interaction_in_progress` (5218), `is_using_pda` (5224), `is_inspecting_artifact` (5217), `start_use_pda` (5360), `start_use_backpack` (5359), `consume_planned_item` (5162).
- Player-state enums are only in `bp_api_dump.txt` (`PlayerTriggerState` at 5084).

## Rules carried over from ImmersiveDialogue
- **ZoneKit first.** Grep the dumps and cfgs, and ask Noah to open assets in the Mod Editor, before any blind build/test cycle. Most `/Script/Stalker2` classes are C++-only; look for assets that USE them, not the classes.
- **Change discipline.** One surgical diff per build, tested by Noah before the next. No new UE4SS type or function without its own single-purpose test build. `FWeakObjectPtr` crashes this game.
- **Layer order.** Pak-only (Layer 1) before any DLL. Do not start the C++ layer until Layer 1 has been tested in-game and its result recorded here.

## Collaboration workflow (this project only)
Noah is the in-game tester, not a code reader. Claude owns the dev loop: edit, build, install, then tell Noah what to look for in-game and which `UE4SS.log` line or `crash_*.dmp` indicates success or failure. Do not hand Noah build/install commands.

For Layer 1 the split is different: Noah drives ZoneKit (open `IMC_PlayerCA`, add mappings, cook the pak). Claude tells him exactly which Input Actions and key bindings to add and where the cooked pak goes.

If a C++ layer is added, copy the build setup from `stalker2-immersive-dialogue/CLAUDE.md`: Shipping config only (`Game__Shipping__Win64`), RE-UE4SS cloned but never committed, Rust on PATH for patternsleuth, `main.dll` installed to `...\Stalker2\Binaries\Win64\ue4ss\Mods\<ModName>\dlls\`. Check the game is not running (`Stalker2-Win64-Shipping.exe`) before overwriting the DLL.
