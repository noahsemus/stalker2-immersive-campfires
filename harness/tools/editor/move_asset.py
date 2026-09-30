"""Rename/move an asset inside the mod plugin and fix up referencing Blueprints. Deletes the redirector left at the
old path (a redirector in the mod's Content would get cooked). Editor CLOSED:

    powershell -File harness\\tools\\run_headless.ps1 -Script harness\\tools\\editor\\move_asset.py \\
        -Arg "SRC=/<Mod>/old/X","DST=/<Mod>/new/X"

Afterwards open and Compile every referencer (compiled bytecode is stale until then) and re-check pins: a K2 pin
default once failed to follow a rename.
"""
import os
import unreal

SRC, DST = ARGS["SRC"], ARGS["DST"]
LOG = os.path.join(SCRATCH, "move_asset.log")
EAL = unreal.EditorAssetLibrary
lines = []


def log(s):
    lines.append(str(s)); unreal.log("[harness] " + str(s))


try:
    if not EAL.does_asset_exist(f"{MOD_ROOT}/{MOD}"):
        try:
            unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(
                "file:" + os.path.abspath(UPLUGIN).replace("\\", "/"), unreal.GameFeaturePluginLoadComplete())
        except Exception as e:
            log(f"load_and_activate failed: {e}")
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    ar.scan_paths_synchronous([MOD_ROOT], True)
    log(f"referencers of src: {[str(r) for r in (ar.get_referencers(SRC, unreal.AssetRegistryDependencyOptions()) or [])]}")
    if not EAL.rename_asset(SRC, DST):
        raise RuntimeError("rename_asset failed")
    if EAL.does_asset_exist(SRC):
        log(f"deleting redirector at src: {EAL.delete_asset(SRC)}")
    log(f"save dirty: {EAL.save_directory(MOD_ROOT, only_if_is_dirty=True, recursive=True)}")
    ar.scan_paths_synchronous([MOD_ROOT], True)
    log(f"after: {[str(a.package_name) for a in ar.get_assets_by_path(MOD_ROOT, recursive=True)]}")
except Exception:
    import traceback
    log("EXCEPTION: " + traceback.format_exc())
os.makedirs(SCRATCH, exist_ok=True)
open(LOG, "w", encoding="utf-8").write("\n".join(lines))
