# Blueprints: paste text, reading graphs back, editor Python, editor traps

## Blueprint nodes as clipboard text (T3D)
Graph nodes copy/paste as plain text: `Begin Object Class=/Script/BlueprintGraph.K2Node_... Name="..."`, one
`CustomProperties Pin (...)` line per pin, links as `LinkedTo=(NodeName PinId,)`, `End Object`. Proven for blocks
of 20-200 nodes (event graphs and anim graphs).

1. Ask the tester to select a few existing nodes of the needed types in the editor and press Ctrl+C. Read them with
   PowerShell `Get-Clipboard -Raw`: that is the exact pin format for this engine build. Or export a whole asset
   yourself: `ue_exec.py tools/editor/export_t3d.py --arg ASSET=/Game/...` (no tester).
2. Generate the block with `tools/t3d/bp_graph.py` (declare nodes and pins, `graph.link(a, b)` writes links on
   **both** ends, `graph.box(...)` comment boxes) on top of `bp_t3d.py` (pin/type strings, fresh 32-hex GUIDs).
   `t3d_lift.py` lifts real nodes out of an exported T3D (e.g. the game's own AnimGraph nodes with their nested
   binding sub-objects), renames them, gives every pin a fresh id and lets you relink them.
3. Put it on the clipboard (`Set-Clipboard -Value (Get-Content <file> -Raw)`), the tester clicks into the graph and
   presses Ctrl+V, then wires only the 1-3 pins that connect to nodes outside the block. **Links to nodes that are
   not in the paste are dropped**, so keep external wiring minimal and name those pins exactly.
4. They compile and save; read it back with `export_t3d.py` to verify (the export lists deleted-but-not-GC'd nodes
   too: trust each graph's `Nodes(n)` list).

**Readable paste layout (tester-approved, Looting 2026-10-10: "best layout so far"):** call `graph.layout_tree()`
before writing. It
- clones every pure node that feeds more than one pin (pure nodes are re-evaluated per use anyway), so each data
  input sits right next to the node that uses it;
- inside each comment box runs the exec chain left to right on a row, each exec node's data inputs as a small tree
  directly to its left; Branch false / Sequence then_1.. open rows below; chains longer than `max_row` wrap;
- places the boxes along the flow: a box entered from another box sits to its right, boxes fed by one box are
  stacked in the order of the pins that feed them, unfed boxes (events) start new groups; boxes are resized to fit.
Generator rules that keep it readable: put every exec node inside a comment box (hand coordinates only choose the
box; an input event and its chain need a box of their own), and never wire one exec output (a cast's `As X`, a
spawn's `Return Value`) to many places: store it in a variable right after the exec node and read the variable at
each use (`self_get` creates one getter per use), or the wires fan out across the whole graph. `layout()` (a plain
column grid) is kept only for comparison; it was harder to follow.

Put `NodeComment` labels and comment boxes in the generated text (see `collaboration.md`). Keep mod-specific
generators in the mod's `zonekit/tools/gen_*.py`; lift reusable node builders into `bp_graph.py` here.

- **Delegate binding pastes fine**: `K2Node_AddDelegate` (`DelegateReference=(MemberParent=<class>,MemberName=...)`,
  a `Delegate` pin whose `PinSubCategoryMemberReference` names the `..._DelegateSignature` in its package) linked to a
  `K2Node_CustomEvent` whose parameters come from `CustomProperties UserDefinedPin (PinName=...,PinType=(...),
  DesiredPinDirection=EGPD_Output)`. Bind once per target object (keep the bound object in a variable and compare).
  Campfires binds `AnimInstance.OnMontageStarted` this way.
- **Don't call a custom event of the same graph from pasted text**: the paste asks to "Fix Self Context Function
  References" and the compile fails ("In use pin no longer exists"). Drive the follow-up from the tick (a flag or a
  timestamp checked each tick) instead.

- **ForEachLoop paste**: `K2Node_MacroInstance` with `MacroGraphReference=(MacroGraph="/Script/Engine.EdGraph'/Engine/
  EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'",GraphBlueprint=...StandardMacros'",
  GraphGuid=99DBFD5540A796041F72A5A9DA655026)` (GUID read from the kit's `Engine/Content/EditorBlueprintResources/
  StandardMacros.uasset`), `ResolvedWildcardType=(PinCategory="object",PinSubCategoryObject=<class>)`, pins `Exec`,
  `Array` (container Array), `LoopBody`, `Array Element`, `Array Index`, `Completed`.
- Function purity after a paste comes from the UFunction (`bDefaultsToPureFunc`), not the pasted `bIsPureFunc`:
  write `const` getters (BlueprintCallable const = pure) without exec pins and static library calls with them, or the
  reconstructed node drops the exec links.
- **A pasted call to a BlueprintInternalUseOnly function is silently dropped** (no error, its links vanish): e.g.
  `KismetMathLibrary` `Ease` / `VEase` / `REase` belong to the `K2Node_EaseFunction` node. Ease by hand
  (`alpha * alpha` + `VLerp`). After every paste, export the graph and compare node and link counts with the
  generated text (match by function + comment, not node name: the editor renames nodes that collide with deleted,
  not yet garbage-collected ones).
- Static library functions are impure unless declared BlueprintPure: e.g. `KismetMaterialLibrary.GetScalarParameterValue`
  pasted without exec pins compiles with "was pruned because its Exec pin is not connected" and reads 0. Put such calls
  in the exec chain and keep their results in variables.
- **Cast output pin names use the class display name with spaces**: `AsInput Mapping Context`,
  `AsInteractable Item Container`, `AsDead Body` (a misspelled pin silently drops its links).
- From Git Bash, `ue_exec.py --arg ASSET=/Mod/...` gets its path rewritten to `C:/Program Files/Git/Mod/...` (MSYS
  path conversion): run it from PowerShell or with `MSYS_NO_PATHCONV=1`.
- `ue_exec.py`: UE's remote execution treats a command as a FILE path when its text contains `<something>.py`
  early (e.g. a docstring saying "run with ue_exec.py ..."): "Could not load Python file". Keep `.py` names out of
  the first lines of scripts sent with it. A script that raises leaves its previous output file in place: delete the
  output before the run, or you read stale results.
- `UUserWidget::GetWidgetFromName` is not Blueprint-callable in 5.5; native widget members bound with BindWidget are
  usually not BP-visible either. Find a child widget by `GetAllWidgetsOfClass(<its class>, TopLevelOnly=false)` +
  `GetPathName` contains `<Parent>.WidgetTree.<Child>` (once, on an edge).

Blueprint "Float" variables are doubles. `BlueprintEditorLibrary.add_member_variable` adds variables from Python;
`reparent_blueprint` reparents; Blueprint graphs themselves cannot be authored from Python (only pasted).

## Editor Python
- **Remote execution** (Project Settings → Plugins → Python → Enable Remote Execution; not in Editor Preferences)
  lets `tools/ue_exec.py <file|code>` run scripts in the tester's open editor in seconds. The harness prelude gives
  scripts `MOD`, `MOD_ROOT`, `UPLUGIN`, `SCRATCH`, `ARGS`.
- In the live editor, `EditorAssetLibrary.duplicate_asset` and `AssetTools.duplicate_asset` return **None for /Game
  sources**; run duplication headless (`run_headless.ps1 tools/editor/duplicate_asset.py`) or edit existing mod
  assets in place.
- `unreal.new_object(cls, outer)` works for small sub-objects (e.g. `PlayerMappableKeySettings`). Setting properties
  on freshly created modifier/trigger objects fails with "cannot be edited on templates": **move** the real objects
  from a duplicated source instead (`rename(outer=...)`, see `input.md`).
- A SoftClassProperty only accepts a real class object from Python (`tools/editor/set_bp_default.py`).
- CDO flags such as `AutoReceiveInput = Player0` on an actor Blueprint can be set from Python.

## Editor traps
- **Save before Compile** on big edits; a compiler crash loses unsaved work. Wait ~10 s after a save before cooking.
- After any asset rename: Compile every referencer (bytecode is stale until then) and re-check pins; use
  `tools/editor/move_asset.py`, which also deletes the redirector (a redirector in Content gets cooked).
- **Property Access nodes only inside AnimGraphs / transition rules**; in an event graph one crashed the compiler.
- The editor crashed when it auto-reopened an overridden `AnimBP_Player` at startup (compile-on-load before mod
  classes exist). Open such assets by hand; if a crash loop starts, delete the `OpenAssetsAtExit=` lines from
  `%LOCALAPPDATA%\Stalker2\Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini` (editor closed).
- Opening the pawn Blueprint once crashed while a modified `AnimBP_Player` sat in the same mod (the pawn editor
  previews the anim class); move the anim asset out temporarily if it recurs.
- **Overridden assets exist twice at runtime** (`/Game/...` and `/<Mod>/...`), and the editor redirects every `/Game`
  pick of an overridden asset to the mod path. Only the game-path object gets the game's runtime treatment (e.g. the
  player's rebinds), so load it by path string when it matters (`input.md`).
- **A pasted `0.0` on a function pin whose C++ default is non-zero comes back as the default** (e.g.
  `Montage_SetPlayRate.NewPlayRate` = 1.0); feed such values from a node output. Blueprint T3D exports also carry
  deleted nodes, so verify pin values in game (probe), not in an export.
- A pasted pure `K2Node_DynamicCast` (`bIsPureCast=True`) comes in as an exec cast; wire its exec pins.
- `Print String` is stripped in Shipping: trace with visible side effects or a dev-box probe (`diagnostics.md`).
- Anim notify / linked-layer pins: a Linked Anim Graph node only exposes an `In Pose` pin if the target's AnimGraph
  function has one; our pass-through ABP never offered it (dead end, `animation.md`).
