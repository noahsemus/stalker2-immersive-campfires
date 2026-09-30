"""Set one class-default value on a Blueprint (values awkward to enter in the UI, e.g. a soft class path).

    powershell -File harness\\tools\\run_headless.ps1 -Script harness\\tools\\editor\\set_bp_default.py \\
        -Arg "BP=/<Mod>/Runtime/BP_X","PROP=MyVar","VALUE=/<Mod>/Runtime/ABP_Y.ABP_Y_C"

Also works through ue_exec.py for plain values. A SoftClassProperty only accepts a real class object from Python;
the saved value is its soft path. VALUE is tried as a class, then as a SoftClassPath, then as the raw string.
"""
import os
import unreal

BP, PROP, VALUE = ARGS["BP"], ARGS["PROP"], ARGS["VALUE"]
EAL = unreal.EditorAssetLibrary


def log(s):
    unreal.log("[harness] " + str(s)); print(s)


if not EAL.does_asset_exist(f"{MOD_ROOT}/{MOD}"):
    try:
        unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(
            "file:" + os.path.abspath(UPLUGIN).replace("\\", "/"), unreal.GameFeaturePluginLoadComplete())
    except Exception as e:
        log(f"load_and_activate failed: {e}")
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([MOD_ROOT], True)
cls_path = BP + "." + BP.rsplit("/", 1)[1] + "_C"
cdo = unreal.get_default_object(unreal.load_class(None, cls_path))
log(f"before: {cdo.get_editor_property(PROP)}")
done = False
for make in (lambda: unreal.load_class(None, VALUE), lambda: unreal.SoftClassPath(VALUE), lambda: VALUE):
    try:
        v = make()
        if v is None:
            continue
        cdo.set_editor_property(PROP, v); done = True; break
    except Exception as e:
        log(f"set attempt failed: {e}")
if not done:
    raise RuntimeError("could not set property")
log(f"after: {cdo.get_editor_property(PROP)}")
log(f"saved: {EAL.save_asset(BP, only_if_is_dirty=False)}")
