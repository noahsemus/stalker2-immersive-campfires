"""Dump Input Mapping Context rows (action, key, mappable name, modifiers, triggers) to JSON.

    <kit python> harness/tools/ue_exec.py harness/tools/editor/dump_imc.py \\
        --arg "IMC=/Game/_Stalker_2/data/input/InputMappingContexts/IMC_Exploration;/<Mod>/..."

Output: <SCRATCH>/imc_dump.json. `mappable` must read OverrideSettings/<Name> on rows the player can rebind;
rows without a mappable name never receive the player's Options > Controls rebinds.
"""
import json
import os
import unreal

paths = [p for p in ARGS.get("IMC", "/Game/_Stalker_2/data/input/InputMappingContexts/IMC_Exploration").split(";") if p]
out = []


def desc(o):
    if o is None:
        return None
    d = {"class": o.get_class().get_name()}
    for prop in ("order", "value_type", "deadzone", "lower_threshold", "upper_threshold", "type", "scalar",
                 "hold_time_threshold", "is_one_shot", "tap_release_time_threshold"):
        try:
            d[prop] = str(o.get_editor_property(prop))
        except Exception:
            pass
    return d


def mappable(m):
    try:
        beh = str(m.get_editor_property("setting_behavior")).rsplit(".", 1)[-1]
    except Exception:
        beh = None
    try:
        s = m.get_editor_property("player_mappable_key_settings")
        name = str(s.get_editor_property("name")) if s else None
    except Exception:
        name = None
    return f"{beh}/{name}"


for path in paths:
    imc = unreal.load_asset(path)
    if not imc:
        out.append({"imc": path, "error": "load failed"}); continue
    for m in imc.get_editor_property("mappings"):
        act = m.get_editor_property("action")
        out.append({"imc": path.rsplit("/", 1)[1],
                    "action": act.get_name() if act else None,
                    "action_value_type": str(act.get_editor_property("value_type")) if act else None,
                    "action_triggers": [desc(x) for x in act.get_editor_property("triggers")] if act else None,
                    "key": str(m.get_editor_property("key").get_editor_property("key_name")),
                    "mappable": mappable(m),
                    "modifiers": [desc(x) for x in m.get_editor_property("modifiers")],
                    "triggers": [desc(x) for x in m.get_editor_property("triggers")]})
os.makedirs(SCRATCH, exist_ok=True)
dst = os.path.join(SCRATCH, "imc_dump.json")
open(dst, "w", encoding="utf-8").write(json.dumps(out, indent=1))
print(f"IMC dump: {len(out)} rows -> {dst}")
