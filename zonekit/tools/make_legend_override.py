"""Override of HUDContextualLegend with its text collapsed: no bottom-centre contextual key hint
("[G] Play guitar"; the same line also carries the drop-body and dialogue-skip hints). Same method as
ImmersiveDialogue's W_SkipHintView (its BUILD.md 5.6): the show/hide logic is native, so the layout is
hidden in the widget tree itself. HUDContextualLegend's tree is one RichTextBlock, LegendText.

Headless (editor closed):  powershell -File harness\\tools\\run_headless.ps1 -Script zonekit\\tools\\make_legend_override.py
"""
import unreal, os
LOG = os.environ.get("IMMCAMP_LOG_LEGEND", r"C:/Users/noahs/AppData/Local/Temp/make_legend_override.log")
PLUGIN = "ImmersiveCampfires"
SRC = "/Game/GameLite/FPS_Game/UIRemaster/HUD/HUDContextualHints/HUDContextualLegend"
DST = "/%s/GameLite/FPS_Game/UIRemaster/HUD/HUDContextualHints/HUDContextualLegend" % PLUGIN
EAL = unreal.EditorAssetLibrary
lines = []
def log(s):
    lines.append(str(s)); unreal.log("[ImmCamp] " + str(s))

try:
    if not EAL.does_directory_exist("/%s" % PLUGIN):
        url = "file:" + os.path.abspath(r"G:/Epic Games/STALKER2ZoneKit/Stalker2/Mods/%s/%s.uplugin" % (PLUGIN, PLUGIN)).replace("\\", "/")
        unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(url, unreal.GameFeaturePluginLoadComplete())
    log("mod mounted: %s" % EAL.does_directory_exist("/%s" % PLUGIN))
    if EAL.does_asset_exist(DST):
        log("override exists, deleting to rebuild"); EAL.delete_asset(DST)
    r = EAL.duplicate_asset(SRC, DST)
    if r is None:
        folder, name = DST.rsplit("/", 1)
        r = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, folder, unreal.load_asset(SRC))
    log("duplicate -> %s" % r)
    bp = unreal.load_asset(DST)
    hidden = 0
    for path in (DST + ".HUDContextualLegend:WidgetTree.LegendText",):
        w = unreal.find_object(None, path)
        log("%s -> %s" % (path, w))
        if w is None:
            continue
        w.modify()
        w.set_editor_property("visibility", unreal.SlateVisibility.COLLAPSED)
        w.set_editor_property("render_opacity", 0.0)
        log("  LegendText visibility=%s opacity=%s" % (w.get_editor_property("visibility"), w.get_editor_property("render_opacity")))
        hidden += 1
    if hidden:
        bp.modify()
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        log("saved: %s" % EAL.save_loaded_asset(bp, only_if_is_dirty=False))
        gen = unreal.find_object(None, DST + ".HUDContextualLegend_C:WidgetTree.LegendText")
        log("generated-class copy: %s vis=%s" % (gen, gen.get_editor_property("visibility") if gen else None))
    else:
        log("LegendText NOT FOUND, nothing saved")
except Exception:
    import traceback
    log("EXCEPTION: " + traceback.format_exc())
open(LOG, "w", encoding="utf-8").write("\n".join(lines))
