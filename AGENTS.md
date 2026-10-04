# ImmersiveCampfires — mod context for the agent

**First read `harness/AGENTS.md`**: the shared rules, tester workflow, pipeline and game knowledge for every
Stalker 2 mod. They apply here. This file holds only what is specific to this mod.

Purpose: while seated at a campfire, Skif can eat, drink, open the PDA and inventory, inspect artifacts and play the
guitar, with proper first-person animations. Sleeping at the fire is core scope (Noah, 2026-09-27), not stretch.

Repo `noahsemus/stalker2-immersive-campfires` (renamed from "Campfire Actions" on 2026-09-27; the old URL
redirects), Zone Kit plugin `ImmersiveCampfires` (`/ImmersiveCampfires/`), asset prefix `ImmCamp`. Adopted into the
harness on 2026-09-30. Sibling of `stalker2-immersive-dialogue`, which shipped the same runtime-host pattern.

## Current state (one line per checkpoint / release: date, what changed, what the tester confirmed in game)
- 2026-09-27: Layer 1 kit checks done (no asset-side veto, no key collisions; `zonekit/README.md`). Plugin created.
- 2026-09-29: own seated mode (builds 14-19): the vanilla sit is taken over once it idles; no post-process ABP
  (every post-load swap crashed). Key sync: only the player's own keys work seated. Noah confirmed P / I / quick
  slots work seated with custom keys.
- 2026-09-29/30 (builds 20-31): poses are yaw tables played as a paused dynamic montage in `FullBody`, frame set
  every tick from the view (`zonekit/tools/make_sit_yaw.py`): `AS_ImmCamp_SitRest` (plain, 151 yaw rows x 23 pitch
  keys) at rest, `AS_ImmCamp_SitAdditive` (additive on the item stance `fp_ar_idle_stand`) while an item / PDA /
  backpack montage runs. Noah confirmed: legs stay put, drink / PDA / backpack / PIR stimpak centred, W stands up,
  pistol back, guitar comes out, putting it away returns to the seated mode.
- 2026-09-30 build 32: pose position compensated for the anim update's advance; the paused rate (0.0001, pasted 0.0
  reverts to 1.0) now holds too. Noah: "best build by far": camera smooth, items good, guitar stays seated and returns
  to the seated mode, walking after standing works. Open: brief input drop every ~1 s after an item, pistol shown
  for a moment after an item (game re-equips it), a short body turn when the guitar comes out, sleep not started.

- 2026-09-30 build 33 = release candidate (Noah): pistol hidden the moment the game re-equips it, the seat faced
  before the guitar hand-back (no body swing), a lost resting pose snaps back instead of easing. Open: a brief
  mouse-look drop about once a second, also after leaving the campfire (Noah saw it before without the mod); the
  build 33 log shows no pose restarts between actions, so it is not the seated-mode logic (see zonekit/README.md).

- 2026-09-30 build 36 (Noah: best release candidate so far): at rest the body is pinned to the seat (mesh world
  rotation) and the camera unhooked (absolute rotation = actor yaw + look pitch); during actions both go back. Body
  jitter gone, guitar seamless. Open: camera control lost for a moment when an item starts / ends, the separate
  shadow mesh still turns with the view (second shadow).

- 2026-10-01 builds 37-77 (Noah: "best so far", checkpoint): camera free and smooth at rest and on stand-up (view eases
  to level / body-forward, look locked while getting up, body does not turn), guitar hint gone (HUDContextualLegend
  override, LegendText collapsed), Sleeping Bag Mod while seated = stand up + its hours popup (its Config's
  "On Widget Init" by name; never touch its tick order: four crashes), full vanilla item animations, arms ease into
  the lap only after the item's own animation (last 0.15 s), injector (LeftHand slot) counts as busy, the game's
  weapon draw after items cut at once, pose tables start on the right frame. Open: the body jumps / shifts after an
  item animation.

- 2026-10-01 v1.0.0 released (Noah: "FINALLY it works"). Builds 78-84: the item is held just before its final reach
  (per-item measured times, live hand-speed check for modded items) while the rest pose blends in (0.55 s), camera
  stays on the head until the item is let go, and NO RemoveWeaponFromHands when the arms leave an item (it swapped the
  stance layer in one frame: hips 8 cm, hands 30 cm = every "arm pops / reaches out" since build 59). Canary removed.
  Build 85 (same v1.0.0, before the Nexus upload; Noah: "beautiful"): the Sleeping Bag Mod stand-up stays unarmed
  (weapon the backpack close re-equips removed at once, hand meshes hidden while getting up, no weapon back).
  Builds 86-87 (same v1.0.0; Noah: "looks great"): items used from the backpack (vanilla and PIR) no longer flip
  rest / free arms every ~0.1 s: the item is the last montage the game started (`OnMontageStarted`, bound per anim
  instance; ours skipped by play length > 1000 s), not `GetCurrentActiveMontage`.

- 2026-10-01 v1.0.1 (Noah: "good works"): saving was blocked after any sit (the takeover ended the vanilla sit by
  clearing the interaction target; the game only unlocks saves when the sit's own exit finishes). Builds 88-90:
  stand-up hands the body back to the vanilla sit (`SetInteractionTarget(TargetSaved)`, seat point under us), the
  sit montage starts at 3.93 s from the montage-started event (no sit-down frame; our pose stays on until then),
  `InjectInputForAction(IA_PlayerCAExit)` at idle, our end steps once the game's sit is over (tick step 12).

- 2026-10-02 v1.0.2 (Noah: "IT'S FIXED"): stand up holstered (build 91, Nexus feedback); mouse look dropped small
  movements while IMC_PlayerCA was in charge (also after a backpack item, even standing): its IA_LookUp/Mouse2D Down
  trigger has actuation threshold 0.5 (IMC_Exploration 0.0); the override now sets 0.0 (build 99). Builds 93-98
  (input-mode re-grab, flush, one-frame pause, input delay, detector toggle) did nothing and were removed.

- 2026-10-03 v1.0.3 (Noah: "nice it works"): Sleeping Bag Mod while seated broke in v1.0.1 (stood up, no window):
  `K2_SetTimer(Config, "On Widget Init")` no longer opened it (build 100: two calls, probe: no window). Build 101:
  after standing, its location RTPC = 1 and its bag-use RTPC = 1 on the player; its own tick opens the window
  (~0.8 s); location restored 4 s later. One direct call kept as a backup.

Open requests: compatibility with **Player Gestures**' "sit anywhere" (Nexus 1674,
https://www.nexusmods.com/stalker2heartofchornobyl/mods/1674; asked by a Nexus user, Noah: TBD). Start by inspecting
how its sit works (its paks; is it a `PlayerContextualAction`-style sit or its own montage) before planning.

## Key facts (verified; details in `zonekit/README.md`)
- Campfire sit = `PlayerContextualAction` actor + `PC.bInContextualAction` + input context `IMC_PlayerCA` (priority
  Exclusive; W/A/S/D/Space/F/Esc = `IA_PlayerCAExit`). While any interaction is in progress native PDA / backpack /
  item paths refuse, hence the takeover (`ResetInteractionTarget` + `EnableInputAfterInteraction`).
- Vanilla sit montage `MG_fp_ca_gd_bonfire` (`FullBody`, sections In 0-4 s / Idle 4-10 / Out 10-14). The vanilla
  sit waits for the `InteractAction` notify at 3.9996 s: a section jump over it leaves the sit state unset (stuck);
  `Montage_SetPosition(3.93)` keeps it.
- Item / PDA / backpack montages use `MainActionSlot` (Project Itemization Reborn uses `DefaultSlot`); all of them
  key the hips 7.4 cm / 19 deg away from `fp_bh_idle_stand` (= `fp_ar_idle_stand`).
- `PC.GetControlRotation` and `Controller.GetControlRotation` return the camera view (feedback if a pose drives the
  camera); the controller actor's rotation never updates. The game's own look pitch is
  `AnimInstancePlayer.CameraData.ClampedControlPitch` = explicit time of `fp_bh_stand_lookvertical_idle`
  (0 = +90 deg, 1 = -90 deg).
- A pasted `0.0` on a function pin whose C++ default is non-zero (e.g. `Montage_SetPlayRate.NewPlayRate`) comes back
  as the default; exports of the Blueprint also carry deleted nodes, so check pin values in game, not in the export.
- `PC.SaveStatesBeforeInteraction` stores the weapon like the vanilla sit but pinned the view pitch and left WASD dead
  after standing (build 28): not used. `Obj.RemoveWeaponFromHands` hides the weapon (type stays equipped).
- Guitar state: `AnimInstancePlayer.GuitarData.bPlayingGuitar`; guitar action
  `/Game/_Stalker_2/data/input/InputActions/Guitar/IA_GuitarContextualAction`.
- `PC` class members: `<kit>\bp_api_dump2.txt` from line 5141; player-state enums only in `bp_api_dump.txt`.

## Assets this mod may override
- `IMC_PlayerCA` (22 vanilla + 21 exploration rows + the BackSpace canary on `IA_PlayerCAExit`).
- The sit-actor Blueprint (fallback host only) and `BP_Stalker2Bonfire` (sleep) if ever needed.
- Never `BP_Stalker2Character`, `AnimBP_Player`, `AnimBP_player_bh`, `IMC_Exploration` or any `.cfg`
  (ImmersiveDialogue overrides the pawn; ZST / Immersive HUD override `AnimBP_Player` / `IMC_Exploration`).

## Runtime host
`BP_ImmCampSubsystem` (ModWorldSubsystem, `Autogenerated_1790710477_WorldSubsystemData` in OverridePackages) spawns
`BP_ImmCampActor`, whose whole event graph is generated by `zonekit/tools/gen_actor_seated_mode.py` (Noah: select all,
delete, paste, save, compile). Member variables are added from Python (`BlueprintEditorLibrary.add_member_variable`)
before a paste that needs them.

## Files
- `PLAN.md` plan and test matrix · `BUILD.md` every edit asset by asset · `zonekit/README.md` engineering log
  (what each test showed, dead ends) · `zonekit/ImmersiveCampfires/` plugin mirror · `zonekit/tools/` mod-specific
  generators, classifier lists and the dev-box probe source (`probe/ImmCampProbeCpp`, built via the
  ImmersiveDialogue CMake tree) · `zonekit/builds/` checkpoint and release paks · `mod.json` names and pak suffixes.
- `CLAUDE.md` / `GEMINI.md` only import `harness/AGENTS.md` and this file, for tools that don't read `AGENTS.md`.

## Release (only when the tester says "cut a release")
Follow `harness/docs/pipeline.md` § Release; test matrix in `PLAN.md` includes the pad and the coexistence test
with ImmersiveDialogue. Remove the canary row first. Nexus page: mod 2894, https://www.nexusmods.com/stalker2heartofchornobyl/mods/2894 (author account geoffjeffrey).
