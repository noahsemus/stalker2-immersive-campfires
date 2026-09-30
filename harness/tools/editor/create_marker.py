"""Create a permanent compatibility marker asset other mods can detect (an empty CurveFloat).

    powershell -File harness\\tools\\run_headless.ps1 -Script harness\\tools\\editor\\create_marker.py \\
        -Arg "FOLDER=/<Mod>/<Mod>Compat","NAME=XX_Interface_v1"

In the mod folder it lives at FOLDER/NAME; listed in OverridePackages.txt it cooks to /Game/<same path minus the
mod root>, which is the path other mods load. Put an interface revision in the name, never the mod version, and never
rename or remove it once released (see docs/compatibility.md: ZST gated on a per-cook anchor and broke).
"""
import os
import unreal

FOLDER, NAME = ARGS["FOLDER"], ARGS["NAME"]
EAL = unreal.EditorAssetLibrary
if not EAL.does_asset_exist(f"{MOD_ROOT}/{MOD}"):
    try:
        unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(
            "file:" + os.path.abspath(UPLUGIN).replace("\\", "/"), unreal.GameFeaturePluginLoadComplete())
    except Exception as e:
        unreal.log(f"[harness] load_and_activate failed: {e}")
path = f"{FOLDER}/{NAME}"
if EAL.does_asset_exist(path):
    unreal.log(f"[harness] exists: {path}")
else:
    a = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, FOLDER, unreal.CurveFloat, unreal.CurveFloatFactory())
    unreal.log(f"[harness] created {a}; saved {EAL.save_asset(path, only_if_is_dirty=False)}")
