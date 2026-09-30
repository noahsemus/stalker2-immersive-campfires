"""Export any asset's graphs as T3D text without the tester (AssetExportTask), e.g. to read a Blueprint or
AnimBlueprint back after a paste, or to lift the game's own nodes with harness/tools/t3d/t3d_lift.py.

    <kit python> harness/tools/ue_exec.py harness/tools/editor/export_t3d.py --arg "ASSET=/Game/.../AnimBP_X"

Output: <SCRATCH>/<AssetName>.t3d. The export also lists deleted-but-not-garbage-collected nodes; trust each
graph's `Nodes(n)` list, not every K2Node_* block in the file.
"""
import os
import unreal

asset = unreal.load_asset(ARGS["ASSET"])
if asset is None:
    raise RuntimeError("load failed: " + ARGS["ASSET"])
os.makedirs(SCRATCH, exist_ok=True)
dst = os.path.join(SCRATCH, asset.get_name() + ".t3d")
t = unreal.AssetExportTask()
t.object = asset
t.filename = dst
t.automated = True
t.prompt = False
t.replace_identical = True
t.exporter = None
ok = unreal.Exporter.run_asset_export_task(t)
print(f"export ok={ok} -> {dst} ({os.path.getsize(dst) if os.path.exists(dst) else 0} bytes)")
