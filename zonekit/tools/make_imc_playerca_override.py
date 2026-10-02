"""Regenerates the mod's IMC_PlayerCA override (PLAN.md Layer 1, BUILD.md 5.1). Runs headless:

  Stalker2ModEditor-Win64-Shipping-Cmd.exe "<kit>\Stalker2\Stalker2.uproject" -run=pythonscript -script=<this file> -unattended -nosplash -stdout -NoShaderCompile

Derived from make_imc_override.py (ImmersiveDialogue's IMC_Dialog generator).

What it does:
  1. duplicates the vanilla IMC_PlayerCA (the seated-at-campfire context, priority
     Exclusive) into the mod plugin at the mirrored path; keeps every vanilla row;
  2. duplicates IMC_Exploration to a temporary asset and MOVES (rename outer) the
     trigger and player-mappable-settings objects of every PDA / inventory / quick-slot /
     item-selector row into the override, then adds a copy of each row. Moving the
     mappable settings keeps each row's PlayerMappableOption name (OpenPDA, QuickSlot1,
     ...), so the player's Options > Controls rebinds reach the seated rows too. Rows
     with key None (the "Alt" slots) are kept: they carry the Alt mappable names;
  2b. sets the mouse-look row's trigger threshold to 0.0 like IMC_Exploration (vanilla 0.5 dropped small movements);
  3. unless IMMCAMP_CANARY=0, adds the canary row IA_PlayerCAExit on BackSpace, so a
     test run can tell "override not loaded" from "action vetoed" (remove for release);
  4. saves the override. The temp asset is never saved; do NOT delete_asset it
     (crashes the commandlet).
"""
import unreal, os, time
LOG = os.environ.get("IMMCAMP_LOG", r"C:/Users/noahs/AppData/Local/Temp/make_imc_playerca_override.log")
CANARY = os.environ.get("IMMCAMP_CANARY", "1").strip() != "0"
PLUGIN = "ImmersiveCampfires"
lines = []
def log(s):
    lines.append(str(s)); unreal.log("[ImmCamp] " + str(s))
SRC_CA     = "/Game/_Stalker_2/data/input/InputMappingContexts/IMC_PlayerCA"
SRC_EXPLO  = "/Game/_Stalker_2/data/input/InputMappingContexts/IMC_Exploration"
DST_DIR    = "/%s/_Stalker_2/data/input/InputMappingContexts" % PLUGIN
DST        = DST_DIR + "/IMC_PlayerCA"
TMP        = DST_DIR + "/IMC_ExplorationTmp_%d" % int(time.time())   # unique per run, never saved
IA_EXIT    = "/Game/_Stalker_2/data/input/InputActions/Delayable/IA_PlayerCAExit"
COPY_ACTIONS = {"IA_OpenPDA", "IA_Inventory", "IA_QuickSlot1", "IA_QuickSlot2",
                "IA_QuickSlot3", "IA_QuickSlot4", "IA_ItemSelector"}
EAL = unreal.EditorAssetLibrary

def dup(src, dst):
    r = EAL.duplicate_asset(src, dst)
    if r is None:
        folder, name = dst.rsplit("/", 1)
        r = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, folder, unreal.load_asset(src))
    return r

def prop(o, name, default=None):
    try:
        return o.get_editor_property(name)
    except Exception:
        return default

def mappable_desc(m):
    beh = prop(m, "setting_behavior")
    s = prop(m, "player_mappable_key_settings")
    nm = prop(s, "name") if s else None
    return "%s/%s" % (str(beh).rsplit(".", 1)[-1] if beh is not None else "-", nm if nm else "-")

def describe(m):
    a = prop(m, "action"); k = prop(m, "key")
    return "%-28s %-26s mappable=%-32s mods=%s trig=%s" % (
        a.get_name() if a else None, str(k.get_editor_property("key_name")), mappable_desc(m),
        [x.get_class().get_name() for x in prop(m, "modifiers", []) if x],
        [x.get_class().get_name() for x in prop(m, "triggers", []) if x])

try:
    log("canary=%s" % CANARY)
    mounted = EAL.does_asset_exist("/%s/%s" % (PLUGIN, PLUGIN)) or EAL.does_directory_exist("/%s" % PLUGIN)
    log(f"mod content mounted: {mounted}")
    if not mounted:
        url = "file:" + os.path.abspath(r"G:/Epic Games/STALKER2ZoneKit/Stalker2/Mods/%s/%s.uplugin" % (PLUGIN, PLUGIN)).replace("\\", "/")
        try:
            unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(url, unreal.GameFeaturePluginLoadComplete())
        except Exception as e:
            log(f"load_and_activate failed: {e}")
        mounted = EAL.does_asset_exist("/%s/%s" % (PLUGIN, PLUGIN)) or EAL.does_directory_exist("/%s" % PLUGIN)
        log(f"mod content mounted after activate: {mounted}")
    log("GameFeatureData exists: %s" % EAL.does_asset_exist("/%s/%s" % (PLUGIN, PLUGIN)))

    # 1. Duplicate IMC_PlayerCA into the mod at the mirrored path.
    if EAL.does_asset_exist(DST):
        log("override exists already, deleting to rebuild")
        EAL.delete_asset(DST)
    log(f"duplicate -> {dup(SRC_CA, DST)}")
    imc = unreal.load_asset(DST)
    kept = list(imc.get_editor_property("mappings"))
    log(f"vanilla rows kept: {len(kept)}")

    # 2. Move the item / PDA rows' objects out of a throwaway copy of IMC_Exploration.
    log(f"temp exploration copy -> {dup(SRC_EXPLO, TMP)}")
    tmp = unreal.load_asset(TMP)
    def take(o):
        if o is None: return None
        if not o.rename(outer=imc): log(f"   rename(outer=override) FAILED for {o.get_class().get_name()}")
        return o
    added = 0; mappable = 0
    for m in tmp.get_editor_property("mappings"):
        a = m.get_editor_property("action")
        if not a or a.get_name() not in COPY_ACTIONS: continue
        nm = unreal.EnhancedActionKeyMapping()
        nm.set_editor_property("action", a)
        nm.set_editor_property("key", m.get_editor_property("key"))
        nm.set_editor_property("modifiers", [take(x) for x in m.get_editor_property("modifiers")])
        nm.set_editor_property("triggers",  [take(x) for x in m.get_editor_property("triggers")])
        beh = prop(m, "setting_behavior")
        if beh is not None:
            try: nm.set_editor_property("setting_behavior", beh)
            except Exception as e: log(f"   set setting_behavior failed: {e}")
        s = prop(m, "player_mappable_key_settings")
        if s is not None:
            try:
                nm.set_editor_property("player_mappable_key_settings", take(s)); mappable += 1
            except Exception as e: log(f"   set player_mappable_key_settings failed: {e}")
        legacy = prop(m, "player_mappable_options")
        if legacy is not None:
            try: nm.set_editor_property("player_mappable_options", legacy)
            except Exception as e: log(f"   set player_mappable_options failed: {e}")
        log(f"  + {describe(nm)}")
        kept.append(nm); added += 1
    log(f"added {added} rows ({mappable} with mappable settings)")

    # 2b. Mouse look: the vanilla row (IA_LookUp / Mouse2D, trigger Down) has actuation threshold 0.5, IMC_Exploration's
    #     has 0.0. With this context in charge, mouse deltas that are small after the sensitivity drop out (small, slow
    #     movements ignored, the view feels laggy; tester + Nexus user, v1.0.1). Match exploration.
    for m in kept:
        a_ = prop(m, "action"); k_ = prop(m, "key")
        if a_ and a_.get_name() == "IA_LookUp" and str(k_.get_editor_property("key_name")) == "Mouse2D":
            for t in prop(m, "triggers", []) or []:
                log(f"  mouse look trigger {t.get_class().get_name()} threshold {t.get_editor_property('actuation_threshold')} -> 0.0")
                t.set_editor_property("actuation_threshold", 0.0)

    # 3. Canary: a second stand-up key. No trigger = fires on press, like the vanilla rows.
    if CANARY:
        c = unreal.EnhancedActionKeyMapping()
        c.set_editor_property("action", unreal.load_asset(IA_EXIT))
        k = unreal.Key(); k.set_editor_property("key_name", "BackSpace")
        c.set_editor_property("key", k)
        kept.append(c)
        log(f"  + CANARY {describe(c)}")

    imc.set_editor_property("mappings", kept)
    log(f"total rows now {len(kept)}")
    log(f"saved: {EAL.save_loaded_asset(imc, only_if_is_dirty=False)}")
    for m in unreal.load_asset(DST).get_editor_property("mappings"):
        log("  VERIFY " + describe(m))
except Exception:
    import traceback
    log("EXCEPTION: " + traceback.format_exc())
open(LOG, "w", encoding="utf-8").write("\n".join(lines))
