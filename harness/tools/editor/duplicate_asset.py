"""Duplicate an asset into the mod plugin (Blueprint graphs survive; a Move would leave a redirector at the old
path, which would still act as an override). Headless only for /Game sources (duplicate_asset returns None in the
open editor):

    powershell -File harness\\tools\\run_headless.ps1 -Script harness\\tools\\editor\\duplicate_asset.py \\
        -Arg "SRC=/Game/.../X","DST=/<Mod>/Runtime/X"

Log: <SCRATCH>/duplicate_asset.log and "[harness]" lines in the commandlet output.
"""
import os
import unreal

SRC, DST = ARGS["SRC"], ARGS["DST"]
LOG = os.path.join(SCRATCH, "duplicate_asset.log")
EAL = unreal.EditorAssetLibrary
lines = []


def log(s):
    lines.append(str(s)); unreal.log("[harness] " + str(s))


def mount_mod():
    """A headless run mounts neither the mod plugin nor its assets into the registry; activate it."""
    if not EAL.does_asset_exist(f"{MOD_ROOT}/{MOD}"):
        try:
            unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(
                "file:" + os.path.abspath(UPLUGIN).replace("\\", "/"), unreal.GameFeaturePluginLoadComplete())
        except Exception as e:
            log(f"load_and_activate failed: {e}")
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([MOD_ROOT], True)
    return EAL.does_asset_exist(f"{MOD_ROOT}/{MOD}")


try:
    log(f"mod mounted: {mount_mod()}")
    log(f"src exists: {EAL.does_asset_exist(SRC)}")
    if EAL.does_asset_exist(DST):
        log("dst exists already, deleting it first"); EAL.delete_asset(DST)
    dup = EAL.duplicate_asset(SRC, DST)
    if dup is None:   # AssetTools fallback (works in some editor states where EAL does not)
        folder, name = DST.rsplit("/", 1)
        dup = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, folder, unreal.load_asset(SRC))
    log(f"duplicate -> {dup}")
    if dup is None:
        raise RuntimeError("duplicate_asset returned None")
    log(f"saved: {EAL.save_asset(DST, only_if_is_dirty=False)}")
    log(f"verify: {EAL.does_asset_exist(DST)} class={unreal.load_asset(DST).get_class().get_name()}")
except Exception:
    import traceback
    log("EXCEPTION: " + traceback.format_exc())
os.makedirs(SCRATCH, exist_ok=True)
open(LOG, "w", encoding="utf-8").write("\n".join(lines))
