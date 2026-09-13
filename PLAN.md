# Campfire Actions — plan

## Context

A Nexus user asked for a mod that lets Skif eat, drink, open the PDA, and inspect artifacts while sitting at a campfire. This is a separate mod from ImmersiveDialogue.

**Verdict: doable, moderate risk.** The block is not a hard-coded "no items while sitting" rule. It is an input-mapping side effect, and the ImmersiveDialogue codebase already has every piece of machinery needed to work around it if the pak-only route is not enough.

### How the game blocks it (from ZoneKit dumps + GameData cfgs)

- Sitting at a campfire is a generic **PlayerContextualAction** (`BP_PlayerContextualAction*` actors placed next to `BP_Stalker2Bonfire*`; one is literally named `BP_PlayerContextualAction_RedForest_Bonfire2`). On sit, the pawn sets `PC.contextual_action = true`, clamps camera yaw/pitch to the actor's `camera_yaw_min/max` + `camera_pitch_min/max`, and pushes the input context **`IMC_PlayerCA`** with priority **Exclusive** (`Stalker2\Content\GameLite\GameData\InputMappingContextPrototypes.cfg:294-298`).
- Exclusive suppresses `IMC_Exploration` (priority Lowest, cfg lines 10-17), which owns `IA_OpenPDA`, `IA_Inventory`, `IA_QuickSlot1..4`, `IA_ItemSelector`. The only actions left mapped in `IMC_PlayerCA` are `IA_PlayerCAExit` and `IA_GuitarContextualAction`.
- So eat/drink/PDA/inventory are blocked purely because their keys are unmapped. There is no `bCanEat` / `bInventoryBlocked` flag anywhere in the dumps. Artifact inspection has no entry Input Action of its own; it launches from the backpack UI, so it follows once inventory opens.
- Possible secondary vetoes (C++-side, unverified): `PC.can_use_inventory()` (`bp_api_dump2.txt:5153`), `PC.is_interaction_in_progress()` (`:5218`), `InputTriggerActionBlocker` conditions on the IA assets (`:3671`), and whatever `PDAOpenIPU` / `InventoryIPU` / `QuickSlot*IPU` check internally (all C++-only, 0 BP members).
- Relevant `PlayerTriggerState` enum values (`bp_api_dump.txt:5084`): `USE_PDA_TRIGGER`, `USE_BACKPACK_TRIGGER`, `USE_ITEM_LEFT_HAND_TRIGGER`, `USE_ITEM_RIGHT_HAND_TRIGGER`, `INSPECT_ARTIFACT_TRIGGER`.
- Unknowns that only in-game testing answers: whether first-person PDA/eat arm anims play sanely on top of the seated pose, whether closing the PDA correctly restores `IMC_PlayerCA` (Exclusive contexts push/pop, so probably yes), and whether the camera clamp fights the PDA view.

## Layered approach (one test build per layer)

### Layer 1 — pak-only, no code (cheapest test)
Open `/Game/_Stalker_2/data/input/InputMappingContexts/IMC_PlayerCA` in ZoneKit, add mappings for `IA_OpenPDA`, `IA_Inventory`, `IA_QuickSlot1..4` (copy the key bindings from `IMC_Exploration`), cook, ship as a `.pak`.

Do NOT lower `IMC_PlayerCA`'s priority in `InputMappingContextPrototypes.cfg` — that re-enables movement/weapon actions and will break the sit.

If this just works, the mod is a pak and we are done.

### Layer 2 — UE4SS "lie hook" if the input arrives but the action is vetoed
New C++ mod cloned from the ImmersiveDialogue skeleton (`CMakeLists.txt`, `dllmain.cpp` helpers `GetPawn`/`Fn`/`CallBool`/`ClassChainHas` at L544-573, and the `InstallIsInDialogLieHook` pattern at L454-470). Post-hook `/Script/Stalker2.PC:CanUseInventory` (and `IsInteractionInProgress` if needed) to return true/false while `contextual_action` is true. Same `RegisterHook` + `SetReturnValue` API the shipped dialogue mod already uses, so no new UE4SS surface.

### Layer 3 — runtime IMC patch instead of pak (only if a DLL-only install is wanted)
Reuse `PatchDialogInputMapping` (ImmersiveDialogue `dllmain.cpp` L3055-3139) against `IMC_PlayerCA`. Caveat: that code only renames keys in place; appending elements to the `Mappings` TArray crashed before. Prefer the pak for adding mappings.

### Discovery tooling (if Layer 1 fails silently)
- `InstallEntrySurveyHooks` (L488-527) pattern: post-hook `PC:StartUsePDA`, `PC:StartUseBackpack`, `PC:ConsumePlannedItem`, `PC:CanUseInventory` to see which fire on keypress while seated.
- `ScanWatched`/`RebindWatch` (L849-931) to confirm `contextual_action` flips on sit/stand.

## Verification
1. Sit at any campfire, press PDA / inventory / quick-slot keys. Success = UI opens or item is consumed while still seated.
2. Close PDA: player must still be seated with the camera clamp intact and `IA_PlayerCAExit` (stand up) still working.
3. Stand up, then confirm normal exploration input is unchanged.
4. Check `ue4ss\UE4SS.log` for any `[CampfireActions]` lines (Layer 2 only) and `ue4ss\crash_*.dmp`.

## Stretch: sleeping at a campfire

Different mechanism from the items work. Sleep is an interaction on a bed actor, not a pawn action:
- `BedView` (`UIDActor_Bed > Actor`, `bp_api_dump2.txt:1704`) owns a `BedHoldComponent` (`HoldComponent`, `:1702`); callbacks `on_sleep_started` / `on_sleep_ended`; `set_interactive_state(bool)`.
- The hold-E flow plays the lie-down anim (`AnimNotify_BedInteract`, `:1260`), opens `W_SleepView` (`CoreVariables.cfg:945`), pushes `IMC_Sleep` (Exclusive, `InputMappingContextPrototypes.cfg:87-93`), fades and skips time.
- Blockers live in `ObjSleepParamsPrototypes.cfg`: `AllowSleepThreshold = 50`, `bAllowEmissionSleep = false`, `CantSleepEffectSIDs = {Radiation, Bleeding, Psy, Hunger}NoSleep`. These apply wherever sleep is triggered.
- `PC` exposes no start-sleep function (only `Obj.is_sleeping()`), so a UE4SS mod cannot invoke sleep directly.

Recommended route, pak-only: edit `BP_Stalker2Bonfire` (a real Blueprint) in ZoneKit and add a bed child actor or `BedHoldComponent` so every campfire gets a hold-E "Sleep" prompt next to the single-click "Sit". Reuses the game's own sleep flow.

Risks: `BedHoldComponent` may require a `BedView` owner (C++ cast); bed GUID / save-state for a synthetic bed per campfire; lie-down anim and `sleep_teleport_min_distance` wake-up placement near the fire; sleep is entered from standing, not from the seated pose (chaining sit into sleep is out of scope).

### Alternative: synthetic "campfire rest" (no bed system)
UE4SS DLL, gated on `PC.contextual_action`, key-triggered from the WndProc hook. Sequence: fade out, advance clock 6h, refill rest, fade in.
- Rest stat: `Obj.get_current_sleepiness_points()` / `set_current_sleepiness_points()` (`bp_api_dump2.txt:4877`, `:5064`). Hunger/thirst/psy setters sit next to them if the rest should cost food/water.
- Fade: stock `PlayerCameraManager.StartCameraFade` (the dialogue mod already caches the camera manager).
- Time skip: no BP-exposed setter. A native TimeManager exists (`CoreVariables.cfg:18-25`, `RealToGameTimeCoef = 24` at `:27`) and quest node `EQuestNodeType::SetTime` takes hours+minutes (`bp_api_dump2.txt:533`), so a native set-time UFunction exists. Find it at runtime: UE4SS Live View or Lua probe, list objects whose class name contains "Time" and their functions. `WeatherConsoleCommands` (`:7404`, CheatManagerExtension) may also expose a time console command runnable via `ExecuteConsoleCommand`.
- Blockers to re-implement from `ObjSleepParamsPrototypes.cfg`: `AllowSleepThreshold = 50`, no emission, none of the `*NoSleep` effects active.
- Not covered by a fake sleep: A-Life / world catch-up, safe-wake teleport. Weather is time-driven and should follow. NPC schedules and emission timers after a 6h jump need an in-game test.
