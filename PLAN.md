# Immersive Campfires — plan (Zone Kit only)

Revised 2026-09-14 after ImmersiveDialogue v2.0.0 shipped as a pure Zone Kit pak
(no UE4SS). Everything below is done in the kit; no DLL is designed, built or
shipped. The first draft of this plan (UE4SS "lie hook" Layer 2, runtime IMC
patch Layer 3) is superseded; see "What changed" at the end.

Updated 2026-09-27 (renamed from Campfire Actions; repo renamed to
`stalker2-immersive-campfires`) with what ImmersiveDialogue learned through
v2.1.1: a `ModWorldSubsystem` in the NewContent container is a Blueprint host
that overrides nothing (it replaces the sit-actor override as the preferred
Layer 2 host and retires the GameFeature research item), mapping-context rows
need `PlayerMappableKeySettings` for player rebinds to reach them, and the
committed IMC generator already uses the moved-objects technique.

## Context

A Nexus user asked for a mod that lets Skif eat, drink, open the PDA, and
inspect artifacts while sitting at a campfire. Separate mod from
ImmersiveDialogue, same author, same toolchain.

**Verdict: doable, moderate risk, pak-only.** The block is an input-mapping
side effect, not a hard-coded rule, and ImmersiveDialogue v2 already proved
every mechanism this mod needs: an Input Mapping Context override, a Blueprint
override that calls native `PC` functions directly, and the cook/install
pipeline.

### How the game blocks it (verified against the kit dumps on 2026-09-12)

- Sitting at a campfire is a generic **PlayerContextualAction**
  (`BP_PlayerContextualAction*` actors placed next to `BP_Stalker2Bonfire*`;
  one is literally named `BP_PlayerContextualAction_RedForest_Bonfire2`). On
  sit the pawn sets `PC.contextual_action = true`, clamps camera yaw/pitch to
  the actor's `camera_yaw_min/max` + `camera_pitch_min/max`, and pushes the
  input context **`IMC_PlayerCA`** with priority **Exclusive**
  (`Stalker2\Content\GameLite\GameData\InputMappingContextPrototypes.cfg:294-298`).
- Exclusive suppresses `IMC_Exploration` (priority Lowest, cfg lines 10-17),
  which owns `IA_OpenPDA`, `IA_Inventory`, `IA_QuickSlot1..4`,
  `IA_ItemSelector`. The only actions left mapped in `IMC_PlayerCA` are
  `IA_PlayerCAExit` and `IA_GuitarContextualAction`.
- So eat/drink/PDA/inventory are blocked purely because their keys are
  unmapped. There is no `bCanEat` / `bInventoryBlocked` flag in the dumps.
  Artifact inspection has no Input Action of its own; it launches from the
  backpack UI, so it follows once inventory opens.
- Possible secondary vetoes (native, unverified): `PC.can_use_inventory()`
  (`bp_api_dump2.txt:5153`), `PC.is_interaction_in_progress()` (`:5218`),
  `InputTriggerActionBlocker` conditions on the IA assets (`:3671`), and
  whatever `PDAOpenIPU` / `InventoryIPU` / `QuickSlot*IPU` check internally
  (all native, 0 BP members).
- `PlayerTriggerState` enum (`bp_api_dump.txt:5084`): `USE_PDA_TRIGGER`,
  `USE_BACKPACK_TRIGGER`, `USE_ITEM_LEFT_HAND_TRIGGER`,
  `USE_ITEM_RIGHT_HAND_TRIGGER`, `INSPECT_ARTIFACT_TRIGGER`.
- Unknowns only an in-game test answers: whether first-person PDA/eat arm
  anims play sanely on the seated pose, whether closing the PDA restores
  `IMC_PlayerCA` (Exclusive contexts push/pop, so probably yes), and whether
  the camera clamp fights the PDA view.

### The ImmersiveDialogue precedent, mapped onto this mod

| Mechanism proven in ImmersiveDialogue v2 | Where it applies here |
|---|---|
| `IMC_Dialog` override: copy rows from `IMC_Exploration` into the active context, keep the game's own modifier/trigger objects, cook as OverrideContent | Layer 1: same script against `IMC_PlayerCA` |
| Native handler ignored the mapped action (`IA_LocomotionForward` in dialogue), so a Blueprint override handled the action itself and called the native `PC` function (`SetMoveVector`) | Layer 2: a Blueprint handles `IA_OpenPDA` etc. and calls `StartUsePDA` / `StartUseBackpack` / `ConsumePlannedItem` directly, bypassing the IPU veto |
| A "no change" result for a whole evening was pak mount order: kit paks mount at 3, `_P` mods at 103, `_10_P` at 1103; the override never loaded | Install every test build as `zzz_ImmersiveCampfires_30_P.*` (release: `_20_P`) from the first test, and ship a canary mapping (below) so "override not loaded" and "action vetoed" are distinguishable |
| Full-file cfg overrides clobber other mods | No cfg edits at all; `InputMappingContextPrototypes.cfg` stays vanilla (its priority must not change anyway) |
| `BP_Stalker2Character` and `AnimBP_Player` overrides conflict with every other mod that touches them; per asset, last mount wins outright | This mod never overrides those two assets: ImmersiveDialogue owns them, and a user running both mods would lose one. Put Blueprint logic in a ModKit world subsystem (overrides nothing; ImmersiveDialogue 2.1.0) or, failing that, on the contextual-action actor |

## Ground rules

1. **Ship a pak, nothing else.** UE4SS is allowed on the dev box as a
   read-only probe (the ImmersiveDialogue `ImmDlgProbeCpp` / Lua patterns),
   never in the release.
2. **Assets this mod may override:** `IMC_PlayerCA`, `BP_PlayerContextualAction`
   (or whichever Blueprint the sit actors derive from), `BP_Stalker2Bonfire`
   (stretch only). **Never** `BP_Stalker2Character`, `AnimBP_Player`,
   `AnimBP_player_bh`, or any `.cfg`.
3. **Mount order.** Release paks are named
   `zzz_ImmersiveCampfires_20_P.{pak,ucas,utoc}` in `~mods`; dev test paks
   `_30_P` so they beat a Vortex-installed release copy. Same base name for all
   three files.
4. **One change per cook**, Noah tests, checkpoint working states as tagged
   commits with the cooked pak in `zonekit/builds/`.
5. **Kit before build.** Every "kit check" below is answered by opening the
   asset or grepping the dumps before the next cook.

## Layer 1 — `IMC_PlayerCA` override (pak, no Blueprint)

Goal: put the item/PDA keys back while seated and see what the game does.

### Kit checks first
- `dump_imc.py` with `IMC_PlayerCA` and `IMC_Exploration` in its path list:
  confirm the asset path
  (`/Game/_Stalker_2/data/input/InputMappingContexts/IMC_PlayerCA`), list its
  current rows, and list every `IMC_Exploration` row for `IA_OpenPDA`,
  `IA_Inventory`, `IA_QuickSlot1..4`, `IA_ItemSelector` (keyboard and gamepad
  keys, their modifiers/triggers, and whether they carry
  `PlayerMappableKeySettings`, which is what lets a player's rebinds carry
  over).
- Check the `IA_*` assets themselves for an `InputTriggerActionBlocker`
  trigger (`bp_api_dump2.txt:3671`). If present, note its condition; it is
  the likeliest native veto.

### Build
1. Create the mod plugin in the kit: `<kit>\CreatePlainMod.bat ImmersiveCampfires`,
   then give the `.uplugin` the same descriptor fields as
   ImmersiveDialogue's (Game Features category, `Mod: true`,
   `ExplicitlyLoaded`). The editor discovers new plugins only at startup and
   generates the GameFeatureData asset on the first launch after that.
2. Generate the override from `zonekit/tools/make_imc_override.py` (template
   copied from ImmersiveDialogue; it already duplicates `IMC_Exploration` to a
   temp asset and *moves* its modifier / trigger / mappable-settings objects
   into the override with `rename(outer=…)`): `SRC = IMC_PlayerCA`,
   `REMOVE = {}`, `COPY_ACTIONS = {IA_OpenPDA, IA_Inventory, IA_QuickSlot1,
   IA_QuickSlot2, IA_QuickSlot3, IA_QuickSlot4, IA_ItemSelector}`,
   `DST = /ImmersiveCampfires/_Stalker_2/data/input/InputMappingContexts/IMC_PlayerCA`.
   Moving the `PlayerMappableKeySettings` is what lets a player's rebinds in
   Options > Controls reach the copied rows (ImmersiveDialogue's AZERTY report,
   2026-09-21). Headless only: `duplicate_asset` returns None in a running
   editor. Do not `delete_asset` the temp asset (commandlet crash); it is
   never saved.
3. **Canary row:** add a second key for `IA_PlayerCAExit` (say `Backspace`)
   to the override. If Backspace stands Skif up, the override is loaded. If
   PDA does nothing while Backspace works, the action is being vetoed and
   Layer 2 is needed. Remove the canary before release.
4. Verify the result with `dump_imc.py` against the `/ImmersiveCampfires/` path.
5. Cook and install with `zonekit/tools/cook_and_install.ps1` (classifier
   lists: `OverridePackages.txt` = the one IMC path, `NewPackages.txt` = the
   `ImmersiveCampfires` GameFeatureData). 5-6 minutes. Dev test paks install
   as `_30_P`; releases ship as `_20_P`.

### Test matrix (Noah, in-game)
| Step | Success |
|---|---|
| Sit at any campfire, press Backspace | Skif stands (override loaded) |
| Sit, press the PDA key | PDA opens while seated |
| Close PDA | still seated, camera still clamped, exit key still stands up |
| Sit, press inventory | backpack opens; inspect an artifact from it |
| Sit, press quick slot 1-4 with food/drink/medkit assigned | item is consumed, arm anim plays |
| Gamepad: same for the pad bindings | same |
| Stand up, walk, open PDA/inventory normally | exploration input unchanged |

If everything passes, the mod is this one asset and it ships.

### Possible outcomes
- **Works:** ship.
- **Backspace works, actions don't:** native veto. Go to Layer 2.
- **Nothing works, including Backspace:** the override did not load (name,
  mount order, classifier list, or a stale file in `Content/`). Fix the
  pipeline, not the mod.
- **Action fires but looks broken** (PDA fights the camera clamp, arm anim
  clips through the seated pose): decide per case; the fixes for camera live
  on the sit actor (its `camera_*` clamps) and are in scope, fixes in
  `AnimBP_Player` are not.

## Layer 2 — Blueprint handler calling `PC` directly

Used only if Layer 1 shows the key arriving and the game vetoing it. The idea
is ImmersiveDialogue's move handler, relocated: bind the action in a
Blueprint we own and call the native function the IPU would have called.

### Preferred host: a ModKit world subsystem (overrides nothing)

Proven by ImmersiveDialogue 2.1.0 (`Runtime/BP_ImmDlgSubsystem`) and in the
wild by Immersive HUD (`BP_ModWorldImp` spawns `BP_ModActorImp`, which calls
`EnableInput`, `Add/RemoveMappingContext` and binds `IA_QuickSlot1-4` /
`IA_Inventory` as EnhancedInputAction events):

- `Runtime/BP_ImmCampSubsystem` (`ModWorldSubsystem`, `OnTick`, NewContent)
  spawns `Runtime/BP_ImmCampActor` once per world. The actor calls
  `EnableInput` on player controller 0 and gates every handler on
  `Cast To PC(Get Player Pawn).contextual_action`, so exactly one handler
  exists regardless of how many bonfires are loaded.
- The subsystem only runs if the editor's **Package Mod** button has generated
  `Autogenerated_<n>_WorldSubsystemData` into the mod's Content (the headless
  cook does not generate it; it cooks it once it exists). That asset goes in
  `OverridePackages.txt`; the subsystem and actor go in `NewPackages.txt`.
- The NewContent container keeps the kit's file name
  (`ImmersiveCampfiresStalker2-Windows-NewContent.*`); its paths are unique, so
  mount order does not matter.
- Cook rules from ImmersiveDialogue: a Blueprint in the NewContent pass keeps
  references to other NewContent assets; a Blueprint in the *override* pass
  that references a mod-only asset gets that reference silently nulled; a
  package listed in both lists is cooked into neither. The editor redirects
  `/Game` picks of an overridden asset to the mod path, and only the
  game-path object carries the player's rebinds, so if the actor needs the
  overridden `IMC_PlayerCA` itself, load it by path string (ImmersiveDialogue
  BUILD.md §5.2b).
- Optional further step: our own `IMC_ImmersiveCampfires` added by the actor
  while seated instead of overriding `IMC_PlayerCA` at all. Only worth trying
  once we know whether the game's "Exclusive" priority blocks a context added
  on top of it; one test build.

The sit-actor override below stays as the fallback host if the subsystem
route fails for a reason we can't fix.

### Fallback host: the sit actor (why not the pawn)
- Overriding `BP_Stalker2Character` is proven to work (ImmersiveDialogue v2
  §5.3) but is off-limits here (ground rule 2).
- The contextual-action actor is the thing that starts and ends the sit, so
  it knows exactly when to enable and disable input, and it is not an asset
  any other known mod touches.

### Kit checks first
- Is `BP_PlayerContextualAction` a Blueprint asset (parent
  `/Script/Stalker2.PlayerContextualAction`), and are the per-level
  `BP_PlayerContextualAction_*` names level-actor labels or child Blueprints?
  Either way one override of the parent covers all; a child Blueprint
  inherits the parent graph. If the sit actors are placed as the native class
  directly with no Blueprint in between, this layer has no host and falls to
  Layer 2b.
- Which events the actor exposes: look for begin/end callbacks
  (`on_action_started` / `on_action_ended` style) and a reference to the
  player or an "is active" flag in the dump. Also check whether `PC` exposes
  the current contextual-action actor (grep `contextual` from
  `bp_api_dump2.txt:5141`).
- `PC` functions to call, all from the dump: `start_use_pda` (`:5360`),
  `start_use_backpack` (`:5359`), `consume_planned_item` (`:5162`). Quick slots
  need the function the `QuickSlot*IPU` calls; grep `quick_slot` / `use_item`
  in the PC block. Artifact inspection needs nothing (entered from the
  backpack UI).
- Is `PC.contextual_action` (`:5163`) Blueprint-writable? Only matters for the
  last-resort variant below.

### Build
Checkout `BP_PlayerContextualAction` to the mod folder (right-click → Checkout
selected content to mod plugin folder). In the override:

```
[sit started event, or BeginPlay if none is exposed]
  ─► Enable Input (Player Controller = Get Player Controller 0)
[sit ended event]
  ─► Disable Input

EnhancedInputAction IA_OpenPDA (Started)
  ─► Branch (gate: this actor is the active one; fallback gate = Cast To PC(Get Player Pawn).contextual_action AND distance to pawn < 300)
       True ─► Start Use PDA (target = the PC)

EnhancedInputAction IA_Inventory (Started)   ─► same gate ─► Start Use Backpack
EnhancedInputAction IA_QuickSlotN (Started)  ─► same gate ─► [quick-slot function from the kit check]
```

Notes:
- The Enhanced Input events only fire if the action is mapped in an active
  context, so the Layer 1 `IMC_PlayerCA` override stays installed. The
  project's default input component is the game's `PlayerEnhancedInputComponent`
  subclass, so actor-level Enhanced Input events should work; a kit check on
  a throwaway actor confirms before building the real graph.
- Every placed sit actor gets an input component if `Enable Input` runs on
  BeginPlay, so the gate matters: without it one keypress calls `StartUsePDA`
  once per bonfire on the map. Prefer the actor's own start/end events.
- Pick the `/Game/…` versions of the `IA_*` assets in the event nodes (the
  `IA_*` assets are not overridden, so no editor redirect applies).
- Cook: `OverridePackages.txt` gains the actor Blueprint path. The kit may
  drop an `Autogenerated_*_ActorReplacementData.uasset` into `Content/` for an
  actor override; v2 shipped without it (plain path override suffices) and
  deleted it before cooking. Do the same unless the sit actors turn out to be
  spawned by class rather than placed, in which case keep it.

### If `StartUsePDA` itself refuses while seated
Last resort, only if the kit check says `contextual_action` is writable:
set it false → `StartUsePDA` → set it true on the next tick. Risk: the camera
clamp or the seated pose may release for a frame. Test on one action before
generalizing.

### Layer 2b — the pawn is the only host
If there is no Blueprint between the placed sit actors and the native class,
the handler has to live on `BP_Stalker2Character`. That collides with
ImmersiveDialogue. Do not ship two competing pawn overrides; instead ship the
campfire handler as a documented, optional addition to the ImmersiveDialogue
pawn graph (one combined pak for users of both, a standalone pawn override
for users of this mod only). Decide only when forced. (Largely moot now that
the subsystem host exists; kept for completeness.)

## Retired research item: GameFeature actions

The 2026-09-14 draft proposed `GameFeatureAction_AddComponents` in the mod's
GameFeatureData to get logic onto the pawn without an override. The
`ModWorldSubsystem` host (Layer 2) solves the same problem and is proven in the
retail game; don't spend a cook on this unless the subsystem route fails.

## Diagnostics without a DLL

- The canary mapping (Layer 1 step 3) is the primary "did the override load"
  signal; keep one in every test build.
- `Print String` is stripped in Shipping, so a Blueprint cannot log. If a
  Layer 2 graph needs tracing, use a visible side effect (a camera fade or
  `Play Sound 2D` on a branch) rather than text.
- Dev-box only: the ImmersiveDialogue UE4SS probe pattern still works for
  reading `PC.contextual_action`, `is_using_pda`, and the active mapping
  contexts each second (its `zonekit/tools/probe/main.lua` shape, or a copy of
  its `ImmDlgProbeCpp` C++ probe, built from that repo's CMake tree). It never
  ships, and it must be listed before `UObjectCacheMod` in `mods.txt`.
- Blueprints can be read back as text: in the editor, Ctrl+A / Ctrl+C a graph
  and Claude reads the clipboard (`Get-Clipboard -Raw`); the same T3D text is
  how new node blocks are handed to Noah to paste.

## Verification (release)
1. The Layer 1 test matrix, all rows, keyboard and pad.
2. Uninstall test: delete the three files, sit, confirm vanilla behaviour.
3. Coexistence test with ImmersiveDialogue v2 installed: talk to an NPC, then
   sit at a campfire and run the matrix again. Both paks are `_20_P`; they
   must not share an asset path.
4. No `crash_*.dmp` in `ue4ss\` if UE4SS is installed on the test box.

## Stretch: sleeping at a campfire

Different mechanism from the items work. Sleep is an interaction on a bed
actor, not a pawn action:
- `BedView` (`UIDActor_Bed > Actor`, `bp_api_dump2.txt:1704`) owns a
  `BedHoldComponent` (`HoldComponent`, `:1702`); callbacks `on_sleep_started`
  / `on_sleep_ended`; `set_interactive_state(bool)`.
- The hold-E flow plays the lie-down anim (`AnimNotify_BedInteract`, `:1260`),
  opens `W_SleepView` (`CoreVariables.cfg:945`), pushes `IMC_Sleep`
  (Exclusive, `InputMappingContextPrototypes.cfg:87-93`), fades and skips
  time.
- Blockers live in `ObjSleepParamsPrototypes.cfg`: `AllowSleepThreshold =
  50`, `bAllowEmissionSleep = false`, `CantSleepEffectSIDs = {Radiation,
  Bleeding, Psy, Hunger}NoSleep`. They apply wherever sleep is triggered.
- `PC` exposes no start-sleep function (only `Obj.is_sleeping()`), so neither
  a Blueprint nor anything else can invoke sleep on the pawn directly.

Recommended route, pak-only: override `BP_Stalker2Bonfire` and add a Child
Actor Component whose class is the game's bed Blueprint (kit check: which
`BP_Bed*` asset the placed beds use, and whether `BedHoldComponent` requires a
`BedView` owner), so every campfire gets a hold-E "Sleep" prompt next to the
single-click "Sit". Reuses the game's own sleep flow, blockers included.
Conflict surface: any mod that overrides the bonfire Blueprint.

Risks: bed GUID / save state for a synthetic bed per campfire; lie-down anim
and `sleep_teleport_min_distance` wake-up placement near the fire; sleep is
entered from standing, not from the seated pose (chaining sit into sleep is
out of scope).

### Alternative: synthetic "campfire rest" in Blueprint (no bed system)
On the Layer 2 host (subsystem actor), a held key while seated runs: fade
out → advance the clock → refill rest → fade in.
- Fade: `Get Player Camera Manager → Start Camera Fade` (plain engine node).
- Rest stat: `Obj.get_current_sleepiness_points()` /
  `set_current_sleepiness_points()` (`bp_api_dump2.txt:4877`, `:5064`);
  hunger/thirst/psy setters sit next to them if the rest should cost food.
- Time skip: no BP-exposed setter found yet. Kit check: grep the dumps for a
  `TimeManager` / game-time class with a settable time (the quest node
  `EQuestNodeType::SetTime`, `bp_api_dump2.txt:533`, proves a native setter
  exists; `CoreVariables.cfg:18-27` names the manager). `Execute Console
  Command` with a `WeatherConsoleCommands` command (`:7404`,
  `CheatManagerExtension`) is unlikely to work in Shipping (no cheat manager)
  but costs one test.
- Blockers to re-implement from `ObjSleepParamsPrototypes.cfg`:
  `AllowSleepThreshold = 50`, no emission, none of the `*NoSleep` effects.
- Not covered by a fake sleep: A-Life / world catch-up, safe-wake teleport.
  Weather follows time. NPC schedules and emission timers after a 6 h jump
  need an in-game test.

## Repo layout

Set up 2026-09-27; see `BUILD.md` §3. Still to create:
`zonekit/tools/make_imc_playerca_override.py` (Layer 1 generator, derived from
the `make_imc_override.py` template) and the plugin itself under
`zonekit/ImmersiveCampfires/`. Checkpoint and release paks are committed under
`zonekit/builds/` (unignored there).

## What changed from the first draft (2026-09-12)

- **Dropped:** Layer 2 as a UE4SS post-hook on `PC:CanUseInventory`; Layer 3
  runtime IMC patch from a DLL; the `InstallEntrySurveyHooks` /
  `ScanWatched` discovery hooks; the WndProc-driven synthetic rest. All were
  `dllmain.cpp` reuse, and that code is now legacy in the sibling repo.
- **Replaced with:** a Blueprint override that binds the Input Actions and
  calls the native `PC` functions directly (the same trick that made movement
  work in dialogue), hosted on the sit actor rather than the pawn to avoid
  colliding with ImmersiveDialogue's pawn and anim overrides.
- **Added:** the `_20_P` mount-order rule from the first test, the canary
  mapping so a silent failure is diagnosable without a DLL, the no-cfg rule,
  the coexistence test with ImmersiveDialogue, the GameFeature
  `AddComponents` research item, and the note that the committed
  ImmersiveDialogue IMC script is stale relative to BUILD.md.
- **2026-09-27:** the subsystem host replaces the sit-actor override as the
  preferred Layer 2 host and retires the GameFeature item; the IMC script is
  no longer stale (it moves the real objects, mappable settings included).
