"""Generates the whole BP_ImmCampSubsystem event graph as paste text (replace the graph with it).

Event On Initialized -> Set Tick Enabled(true)       (ModWorldSubsystem ticks only when enabled;
                                                      same as ImmersiveDialogue's BP_ImmDlgSubsystem)
Event On Tick -> Branch(Is Valid(SeatedActor))       (one cheap check per tick)
   false -> SpawnAttempts += 1 -> Spawn Actor from Class(BP_ImmCampActor) -> Set SeatedActor
Build 1 spawned once and turned tick off; in game the subsystem existed but no actor did, so the
actor is now re-spawned whenever it is missing. SpawnAttempts is read by the dev probe.
Needs the variables SeatedActor (BP_ImmCampActor ref) and SpawnAttempts (int) on the Blueprint
(added from Python with BlueprintEditorLibrary.add_member_variable).
Usage: python gen_subsystem_spawn.py <out.txt>
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from bp_t3d import G, pin, head, comment_box, cls, TGT, write

MWS = cls("/Script/Stalker2.ModWorldSubsystem")
OBJ = cls("/Script/CoreUObject.Object")
ACTOR = cls("/Script/Engine.Actor")
KML = cls("/Script/Engine.KismetMathLibrary")
KSL = cls("/Script/Engine.KismetSystemLibrary")
XFORM = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Transform'\""
VEC = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Vector'\""
ROT = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Rotator'\""
ACT_BPGC = "\"/Script/Engine.BlueprintGeneratedClass'/ImmersiveCampfires/Runtime/BP_ImmCampActor.BP_ImmCampActor_C'\""
ACT_PATH = "/ImmersiveCampfires/Runtime/BP_ImmCampActor.BP_ImmCampActor_C"

N = dict(init="K2Node_Event_900", tick="K2Node_Event_901", on="K2Node_CallFunction_900",
         spawn="K2Node_SpawnActorFromClass_900", mk="K2Node_CallFunction_901",
         valid="K2Node_CallFunction_903", br="K2Node_IfThenElse_900", getact="K2Node_VariableGet_900",
         getn="K2Node_VariableGet_901", add="K2Node_CallFunction_904", setn="K2Node_VariableSet_900",
         setact="K2Node_VariableSet_901")
P = {k: G() for k in ("init_then on_ex tick_then br_ex br_c br_f valid_in valid_ret getact_out getn_out "
                      "add_a add_ret setn_ex setn_then setn_in sp_ex sp_then sp_ret sp_xf mk_ret "
                      "setact_ex setact_in").split()}


def event(name, member, x, y, then_pid, then_links, extra_pins=()):
    return head("/Script/BlueprintGraph.K2Node_Event", name, x, y, "",
                [f"EventReference=(MemberParent={MWS},MemberName=\"{member}\")", "bOverrideFunction=True"]) + [
        pin(G(), "OutputDelegate", "delegate", out=True).replace(
            "PinType.PinSubCategoryMemberReference=()",
            f"PinType.PinSubCategoryMemberReference=(MemberParent={MWS},MemberName=\"{member}\")"),
        pin(then_pid, "then", "exec", out=True, links=then_links)] + list(extra_pins) + ["End Object"]


def libfn(name, lib, libname, member, x, y, pins, comment=""):
    return head("/Script/BlueprintGraph.K2Node_CallFunction", name, x, y, comment,
                ["bIsPureFunc=True", f"FunctionReference=(MemberParent={lib},MemberName=\"{member}\")"]) + [
        pin(G(), "self", "object", lib, hidden=True, extra=f'DefaultObject="/Script/Engine.Default__{libname}",')
    ] + pins + ["End Object"]


def varget(name, var, cat, sub, x, y, out_pid, links):
    return head("/Script/BlueprintGraph.K2Node_VariableGet", name, x, y, "",
                [f'VariableReference=(MemberName="{var}",bSelfContext=True)']) + [
        pin(out_pid, var, cat, sub, out=True, links=links),
        pin(G(), "self", "object", MWS, hidden=True, extra=TGT), "End Object"]


def varset(name, var, cat, sub, x, y, comment, ex, ex_links, then, then_links, inp, in_links):
    return head("/Script/BlueprintGraph.K2Node_VariableSet", name, x, y, comment,
                [f'VariableReference=(MemberName="{var}",bSelfContext=True)']) + [
        pin(ex, "execute", "exec", links=ex_links),
        pin(then, "then", "exec", out=True, links=then_links),
        pin(inp, var, cat, sub, links=in_links),
        pin(G(), "Output_Get", cat, sub, out=True,
            extra='PinToolTip="Retrieves the value of the variable, can use instead of a separate Get node",'),
        pin(G(), "self", "object", MWS, hidden=True, extra=TGT), "End Object"]


o = []
# ---- Enable tick ----
o += comment_box("EdGraphNode_Comment_900", -60, -80, 800, 260, "Enable tick")
o += event(N["init"], "OnInitialized", 0, 0, P["init_then"], [(N["on"], P["on_ex"])])
o += head("/Script/BlueprintGraph.K2Node_CallFunction", N["on"], 360, 0, "tick: on",
          ['FunctionReference=(MemberName="SetTickEnabled",bSelfContext=True)']) + [
    pin(P["on_ex"], "execute", "exec", links=[(N["init"], P["init_then"])]),
    pin(G(), "then", "exec", out=True),
    pin(G(), "self", "object", MWS, extra=TGT),
    pin(G(), "bIsEnabled", "bool", extra='DefaultValue="true",'), "End Object"]

# ---- Keep seated-input actor alive ----
o += comment_box("EdGraphNode_Comment_901", -60, 240, 2000, 520, "Keep seated-input actor alive")
o += event(N["tick"], "OnTick", 0, 320, P["tick_then"], [(N["br"], P["br_ex"])],
           [pin(G(), "DeltaTime", "real", subcat="float", out=True)])
o += varget(N["getact"], "SeatedActor", "object", ACT_BPGC, 0, 520, P["getact_out"], [(N["valid"], P["valid_in"])])
o += libfn(N["valid"], KSL, "KismetSystemLibrary", "IsValid", 220, 520, [
    pin(P["valid_in"], "Object", "object", OBJ, links=[(N["getact"], P["getact_out"])]),
    pin(P["valid_ret"], "ReturnValue", "bool", out=True, links=[(N["br"], P["br_c"])])])
o += head("/Script/BlueprintGraph.K2Node_IfThenElse", N["br"], 360, 320, "actor alive?") + [
    pin(P["br_ex"], "execute", "exec", links=[(N["tick"], P["tick_then"])]),
    pin(P["br_c"], "Condition", "bool", links=[(N["valid"], P["valid_ret"])], extra='DefaultValue="true",'),
    pin(G(), "then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "true", "true"),'),
    pin(P["br_f"], "else", "exec", out=True, links=[(N["setn"], P["setn_ex"])],
        extra='PinFriendlyName=NSLOCTEXT("K2Node", "false", "false"),'),
    "End Object"]
o += varget(N["getn"], "SpawnAttempts", "int", "None", 420, 620, P["getn_out"], [(N["add"], P["add_a"])])
o += libfn(N["add"], KML, "KismetMathLibrary", "Add_IntInt", 620, 620, [
    pin(P["add_a"], "A", "int", links=[(N["getn"], P["getn_out"])], extra='DefaultValue="0",'),
    pin(G(), "B", "int", extra='DefaultValue="1",'),
    pin(P["add_ret"], "ReturnValue", "int", out=True, links=[(N["setn"], P["setn_in"])])])
o += varset(N["setn"], "SpawnAttempts", "int", "None", 640, 320, "count spawn",
            P["setn_ex"], [(N["br"], P["br_f"])], P["setn_then"], [(N["spawn"], P["sp_ex"])],
            P["setn_in"], [(N["add"], P["add_ret"])])
o += head("/Script/BlueprintGraph.K2Node_SpawnActorFromClass", N["spawn"], 960, 320, "spawn seated-input actor") + [
    pin(P["sp_ex"], "execute", "exec", links=[(N["setn"], P["setn_then"])]),
    pin(P["sp_then"], "then", "exec", out=True, links=[(N["setact"], P["setact_ex"])]),
    pin(G(), "Class", "class", ACTOR, extra=f'DefaultObject="{ACT_PATH}",'),
    pin(P["sp_ret"], "ReturnValue", "object", ACT_BPGC, out=True, links=[(N["setact"], P["setact_in"])]),
    pin(G(), "WorldContextObject", "object", OBJ, hidden=True),
    pin(P["sp_xf"], "SpawnTransform", "struct", XFORM, links=[(N["mk"], P["mk_ret"])]),
    pin(G(), "CollisionHandlingOverride", "byte",
        "\"/Script/CoreUObject.Enum'/Script/Engine.ESpawnActorCollisionHandlingMethod'\"",
        extra='DefaultValue="AlwaysSpawn",'),
    pin(G(), "TransformScaleMethod", "byte", "\"/Script/CoreUObject.Enum'/Script/Engine.ESpawnActorScaleMethod'\"",
        adv=True, extra='DefaultValue="MultiplyWithRoot",'),
    pin(G(), "Owner", "object", ACTOR, adv=True),
    "End Object"]
o += libfn(N["mk"], KML, "KismetMathLibrary", "MakeTransform", 700, 520, [
    pin(G(), "Location", "struct", VEC, extra='DefaultValue="0.000000,0.000000,0.000000",'),
    pin(G(), "Rotation", "struct", ROT, extra='DefaultValue="0.000000,0.000000,0.000000",'),
    pin(G(), "Scale", "struct", VEC, extra='DefaultValue="1.000000,1.000000,1.000000",'),
    pin(P["mk_ret"], "ReturnValue", "struct", XFORM, out=True, links=[(N["spawn"], P["sp_xf"])])])
o += varset(N["setact"], "SeatedActor", "object", ACT_BPGC, 1500, 320, "remember actor",
            P["setact_ex"], [(N["spawn"], P["sp_then"])], G(), [],
            P["setact_in"], [(N["spawn"], P["sp_ret"])])

write(sys.argv[1], o)
print("ok", len(o), "lines")
