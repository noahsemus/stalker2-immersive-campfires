# ImmersiveCampfires — engineering log

What each kit check and each in-game test showed, newest at the bottom. Record
dead ends here so they are never retried. The plan is in [../PLAN.md](../PLAN.md);
the reproducible edits are in [../BUILD.md](../BUILD.md).

## 2026-09-27 — harness set up

Repo renamed from `stalker2-campfire-actions`; plan branch (Zone Kit only,
2026-09-14) merged and updated with ImmersiveDialogue 2.1.x findings (world
subsystem host, mappable key settings, `_30_P` dev test paks). Tools copied from
ImmersiveDialogue `zonekit/tools/`. Nothing cooked yet.

## 2026-09-27 — Layer 1 kit checks, plugin created

- `IMC_PlayerCA` (vanilla, 20 rows): `IA_PlayerCAExit` on Space / Esc / W A S D /
  F / pad A B X Y / left stick / Special_Right; `IA_LookUp` (mouse, right stick,
  numpad); `IA_GuitarContextualAction` on G / right-stick click. No row uses the
  keys we add, so no collision on keyboard or pad.
- `IMC_Exploration` rows to copy (21, incl. the key-None "Alt" slots):
  `IA_OpenPDA` P (Tap + Hold 1.0) / pad Special_Left; `IA_Inventory` I / DPad
  Down; `IA_QuickSlot1/3` Q / E tap, `IA_QuickSlot2/4` Q / E hold 0.5 (pad DPad
  Left / Right); `IA_ItemSelector` Tab / LB. Keyboard rows carry
  `PlayerMappableKeySettings` (OpenPDA, Inventory, QuickSlot1..4, ItemSelector,
  and the *Alt names); pad rows inherit from the action.
- **No `InputTriggerActionBlocker`** on any of the IA assets (action-level
  triggers are only Tap / Hold / Down), so there is no asset-side veto; any
  veto would be native.
- PC exposes `start_use_pda(initial_page_type)`, `start_use_backpack()`,
  `can_use_inventory()`, `consume_planned_item()`, and `contextual_action` is
  Read-Write (Layer 2 material). No BP-callable quick-slot function.
- Plugin created with `CreatePlainMod.bat`, descriptor fields set. The headless
  commandlet refuses to mount it ("without a UGameFeatureData asset ... will not
  load in Mod Editor"), and the Python `GameFeaturesSubsystem` is not exposed, so
  a restart alone does not help either (same warning in the editor log). The
  GameFeatureData (with its AddToContentPack / AddConfigsPath /
  AddWorldPartitionContent actions) is created by the ModKit when the mod is
  **picked as the active mod in the toolbar mod selector**; that also mounts
  the plugin. Duplicating another mod's GameFeatureData is wrong: its actions
  carry that mod's ContentPackName / ConfigPath, which Python cannot edit, and
  the editor refuses to delete a GameFeatureData while running (delete the
  file on disk).
- Generator written: `tools/make_imc_playerca_override.py` (vanilla rows + the 21
  copied rows with moved trigger/mappable objects + canary BackSpace ->
  `IA_PlayerCAExit`).

## 2026-09-27 — first test build (Layer 1 + canary)

Mod picked in the toolbar selector: GameFeatureData created, plugin mounted.
`make_imc_playerca_override.py` ran in the live editor through `ue_exec.py`
(the AssetTools fallback in `dup()` works there): 22 vanilla rows + 21 copied
rows (14 with mappable settings) + canary BackSpace -> `IA_PlayerCAExit` = 44.
Cooked and installed as `zzz_ImmersiveCampfires_30_P` (override pak holds
`IMC_PlayerCA`) + the NewContent container (GameFeatureData). Awaiting Noah's run.

## 2026-09-28 — first run: nothing works, canary included

Noah: seated shows only the vanilla guitar / Escape prompts; no added key
worked, Backspace canary included. Checked:
- Both containers mounted (`Stalker2_2.log`): override at Order 3103, NewContent
  at 3. No other pak in `~mods` contains `IMC_PlayerCA` (byte grep of every
  .utoc/.pak).
- The cooked override is right: extracted `IMC_PlayerCA.uheader` names include
  BackSpace, P, I, Q, E, Tab, DPad, OpenPDA / QuickSlot* mappable names.
- The campfire context really is `IMC_PlayerCA` (only IMC holding
  `IA_GuitarContextualAction` + `IA_PlayerCAExit`; cfg MappingId
  `PlayerContextualAction`).
- ImmDlgProbeCpp shows the ImmersiveDialogue `IMC_Dialog` override live at
  runtime (38 rows), so IMC overrides do apply in general.
- Noah's rebinds (`CustomizeControls.cfg`): PDA = CapsLock, Inventory = LeftAlt,
  QuickSlot1/2 = Z, QuickSlot3/4 = X, LeanLeft/Right = Q/E. So P / I / Q / E were
  the wrong keys to test on his setup; the canary is the real failure.
  `PlayerContextualAction =` is empty in that file (it lists per-context rows
  whose mappable name the player rebound, e.g. InspectArtifact).

Next: `tools/probe/ImmCampProbeCpp` (dev-only UE4SS C++ probe, built from the
ImmersiveDialogue CMake tree, which now adds it via an optional
`add_subdirectory`). While seated it logs each `IMC_PlayerCA` object in memory
(path, rows, keys) and the live `EnhancedPlayerInput.EnhancedActionMappings`
keys for the exit / PDA / inventory / quick-slot actions. Installed to
`ue4ss\Mods\ImmCampProbeCpp`, listed before `UObjectCacheMod`.

## 2026-09-28 — probe run: override live, actions vetoed natively

ImmCampProbeCpp captured two sits (PC prop is `bInContextualAction`): the live
`EnhancedPlayerInput.EnhancedActionMappings` holds all 44 override rows
(`IA_OpenPDA:P`, `IA_Inventory:I`, `IA_QuickSlot*:Q/E`, canary `BackSpace`), and
the only `IMC_PlayerCA` in memory is the game-path object with 44 rows. Noah:
Backspace stands up; P and I (pressed in the first run too) do nothing. So the
keys arrive and the game's native handlers (PDAOpenIPU / InventoryIPU, no BP
surface, no cfg) ignore them while seated -> Layer 2.
- Player rebinds do not reach the copied rows: `CustomizeControls.cfg` stores
  rebinds per context and `PlayerContextualAction =` stays empty (rewritten at
  exit, still empty); live rows keep the asset's default keys (P, not Noah's
  CapsLock). ImmersiveDialogue 2.1.0 notes the Controls menu writes a context's
  section when the player applies a binding; untested here.
- Quick slots have no BP-callable entry on PC (only `consume_planned_item`,
  which needs a planned item set natively). Open question.

Layer 2 started: `Runtime/BP_ImmCampSubsystem` (ModWorldSubsystem) and
`Runtime/BP_ImmCampActor` (Actor, CDO `AutoReceiveInput = Player0` set from
Python) created in the live editor. Actor graph generated by
`tools/gen_actor_seated_input.py` (IA_OpenPDA / IA_Inventory `Started` -> Cast To
PC(Get Player Pawn) -> Branch `bInContextualAction` -> `StartUsePDA(None)` /
`StartUseBackpack`).

## 2026-09-29 — Layer 2 build 1 (PDA + backpack handler)

- Blueprints can be read back without Noah: `AssetExportTask` on a Blueprint
  (via `ue_exec.py`) writes the full T3D of every graph (used to lift the
  ImmersiveDialogue subsystem's node formats and to verify our pastes).
- `BP_ImmCampActor`: pasted from `tools/gen_actor_seated_input.py`, compiled clean.
- `BP_ImmCampSubsystem`: pasted from `tools/gen_subsystem_spawn.py`:
  OnInitialized -> SetTickEnabled(true) (ModWorldSubsystem does not tick until
  enabled; ImmersiveDialogue does the same), OnTick -> SpawnActorFromClass
  (BP_ImmCampActor) -> SetTickEnabled(false). Compiled clean.
- Package Mod generated `Autogenerated_1790710477_WorldSubsystemData` and added
  it to OverridePackages.txt itself. Cooked + installed: override container has
  the WorldSubsystemData + IMC_PlayerCA; NewContent has the GFD + both BPs.
- Probe now also lists live `BP_ImmCampActor_C` / `BP_ImmCampSubsystem_C`
  objects on each sit. (Vortex had rewritten `mods.txt` and removed both probe
  folders; ImmCampProbeCpp reinstalled, ImmDlgProbeCpp left out.)

## 2026-09-29 — build 1 result: subsystem alive, no actor -> build 2

Noah: P / I still do nothing seated. Probe on both sits: `BP_ImmCampSubsystem_C`
lives in `WorldMap_WP`, **no `BP_ImmCampActor_C` object exists**. The
spawn-once-then-tick-off graph either spawned too early (actor gone) or never
spawned. Build 2: subsystem variables `SeatedActor` / `SpawnAttempts` (added
from Python, `BlueprintEditorLibrary.add_member_variable`), OnTick ->
Branch(IsValid(SeatedActor)) false -> SpawnAttempts+1 -> SpawnActor -> Set
SeatedActor; tick stays on. Probe prints both variables on each sit.
(T3D export also lists deleted-but-not-GC'd nodes; trust the graph's `Nodes(n)`
list, not every `K2Node_*` object in the file.)

## 2026-09-29 — build 2 result: actor alive, still nothing -> build 3 (counters)

Probe: `spawnAttempts=1 seatedActor=BP_ImmCampActor_C_...`, actor lives in
`WorldMap_WP:PersistentLevel` for the whole sit. P / I still do nothing (Noah;
he also only sees the vanilla guitar hint, which is expected: hints don't list
our rows). Build 3 adds int counters `Presses` (after the IA Started event) and
`Calls` (right before StartUsePDA / StartUseBackpack) to the actor; the probe
reads them plus the actor's `InputComponent` class, now also on stand-up.

## 2026-09-29 — build 3 result: input arrives, native call refuses -> build 4

Probe on stand-up: `Presses=4 Calls=4 inputComp=PlayerEnhancedInputComponent`
(2 x P, 2 x I). The seated keys reach our actor through the game's own input
component class, the seated gate passes, `StartUsePDA` / `StartUseBackpack` are
called, nothing opens. Noah: opening the PDA / backpack plays a first-person
arms animation; likely the veto sits in that animation / state path.
Build 4 (`gen_actor_seated_input.py`, now on `bp_graph.py`, which writes links
on both ends): record `CanUseInventory` and `IsInteractionInProgress` before
the call, set `PC.bInContextualAction = false` around the call and back to true
right after, record `IsUsingPDA` / `IsUsingBackpack` afterwards. Probe reads the
three bools.

## 2026-09-29 — build 4 result: flag toggle does nothing; sit = interaction in progress

Probe (7 presses): `Presses=7 Calls=7 CanInvBefore=1 InteractBefore=1
UsingAfter=0`. Setting `bInContextualAction` false around the call compiles
(the flag is BP-writable) but changes nothing, and nothing opened. The game
treats the sit as an interaction in progress for its whole length, and
`CanUseInventory` is true, so the veto is the interaction state.
Build 5: save `GetInteractionTarget()`, `ResetInteractionTarget()`, record
`IsInteractionInProgress()` again (InteractMid) and IsValid(target) (HadTarget),
flag off, call, flag on, record IsUsing*, `SetInteractionTarget(saved)`.

## 2026-09-29 — build 5 result: dead end for the vanilla sit; own seated mode

Probe: `HadTarget=1 InteractMid=0 UsingAfter=0`. Clearing the interaction target
does end "interaction in progress", but the game treats that as the sit ending:
Noah saw Skif stand up and sit back down (the restore re-sits him), and the
PDA / backpack still did not open. Conclusion: inside the vanilla sit the
native open paths are blocked, and the only BP lever that unblocks them ends
the sit. Nothing BP-exposed opens the PDA / inventory views directly (no view
API on UIManagerEx / ViewBase / CppMediator).

Noah chose **our own seated mode** (2026-09-29): a sit the game does not count as
an interaction, so PDA, backpack, artifacts and eating use their normal paths.
Kit facts for it:
- The bonfire sit is `MG_fp_ca_gd_bonfire` (sit_ground_bonfire folder), slot
  **FullBody**, sections In -> Idle (Idle loops) -> Out. `AnimCollection_pca_bonfire`
  also sets `bShouldLerpToInteractable` and `bShouldToggleFOV`.
- `BP_PlayerContextualAction` (/Game/_STALKER2/Animations/Player/AnimSequences/
  contextual_action/) is an empty Blueprint over the native class.
- `CppMediator.lerp_player_to_location_and_rotation` exists (seat placement).
- `SetTimeEditorQuestNode` / `CppMediator.start_quest_node(sid)` are a lead for
  the sleep feature's time skip.
Proof build (`tools/gen_actor_seat_test.py`, replaces the actor graph): Home key
plays / stops the bonfire montage on the pawn (`Character.PlayAnimMontage`
"In" / `StopAnimMontage`), no interaction involved.

## 2026-09-29 — full seated mode (build 6)

Noah: no small proofs, build the whole thing. `tools/gen_actor_seated_mode.py`
(119 nodes, replaces the actor graph): vanilla sit as the entry (prompt, sit-in,
guitar); once the vanilla montage is in "Idle", take over: save the interaction
target and actor yaw, `ResetInteractionTarget`, `PlayAnimMontage(sit, "Idle")`,
SeatedMode. Every tick while seated: `DisableMovement`, camera-manager look
limits (pitch -60..50, yaw seat ± 75), re-play "Idle" if no montage runs or the
sit montage jumped to "Out". Stand = IA_LocomotionForward / IA_Jump /
IA_Interact Started -> "Out" + 3.6 s delay -> walking + saved standing limits.
G (legacy key, not consumed) -> hand back to the vanilla sit via
`SetInteractionTarget(saved)` (VanillaHold until the player stands). Look
limits saved once while standing. The IMC_PlayerCA override stays in this
build (only matters during the vanilla phase).

## 2026-09-29 — build 6 result and the legs layer (build 7)

Noah: stays seated, P / I / Q / E work, but (1) his rebinds (CapsLock, Left Alt)
don't: `IMC_PlayerCA` stays active after `ResetInteractionTarget`, and only our
override's default rows answer; (2) the mouse turns the whole body (the vanilla
sit routes look to a camera-only path while `bInContextualAction` is set);
(3) no arm animations for PDA / backpack / items.
Why (3): in `AnimBP_Player` the `FullBody` slot sits after everything
(`PreFullBodyPose` cache -> Slot FullBody -> LayeredBoneBlend with no layers ->
out), so any FullBody montage hides the arm-action layers
(`AnimBP_player_bh` WeaponLayer: `PreActionFullbodySlot` -> MainActionSlot /
UpperBody). Dead ends: montage blend profiles (UE 5.5 clears
`ActiveBlendProfile` once the blend-in ends; BlendMask mode isn't handled for
montages at all), `DetectorLayer` (no input pose, detector-only),
`GuitarStateMachine` (guitar only).
Fix chosen by Noah: a post-process anim BP, `Runtime/ABP_ImmCampSeatedLegs`
(Input Pose -> LBB blend mask `lower_body_blend_mask` <- sit idle -> LBB branch
`jnt_camera` <- sit idle), installed with ImmersiveDialogue's mesh-swap trick only
while seated, the previous post-process class (ImmersiveDialogue's
`ABP_ImmDlgBody` or none) saved and put back on stand-up / guitar. ImmDlg's
subsystem sets `bDisablePostProcessBlueprint = true` every tick outside
dialogue, so our actor sets it false every seated tick and is made a tick
prerequisite of the player mesh. Also: `EnableInputAfterInteraction` after the
takeover (normal controls), `bUseControllerRotationYaw` false while seated,
`IA_PlayerCAExit` added to the stand events. Generators: `gen_abp_seated_legs.py`
(nodes lifted from the game's own exports by `t3d_lift.py`),
`gen_actor_seated_mode.py` (197 nodes).

## 2026-09-29 — build 7: crash at takeover -> swap only while standing (build 8)

Crash right after the sit-in: `EXCEPTION_ACCESS_VIOLATION reading 0xa00`
(`Stalker2_2.log`), UE4SS ProcessEvent frames in the stack, i.e. inside our BP
chain, 0.4 s after `bInContextualAction` rose. Same address family as
ImmersiveDialogue's 09-17 class-swap crash. Cause: the mesh swap (which
re-initialises the anim instances) ran during the interaction teardown; the
native sit code still points at the old montage / anim data.
Build 8: the swap never runs during a sit. Tick step 4 installs the legs layer
while a `PlayerContextualAction` is the interaction target (standing, looking at
the seat prompt), keeps it disabled until seated, and restores the saved class
once no seat is targeted (standing, not seated, 2 s cooldown). Takeover requires
the layer to be installed; stand-up and guitar no longer swap. New variable
`LastSwapTime`. Assumption to verify: `GetInteractionTarget` returns the focused
seat before interacting.

## 2026-09-29 — build 8: crash on interact -> legs layer on AnimInstancePlayer (build 9)

Probe: layer went null -> `ABP_ImmDlgBody_C` (ImmersiveDialogue's attach, 2 s
after load) -> `ABP_ImmCampSeatedLegs_C` at the seat prompt (install worked
while standing, no crash), then the crash (`0xa00`, same stack as build 7) 0.3 s
later on the interact click. Common factor of both crashes: our post-process
instance present when the native sit starts. Ours was parented to plain
`AnimInstance`; ImmersiveDialogue's is `AnimInstancePlayer` and never crashes,
so the native sit code evidently treats the post-process instance as an
`AnimInstancePlayer` (field near +0xa00). Build 9: `ABP_ImmCampSeatedLegs`
reparented to `AnimInstancePlayer` (BlueprintEditorLibrary.reparent_blueprint),
graph unchanged, actor recompiled.

## 2026-09-29 — build 9: still crashes on interact, layer not even installed

Probe: layer stayed `ABP_ImmDlgBody_C` (ours never installed), crash on the
interact click anyway, same `0xa00` stack -> not the layer. Resolved the stack
against the exe (base from UE4SS's `ProcessLocalScriptFunction` address and its
signature file; function starts from `.pdata`; exec thunks from the
`FNameNativePtrPair` tables in `.rdata`): script VM -> exec thunk of
**`PC.IsVaulting`** -> native crash reading this+0xa00. Our cooked BP never
calls IsVaulting. The only new input binding since build 6 is
`IA_PlayerCAExit` (added in build 7 as a stand-up fallback); it triggers the
moment the sit context comes up with the interact key still held, and the
game's delayable handler for it evidently treats the bound object as the PC.
Build 10: `IA_PlayerCAExit` binding removed (stand = move / jump / interact).
Tool: `%TEMP%/findfn*.py` (to be moved into tools/ if needed again).

## 2026-09-29 — build 10 still crashes at the click -> control test without the mod

Build 10 (no IA_PlayerCAExit binding, layer never installed: probe shows only
`ABP_ImmDlgBody_C`) crashes at the interact click with the identical stack.
Nothing of the takeover runs at that moment. Vortex redeployed the mod set at
17:27, between the last clean build-6 session (17:05-17:08) and the first
crash (17:36); ImmersiveDialogue's 2.1 files (09-27 12:20) were already there
for build 6. Control test: dev pak parked in the scratchpad (`parked/`), Noah
sits at the same campfire with everything else unchanged.

Control test (dev pak parked): no crash -> it is our mod. Pattern over builds 7-10:
the crash comes whenever our post-process instance is swapped in around the
vanilla sit (build 7: swap during the takeover; build 8: installed at the prompt,
crash on the click; builds 9/10: install evidently on the click frame, faster
than the 1 s probe sample). Build 11: no swap ever overlaps the vanilla
interaction. Takeover = build-6 style (reset, controls, yaw, re-play the sit
montage "Idle"), then Delay 1.5 s -> if still seated: save previous class, swap
in the legs layer, stop the sit montage. Stand = "Out" + 4.1 s, then restore the
previous class, then walking. Guitar = restore, 0.5 s, then SetInteractionTarget.
Seat-prompt install (step 4) removed.

## 2026-09-29 — build 11: crash 20 ms after the legs layer went on -> clear the sit flag (build 12)

Probe: flag up 20:47:25, legs layer on 26.66 with `bInContextualAction` still
**1**, crash 26.68: `EXCEPTION_ACCESS_VIOLATION reading 0x20`, script VM ->
exec thunk of **`PC.HasNightVisionAnimation`** (resolved the same way as
IsVaulting). So `ResetInteractionTarget` does not clear the contextual-action
flag, and our post-process instance present while the game is in that state
crashes (same as build 8, where the click started the sit with our layer on).
Build 12: the takeover sets `PC.bInContextualAction = false` (BP-writable,
build 4), the seated tick keeps it false, and the delayed install requires it
false.

## 2026-09-29 — build 12: still crashes (HasNightVisionAnimation) -> diagnostic build 13

Flag cleared (probe never saw seated=1 for a full second), crash ~5 s after the
sit with the same HasNightVisionAnimation stack, i.e. right after the delayed
swap. Diagnostic build 13 (`scratchpad/gen_diag.py`, not the product): the
delayed install swaps back in the *previous* class (ImmersiveDialogue's
ABP_ImmDlgBody) instead of ours. Crash -> swapping after a sit is the problem;
no crash -> our class is the problem (next: a full AnimBP_Player copy like
ImmersiveDialogue's, with the legs blend on top).

## 2026-09-29 — diagnostic build 13: crash too -> no post-load swaps (build 14)

Swapping ImmersiveDialogue's own class back in after the sit crashed the same
way. So any post-process swap during play, followed by (or following) a sit,
crashes; the class is irrelevant. ImmersiveDialogue's single swap ~1 s after
load is the only swap known to be safe. Build 14: `USE_LEGS_LAYER = False` in
the generator (delayed install not emitted), seated pose = sit montage "Idle"
held by us with the build-6 heal; kept: flag off, EnableInputAfterInteraction,
body-yaw off, look limits. Arms stay in the seated pose (no item animations).
Next idea for arms: install our layer once at load (chaining the previous
class through a Linked Anim Graph node), never swap afterwards.

## 2026-09-29 — build 14 result: stable; build 15 = legs layer installed once at load

Build 14 (no swap): no crash, all actions work seated, but (a) no arm
animations (sit montage FullBody) and (b) only the default keys work (the
override's `IMC_PlayerCA` rows; rebinds for that context are written only when
the player applies bindings in Options with the override installed; to test).
Build 15: the legs layer goes on once per world, 3 s after the pawn appears,
outside dialogue / sit (step 5; ImmersiveDialogue swaps at ~1 s). It chains the
previous class through a Linked Anim Graph tagged "Previous"
(`LinkAnimGraphByTag`; default instance `ABP_ImmCampPassThrough`), and only
blends seated legs while its `Seated` variable is set (step 4, which also
enables the post-process instance while seated). Takeover stops the sit montage
when the layer is present, else holds it (build-14 behaviour). No swaps on
stand-up or guitar.

## 2026-09-29 — build 15 dead end (Linked Anim Graph) -> additive sit (build 16)

The Linked Anim Graph node never offers an `In Pose` pin for our pass-through
ABP (its pins come from the target's AnimGraph function parameters; only the
AnimInstancePlayer "Exposable Properties" appear). Dropped the whole
post-process route. Build 16: `AS_ImmCamp_SitAdditive` (tools/make_sit_additive.py):
the bonfire sit idle duplicated, 85 non-lower-body tracks set to
`fp_bh_idle_stand` frame 0, additive local-space against that frame. Played by
the actor as a looping dynamic montage in the `FullBody` slot (own slot group
`FullBodyGroup`, so UpperBody / action montages don't cancel it); the slot adds
it on top of the game pose, so arm / item animations show. Heal: re-play if
`IsPlayingSlotAnimation` is false. Stand: StopSlotAnimation then the vanilla
"Out" montage. Guitar: StopSlotAnimation, 0.3 s, SetInteractionTarget. No
post-process swaps anywhere (the two ABPs stay in the plugin, unused).

## 2026-09-29 — build 16 result -> build 17

No crash; the item arm animations play (backpack fully right). Issues: (1) mouse
yaw turned the upper body, camera didn't yaw (the camera hangs off the body; with
`bUseControllerRotationYaw` off only the aim offset turns); (2) weapon half
state (laser + shadow, no weapon, hands in weapon pose): the vanilla sit's
SaveStatesBeforeInteraction is never undone after ResetInteractionTarget;
(3) PDA / bottle off-centre: v1 additive used the sit camera but the standing
upper body; (4) seat prompt still visible; (5) default keys only
(`PlayerContextualAction =` still empty in CustomizeControls.cfg).
Build 17: additive v2 (`make_sit_additive.py`: hips + legs from the sit,
spine_01 counter-rotated so the chest stays upright, everything above standing,
jnt_camera moved by exactly the chest drop: 83 cm down, 7.7 cm back); takeover
keeps yaw-follow on, calls `RestoreStatesAfterInteraction`, and
`SetInteractionActive(false)` on the saved seat component (true again on stand /
guitar). Rebinds: Noah to apply a binding after having sat once (IMC_PlayerCA
loaded), then check the cfg.

## 2026-09-29 — build 17 result -> build 18

Yaw fixed. Unchanged: weapon laser + shadow without the weapon, PDA / bottle
off-centre, sit prompt visible, default keys (cfg `PlayerContextualAction =`
still empty; not clear the Options step was done after a sit). Diagnosis: the
vanilla sit (`bShouldToggleFOV`) turns the first-person FOV / foreground render
off and only its own exit turns it back on, so the FP weapon is not drawn and FP
items render at world FOV (off-centre). `SetInteractionActive(false)` on the
saved component did not hide the prompt. Build 18: takeover also calls
`ToggleFOVAndForegroundRender(true)` and `PC.DisableInteractions`; stand-up and
guitar call `PC.EnableInteractions`.

Noah (2026-09-29): players must never have to re-apply bindings. Build 18 adds
an automatic key sync to the takeover (once per world, `KeysSynced`): load the
game-path `IMC_Exploration` and `IMC_PlayerCA` by path string (ImmersiveDialogue
2.1 pattern: MakeSoftObjectPath -> Conv -> LoadAsset_Blocking -> cast), for each
`IMC_Exploration.Mappings` row whose action is OpenPDA / Inventory / QuickSlot1-4
/ ItemSelector and whose key is valid, `MapKey` it into IMC_PlayerCA, then
`EnhancedInputLibrary.RequestRebuildControlMappingsUsingContext(IMC_PlayerCA,
true)`. Assumes the game writes the player's rebinds into the game-path
IMC_Exploration object (ImmersiveDialogue saw that for IMC_Dialog). Quick-slot
tap / hold come from the IA assets' own triggers; the added OpenPDA row has no
Tap/Hold trigger.

## 2026-09-29 — build 18 result -> build 19

Custom keys work seated (key sync OK). Noah: only the custom keys should work;
drinking still off-centre; hands look like they hold an invisible weapon; they
should rest like the vanilla sit. Build 19: key sync first
`UnmapAllKeysFromAction` for the seven actions in IMC_PlayerCA, then maps the
exploration keys (only the player's keys remain). Takeover:
`Obj.ChangeMainHandWeapon(None, 0, skip anim)` instead of
RestoreStatesAfterInteraction (bare hands), resting pose = the vanilla sit
montage "Idle". Seated tick: arms busy = IsUsingPDA || IsUsingBackpack ||
HasItemInMainHand || IsLeftHandBusy -> the additive free-arms pose; 0.4 s after
the last busy tick -> back to the resting montage (also heals a lost pose).
Stand-up and guitar end with `EquipLastHeldItem`.

## 2026-09-29 — builds 20-27: yaw tables, busy detection, guitar

- Busy = `IsUsingPDA || IsUsingBackpack || IsSlotActive(MainActionSlot | DefaultSlot | UpperBody)` (all item / PDA /
  backpack montages are in `MainActionSlot`; PIR's stimpak in `DefaultSlot`). Weapon: `ChangeMainHandWeapon(None)`
  never changed the hand type; `RemoveWeaponFromHands` hides the weapon (hand type stays 1).
- Legs turned with the view (bUseControllerRotationYaw). Poses rebuilt as yaw tables (`make_sit_yaw.py`), played as
  a paused dynamic montage in `FullBody`, position set per tick from the view yaw: rest = the sit frame 0 with the
  whole body turned by -yaw about the root; free arms = additive, hips moved (not turned) to the sit position, legs
  re-expressed under the standing hips, jnt_camera and the other root children (jnt_item: the PDA hangs off it)
  moved by the same offset. Noah: legs stay put, drink / PDA centred.
- Rest pose overrode jnt_camera: no looking up / down (build 21). Build 22: rest table = 151 yaw rows x 23 pitch keys.
- Guitar: IA is in `InputActions/Guitar/` (not Delayable). `VanillaHold` was released one tick after G (the sit flag
  comes back only after the sit-in); `GuitarPending` now set first. A section jump over the sit-in skipped the
  `InteractAction` notify at 3.9996 s: stuck. Guitar put away -> `bPlayingGuitar` false -> back to the seated mode.

## 2026-09-30 — builds 28-32: the view source, the pause, stand-up

- Probe burst (per-update ControlRotation vs camera vs montage position): `PC.GetControlRotation` returns the camera,
  which this pose drives (feedback, shake); `Controller.GetControlRotation` too; the controller actor's rotation never
  updates. Pitch now from `AnimInstancePlayer.CameraData.ClampedControlPitch` (look-vertical explicit time,
  0 = +90, 1 = -90: `fp_bh_stand_lookvertical_idle`); matches ControlRotation exactly in the burst.
- Item stance: every item animation keys the hips 7.4 cm / 19 deg from `fp_bh_idle_stand`; the additive table is now
  built on `fp_ar_idle_stand` (same hips): Noah, legs better during items.
- `SaveStatesBeforeInteraction` / `RestoreStatesAfterInteraction` (build 28): weapon stored (hand 0) but the view
  pitch pinned at the min and WASD dead after standing. Removed.
- The pose montage ran at rate 1.00 all along (probe `@1.00`, position = target + one frame time): stutter, legs
  vibrating, the body sweeping through the 1 s yaw table during items. A pasted `NewPlayRate = 0.0` comes back as the
  C++ default 1.0. Build 32: SetPosition(target - DeltaSeconds * rate).
- Can't walk after a guitar round trip: move input not ignored, walking mode (probe `move`); `IMC_PlayerCA` (WASD =
  leave the sit) stays applied. Build 31: stand-up removes it.

## 2026-09-30 — build 32 result (Noah: best build by far)

Camera smooth (stutter gone: position compensation + a 0.0001 pause rate that survives the paste; probe `@0.00`),
items good, guitar: stays seated, no camera jank, put away returns to our seated mode, walking after standing works
(IMC_PlayerCA removed on stand). Open: after an item the look "drops input" briefly about every second; the game
re-equips the pistol after an item (`MG_fp_udp_equip`, hand 1) and it shows until the resting pose hides it; the body
turns for a moment when the guitar comes out (the vanilla montage faces the actor = view direction, then the vanilla
sit turns to the seat).

## 2026-09-30 — build 33: release candidate

Pistol hidden as soon as the game re-equips it (hand type change -> RemoveWeaponFromHands), `SetControlRotation`
to the seat before the guitar hand-back (no body swing), healing a lost resting pose uses a 0.01 s blend.
Noah: release candidate. The mouse-look drop is still there, also after leaving the campfire. Probe montage log:
our pose montage changes only at item start / end (one change each, plus one ~60 ms after the re-equip), never
periodically while idle; standing, the actor's tick does only cheap branches. Suspects outside the release: the
dev probe itself (three `FindFirstOf` object-array scans every 0.5 s) and the dev box's UE4SS Lua mods
(InventoryTabs background loop, UltraPlus, DarkerNights, WalkWithWheels).
