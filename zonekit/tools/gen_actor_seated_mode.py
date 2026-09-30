"""Generates the whole BP_ImmCampActor event graph: our own seated mode (replace the graph with it).

Why: inside the vanilla campfire sit the game counts an interaction in progress, and every native
PDA / backpack / item path refuses to start (builds 1-5, zonekit/README.md). Our mode keeps the
seated pose without the interaction, so those paths run normally.

Flow
  Event Tick -> Cast To PC -> Sequence:
    0 Save look limits once   (camera manager ViewPitch/Yaw Min/Max while standing)
    1 Release vanilla hold    (VanillaHold && !seated flag -> VanillaHold = false)
    2 Take over vanilla sit   (seated flag && !SeatedMode && !VanillaHold && sit montage in "Idle"):
                               TargetSaved = GetInteractionTarget, SeatYaw = actor yaw,
                               ResetInteractionTarget (ends the interaction), PlayAnimMontage(sit, "Idle"),
                               SeatedMode = true
    3 Keep seated             (SeatedMode && !Standing): DisableMovement, look limits around SeatYaw,
                               re-play "Idle" if no montage runs or the sit montage reached "Out"
  IA_LocomotionForward / IA_Jump / IA_Interact (Started) -> Cast To PC -> (SeatedMode && !Standing):
      Standing = true, SeatedMode = false, PlayAnimMontage(sit, "Out"), Delay 3.6 s,
      SetMovementMode(Walking), restore look limits, Standing = false
  G key (not consumed) -> Cast To PC -> (SeatedMode && !Standing):
      SeatedMode = false, VanillaHold = true, SetMovementMode(Walking), restore look limits,
      SetInteractionTarget(TargetSaved)   (vanilla sit resumes; guitar available; items again after
                                           standing up and sitting down)
Variables (added from Python): SeatedMode, Standing, VanillaHold, LimitsSaved (bool); SeatYaw,
DefPitchMin, DefPitchMax, DefYawMin, DefYawMax (real); TargetSaved (InteractionComponent).
Usage: python gen_actor_seated_mode.py <out.txt>
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from bp_t3d import cls, TGT, write
from bp_graph import Graph, Node

PC = cls("/Script/Stalker2.PC")
CHAR = cls("/Script/Engine.Character")
ACTOR = cls("/Script/Engine.Actor")
PAWN = cls("/Script/Engine.Pawn")
OBJ = cls("/Script/CoreUObject.Object")
OBJC = cls("/Script/Stalker2.Obj")
VEC = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Vector'\""
ABA = "\"/Script/CoreUObject.ScriptStruct'/Script/Engine.AlphaBlendArgs'\""
SC_ = cls("/Script/Engine.SceneComponent")
HANDENUM = "\"/Script/CoreUObject.Enum'/Script/Stalker2.EMainHandEquipmentType'\""
GS = cls("/Script/Engine.GameplayStatics")
KML = cls("/Script/Engine.KismetMathLibrary")
KSL = cls("/Script/Engine.KismetSystemLibrary")
MONT = cls("/Script/Engine.AnimMontage")
ANIMI = cls("/Script/Engine.AnimInstance")
SKM = cls("/Script/Engine.SkeletalMeshComponent")
CMC = cls("/Script/Engine.CharacterMovementComponent")
PCM = cls("/Script/Engine.PlayerCameraManager")
SKMESH = cls("/Script/Engine.SkeletalMesh")
ANIMCLS = cls("/Script/Engine.AnimInstance")
SHADOW = "/Game/_STALKER2/SkeletalMeshes/player/sta/sta_03/SK_pla_sta_03_SHA.SK_pla_sta_03_SHA"
LEGS_PP = "/ImmersiveCampfires/Runtime/ABP_ImmCampSeatedLegs.ABP_ImmCampSeatedLegs_C"
ICOMP = cls("/Script/Stalker2.InteractionComponent")
IA_CLS = cls("/Script/EnhancedInput.InputAction")
ROT = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Rotator'\""
V2D = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Vector2D'\""
KEY = "\"/Script/CoreUObject.ScriptStruct'/Script/InputCore.Key'\""
LATENT = "\"/Script/CoreUObject.ScriptStruct'/Script/Engine.LatentActionInfo'\""
MOVEMODE = "\"/Script/CoreUObject.Enum'/Script/Engine.EMovementMode'\""
SELF = "\"/Script/Engine.BlueprintGeneratedClass'/ImmersiveCampfires/Runtime/BP_ImmCampActor.BP_ImmCampActor_C'\""
SIT = "/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/MG_fp_ca_gd_bonfire.MG_fp_ca_gd_bonfire"
IA_DIR = "/Game/_Stalker_2/data/input/InputActions/Delayable/"
BG = "/Script/BlueprintGraph."
GET_TIP = 'PinToolTip="Retrieves the value of the variable, can use instead of a separate Get node",'

# Legs layer: a post-process ABP swapped in after a sit crashed the game every time (builds 7-13,
# also with ImmersiveDialogue's own class). ImmersiveDialogue's single swap ~1 s after load is safe,
# so ours is installed ONCE per world, 3 s after the pawn appears, and never swapped again. It
# chains the previous class (ImmersiveDialogue's) through a Linked Anim Graph tagged "Previous" and
# only blends the seated legs while its Seated variable is set. Without it: sit montage held.
USE_LEGS_LAYER = False          # the old after-sit install (kept for reference, not emitted)
# Build 16: no post-process layer at all. Seated pose = AS_ImmCamp_SitAdditive (the bonfire sit idle made
# additive against fp_bh_idle_stand frame 0, upper-body bones zeroed; made by tools/make_sit_additive.py)
# played as a looping dynamic montage in the FullBody slot, so the game's arm / item animations show.
SIT_ADD = "/ImmersiveCampfires/Runtime/AS_ImmCamp_SitAdditive.AS_ImmCamp_SitAdditive"
# Build 21: both seated poses are yaw tables (tools/make_sit_yaw.py): 31 keys over 1.0 s, key i = view yaw
# -75 + 5 i relative to the seat. The pose montage is paused and its position set from the view yaw every
# tick, so the legs (resting: the whole body) stay put while the view turns the actor.
SIT_REST = "/ImmersiveCampfires/Runtime/AS_ImmCamp_SitRest.AS_ImmCamp_SitRest"
SIT_ADD_BH = "/ImmersiveCampfires/Runtime/AS_ImmCamp_SitAdditiveBH.AS_ImmCamp_SitAdditiveBH"   # build 40: empty-handed stance
IA_GUITAR = "/Game/_Stalker_2/data/input/InputActions/Guitar/IA_GuitarContextualAction.IA_GuitarContextualAction"
ANIMSEQB = cls("/Script/Engine.AnimSequenceBase")
MONTCLS = cls("/Script/Engine.AnimMontage")
LOAD_INSTALL_DELAY = 3.0
LEGS_TAG = "Previous"

# Tunables
PITCH_MIN, PITCH_MAX, YAW_HALF = -60.0, 50.0, 75.0
STAND_DELAY = 4.1          # sit "Out" section is 4.0 s; the layer swap waits until it is done

g = Graph()
seq = [0]


def nm(kind):
    seq[0] += 1
    return f"{kind}_{900 + seq[0]}"


def exec_pins(n):
    n.pin("execute", "exec")
    n.pin("then", "exec", out=True)
    return n


# ---------- node factories ----------
def lib_pure(lib, libname, member, x, y, pins, comment=""):
    n = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
             ["bIsPureFunc=True", f"FunctionReference=(MemberParent={lib},MemberName=\"{member}\")"])
    n.pin("self", "object", sub=lib, hidden=True, extra=f'DefaultObject="/Script/Engine.Default__{libname}",')
    for p in pins:
        n.pin(*p[:2], **p[2]) if len(p) > 2 else n.pin(*p)
    return n


def member_pure(owner_cls, member, x, y, target, pins):
    n = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, "",
             ["bIsPureFunc=True", f"FunctionReference=(MemberParent={owner_cls},MemberName=\"{member}\")"])
    n.pin("self", "object", sub=owner_cls, extra=TGT)
    for p in pins:
        n.pin(*p[:2], **p[2]) if len(p) > 2 else n.pin(*p)
    g.link(target, n["self"])
    return n


def member_call(owner_cls, member, x, y, target, comment, pins=()):
    n = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
                       [f"FunctionReference=(MemberParent={owner_cls},MemberName=\"{member}\")"]))
    n.pin("self", "object", sub=owner_cls, extra=TGT)
    for p in pins:
        n.pin(*p[:2], **p[2]) if len(p) > 2 else n.pin(*p)
    g.link(target, n["self"])
    return n


def self_get(var, cat, x, y, sub="None", subcat=""):
    n = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x, y, "",
             [f'VariableReference=(MemberName="{var}",bSelfContext=True)'])
    n.pin(var, cat, sub=sub, subcat=subcat, out=True)
    n.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    return n[var]


def self_set(var, cat, x, y, comment="", default=None, sub="None", subcat=""):
    n = exec_pins(Node(g, BG + "K2Node_VariableSet", nm("K2Node_VariableSet"), x, y, comment,
                       [f'VariableReference=(MemberName="{var}",bSelfContext=True)']))
    n.pin(var, cat, sub=sub, subcat=subcat, extra=f'DefaultValue="{default}",' if default is not None else "")
    n.pin("Output_Get", cat, sub=sub, subcat=subcat, out=True, extra=GET_TIP)
    n.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    return n


def other_get(owner_cls, var, cat, x, y, target, sub="None", subcat="", friendly=""):
    n = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x, y, "",
             [f'VariableReference=(MemberParent={owner_cls},MemberName="{var}")'])
    n.pin(var, cat, sub=sub, subcat=subcat, out=True, extra=friendly)
    n.pin("self", "object", sub=owner_cls, extra=TGT)
    g.link(target, n["self"])
    return n[var]


def other_set(owner_cls, var, cat, x, y, target, comment="", default=None, subcat=""):
    n = exec_pins(Node(g, BG + "K2Node_VariableSet", nm("K2Node_VariableSet"), x, y, comment,
                       [f'VariableReference=(MemberParent={owner_cls},MemberName="{var}")']))
    n.pin(var, cat, subcat=subcat, extra=f'DefaultValue="{default}",' if default is not None else "")
    n.pin("Output_Get", cat, subcat=subcat, out=True, extra=GET_TIP)
    n.pin("self", "object", sub=owner_cls, extra=TGT)
    g.link(target, n["self"])
    return n


def branch(x, y, comment, cond):
    n = Node(g, BG + "K2Node_IfThenElse", nm("K2Node_IfThenElse"), x, y, comment)
    n.pin("execute", "exec")
    n.pin("Condition", "bool", extra='DefaultValue="true",')
    n.pin("then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "true", "true"),')
    n.pin("else", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "false", "false"),')
    g.link(cond, n["Condition"])
    return n


def b_and(x, y, a, b):
    n = lib_pure(KML, "KismetMathLibrary", "BooleanAND", x, y,
                 [("A", "bool", dict(extra='DefaultValue="false",')), ("B", "bool", dict(extra='DefaultValue="false",')),
                  ("ReturnValue", "bool", dict(out=True))])
    g.link(a, n["A"])
    g.link(b, n["B"])
    return n["ReturnValue"]


def b_or(x, y, a, b):
    n = lib_pure(KML, "KismetMathLibrary", "BooleanOR", x, y,
                 [("A", "bool", dict(extra='DefaultValue="false",')), ("B", "bool", dict(extra='DefaultValue="false",')),
                  ("ReturnValue", "bool", dict(out=True))])
    g.link(a, n["A"])
    g.link(b, n["B"])
    return n["ReturnValue"]


def b_not(x, y, a):
    n = lib_pure(KML, "KismetMathLibrary", "Not_PreBool", x, y,
                 [("A", "bool", dict(extra='DefaultValue="false",')), ("ReturnValue", "bool", dict(out=True))])
    g.link(a, n["A"])
    return n["ReturnValue"]


def name_eq(x, y, a, literal):
    n = lib_pure(KML, "KismetMathLibrary", "EqualEqual_NameName", x, y,
                 [("A", "name", dict(extra='DefaultValue="None",')), ("B", "name", dict(extra=f'DefaultValue="{literal}",')),
                  ("ReturnValue", "bool", dict(out=True))])
    g.link(a, n["A"])
    return n["ReturnValue"]


def dbl_op(x, y, op, a, b_const):
    n = lib_pure(KML, "KismetMathLibrary", op, x, y,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                  ("B", "real", dict(subcat="double", extra=f'DefaultValue="{b_const}",')),
                  ("ReturnValue", "real", dict(subcat="double", out=True))])
    g.link(a, n["A"])
    return n["ReturnValue"]


def player_cast(x, y, label, exec_from):
    gp = lib_pure(GS, "GameplayStatics", "GetPlayerPawn", x - 300, y + 220,
                  [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)),
                   ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                   ("ReturnValue", "object", dict(sub=PAWN, out=True))])
    c = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), x, y, f"player ({label})",
                       [f"TargetType=\"/Script/CoreUObject.Class'/Script/Stalker2.PC'\""]))
    c.pin("CastFailed", "exec", out=True)
    c.pin("Object", "object", sub=OBJ)
    c.pin("AsPC", "object", sub=PC, out=True)
    c.pin("bSuccess", "bool", out=True)
    g.link(gp["ReturnValue"], c["Object"])
    for e in exec_from:
        g.link(e, c["execute"])
    return c


def play_sit(x, y, as_pc, section, comment):
    return member_call(CHAR, "PlayAnimMontage", x, y, as_pc, comment, [
        ("AnimMontage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')),
        ("InPlayRate", "real", dict(subcat="float", extra='DefaultValue="1.000000",')),
        ("StartSectionName", "name", dict(extra=f'DefaultValue="{section}",')),
        ("ReturnValue", "real", dict(subcat="float", out=True))])


def cam_mgr(x, y):
    n = lib_pure(GS, "GameplayStatics", "GetPlayerCameraManager", x, y,
                 [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)),
                  ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                  ("ReturnValue", "object", dict(sub=PCM, out=True))])
    return n["ReturnValue"]


def chain(*nodes):
    for a, b in zip(nodes, nodes[1:]):
        g.link(a["then"], b["execute"])


def restore_limits(x, y, label, prev):
    cm = cam_mgr(x, y + 260)
    sets = []
    for k, (prop, var) in enumerate([("ViewPitchMin", "DefPitchMin"), ("ViewPitchMax", "DefPitchMax"),
                                     ("ViewYawMin", "DefYawMin"), ("ViewYawMax", "DefYawMax")]):
        s = other_set(PCM, prop, "real", x + 280 * k, y, cm, f"restore {prop} ({label})" if k == 0 else "", subcat="float")
        g.link(self_get(var, "real", x + 280 * k - 60, y + 180, subcat="double"), s[prop])
        sets.append(s)
    chain(prev, *sets)
    return sets[-1]


def play_additive(x, y, comment, prev, asset=None, blend_in=0.35):
    n = member_call(ANIMI, "PlaySlotAnimationAsDynamicMontage", x, y, anim, comment, [
        ("Asset", "object", dict(sub=ANIMSEQB, extra=f'DefaultObject="{asset or SIT_ADD}",')),
        ("SlotNodeName", "name", dict(extra='DefaultValue="FullBody",')),
        ("BlendInTime", "real", dict(subcat="float", extra=f'DefaultValue="{blend_in:.6f}",')),
        ("BlendOutTime", "real", dict(subcat="float", extra='DefaultValue="0.250000",')),
        ("InPlayRate", "real", dict(subcat="float", extra='DefaultValue="1.000000",')),
        ("LoopCount", "int", dict(extra='DefaultValue="1000000",')),
        ("BlendOutTriggerTime", "real", dict(subcat="float", extra='DefaultValue="-1.000000",')),
        ("InTimeToStartMontageAt", "real", dict(subcat="float", extra='DefaultValue="0.000000",')),
        ("ReturnValue", "object", dict(sub=MONTCLS, out=True))])
    g.link(prev["then"], n["execute"])
    sv = self_set("PoseMontage", "object", x + 350, y, "", sub=MONTCLS)
    g.link(n["ReturnValue"], sv["PoseMontage"])
    g.link(n["then"], sv["execute"])
    pz = member_call(ANIMI, "Montage_SetPlayRate", x + 650, y, anim, "paused: the view yaw picks the frame", [
        ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="0.000100",'))])
    pz.pins["Montage"].const = True
    g.link(n["ReturnValue"], pz["Montage"])
    g.link(sv["then"], pz["execute"])
    return pz


def make_rot(x, y, pitch_pin=None, yaw_pin=None, pitch="0.0", yaw="0.0"):
    r = lib_pure(KML, "KismetMathLibrary", "MakeRotator", x, y,
                 [("Roll", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                  ("Pitch", "real", dict(subcat="float", extra=f'DefaultValue="{pitch}",')),
                  ("Yaw", "real", dict(subcat="float", extra=f'DefaultValue="{yaw}",')),
                  ("ReturnValue", "struct", dict(sub=ROT, out=True))])
    if pitch_pin is not None:
        g.link(pitch_pin, r["Pitch"])
    if yaw_pin is not None:
        g.link(yaw_pin, r["Yaw"])
    return r["ReturnValue"]


def set_rot(kind, x, y, target, rot_pin, comment):
    """kind: K2_SetWorldRotation / K2_SetRelativeRotation on a scene component."""
    n = member_call(cls("/Script/Engine.SceneComponent"), kind, x, y, target, comment, [
        ("NewRotation", "struct", dict(sub=ROT)), ("bSweep", "bool", dict(extra='DefaultValue="false",')),
        ("SweepHitResult", "struct", dict(sub="\"/Script/CoreUObject.ScriptStruct'/Script/Engine.HitResult'\"", out=True)),
        ("bTeleport", "bool", dict(extra='DefaultValue="true",'))])
    g.link(rot_pin, n["NewRotation"])
    return n


def set_abs_rot(x, y, target, on, comment):
    return member_call(cls("/Script/Engine.SceneComponent"), "SetAbsolute", x, y, target, comment, [
        ("bNewAbsoluteLocation", "bool", dict(extra='DefaultValue="false",')),
        ("bNewAbsoluteRotation", "bool", dict(extra=f'DefaultValue="{on}",')),
        ("bNewAbsoluteScale", "bool", dict(extra='DefaultValue="false",'))])


def cam_of(x, y, pc_pin):
    return member_pure(PC, "GetCameraComponent", x, y, pc_pin, [("ReturnValue", "object", dict(sub=cls("/Script/Engine.CameraComponent"), out=True))])["ReturnValue"]


def body_release(x, y, pc_pin, prev, label):
    """Mesh back under the actor, camera back on its bone (relative rotation saved at the takeover)."""
    mesh_ = other_get(CHAR, "Mesh", "object", x, y + 300, pc_pin, sub=SKM)
    m = set_rot("K2_SetRelativeRotation", x + 200, y, mesh_, make_rot(x + 50, y + 450), f"body follows the actor again ({label})")
    cam_ = cam_of(x + 300, y + 450, pc_pin)
    a = set_abs_rot(x + 500, y, cam_, "false", f"camera back on the head ({label})")
    cr = make_rot(x + 600, y + 450, self_get("CamRelP", "real", x + 450, y + 550, subcat="double"),
                  self_get("CamRelY", "real", x + 450, y + 650, subcat="double"))
    c = set_rot("K2_SetRelativeRotation", x + 800, y, cam_, cr, "")
    shd_ = other_get(PC, "ShadowMeshComponent", "object", x + 900, y + 300, pc_pin, sub=SKM)
    sh = set_rot("K2_SetRelativeRotation", x + 1100, y, shd_,
                 make_rot(x + 950, y + 450, yaw_pin=self_get("ShadowRelY", "real", x + 800, y + 550, subcat="double")), f"shadow follows the actor again ({label})")
    hk = self_set("CamUnhooked", "bool", x + 1400, y, "camera hooked", default="false")
    g.link(prev["then"], m["execute"])
    chain(m, a, c, sh, hk)
    return hk


def blend_args(x, y, seconds, option="HermiteCubic"):
    n = Node(g, BG + "K2Node_MakeStruct", nm("K2Node_MakeStruct"), x, y, "", [f"StructType={ABA}", "bMadeAfterOverridePinRemoval=True"])
    n.pin("BlendTime", "real", subcat="float", extra=f'DefaultValue="{seconds:.6f}",')
    n.pin("BlendOption", "byte", sub="\"/Script/CoreUObject.Enum'/Script/Engine.EAlphaBlendOption'\"", extra=f'DefaultValue="{option}",')
    n.pin("CustomCurve", "object", sub=cls("/Script/Engine.CurveFloat"))
    n.pin("AlphaBlendArgs", "struct", sub=ABA, out=True)
    return n["AlphaBlendArgs"]


def play_rest_eased(x, y, comment, prev, seconds):
    """Resting pose back in with an ease-in-out blend (arms settle into the lap with some weight)."""
    n = member_call(ANIMI, "PlaySlotAnimationAsDynamicMontage_WithBlendArgs", x, y, anim, comment, [
        ("Asset", "object", dict(sub=ANIMSEQB, extra=f'DefaultObject="{SIT_REST}",')),
        ("SlotNodeName", "name", dict(extra='DefaultValue="FullBody",')),
        ("BlendIn", "struct", dict(sub=ABA)),
        ("BlendOut", "struct", dict(sub=ABA)),
        ("InPlayRate", "real", dict(subcat="float", extra='DefaultValue="1.000000",')),
        ("LoopCount", "int", dict(extra='DefaultValue="1000000",')),
        ("BlendOutTriggerTime", "real", dict(subcat="float", extra='DefaultValue="-1.000000",')),
        ("InTimeToStartMontageAt", "real", dict(subcat="float", extra='DefaultValue="0.000000",')),
        ("ReturnValue", "object", dict(sub=MONTCLS, out=True))])
    for pn in ("BlendIn", "BlendOut"):
        n.pins[pn].ref = True
        n.pins[pn].const = True
    g.link(blend_args(x - 250, y + 350, seconds, "ExpOut"), n["BlendIn"])
    g.link(blend_args(x - 250, y + 550, 0.25, "Linear"), n["BlendOut"])
    g.link(prev["then"], n["execute"])
    sv = self_set("PoseMontage", "object", x + 350, y, "", sub=MONTCLS)
    g.link(n["ReturnValue"], sv["PoseMontage"])
    g.link(n["then"], sv["execute"])
    pz = member_call(ANIMI, "Montage_SetPlayRate", x + 650, y, anim, "paused: the view picks the frame", [
        ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="0.000100",'))])
    pz.pins["Montage"].const = True
    g.link(n["ReturnValue"], pz["Montage"])
    g.link(sv["then"], pz["execute"])
    return pz


def set_actor_loc(x, y, target, loc_pin, comment):
    n = member_call(ACTOR, "K2_SetActorLocation", x, y, target, comment, [
        ("NewLocation", "struct", dict(sub=VEC)), ("bSweep", "bool", dict(extra='DefaultValue="false",')),
        ("SweepHitResult", "struct", dict(sub="\"/Script/CoreUObject.ScriptStruct'/Script/Engine.HitResult'\"", out=True)),
        ("bTeleport", "bool", dict(extra='DefaultValue="true",')), ("ReturnValue", "bool", dict(out=True))])
    g.link(loc_pin, n["NewLocation"])
    return n


def ca_restore(x, y, prev_then, label):
    """If the guitar hand-back moved the seat point, put it back. Returns the exec pin to continue from."""
    br = branch(x, y, f"seat point moved? ({label})", self_get("CAMoved", "bool", x - 150, y + 150))
    g.link(prev_then, br["execute"])
    mv = set_actor_loc(x + 300, y, self_get("CAActor", "object", x + 150, y + 250, sub=ACTOR),
                       self_get("CAOrig", "struct", x + 150, y + 350, sub=VEC), f"seat point back ({label})")
    g.link(br["then"], mv["execute"])
    off = self_set("CAMoved", "bool", x + 600, y, "", default="false")
    g.link(mv["then"], off["execute"])
    sq_ = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), x + 850, y, "")
    sq_.pin("execute", "exec")
    sq_.pin("then_0", "exec", out=True)
    g.link(off["then"], sq_["execute"])
    g.link(br["else"], sq_["execute"])
    return sq_["then_0"]


def play_rest(x, y, comment, prev, blend_in=0.35):
    return play_additive(x, y, comment, prev, SIT_REST, blend_in)


def stop_additive(x, y, comment, prev, anim_pin):
    n = member_call(ANIMI, "StopSlotAnimation", x, y, anim_pin, comment, [
        ("InBlendOutTime", "real", dict(subcat="float", extra='DefaultValue="0.250000",')),
        ("SlotNodeName", "name", dict(extra='DefaultValue="FullBody",'))])
    g.link(prev["then"], n["execute"])
    return n


def layer_is_ours(x, y, as_pc_pin):
    m = other_get(CHAR, "Mesh", "object", x - 400, y, as_pc_pin, sub=SKM)
    inst = member_pure(SKM, "GetPostProcessInstance", x - 200, y, m, [("ReturnValue", "object", dict(sub=ANIMI, out=True))])
    oc = lib_pure(GS, "GameplayStatics", "GetObjectClass", x, y,
                  [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "class", dict(sub=OBJ, out=True))])
    g.link(inst["ReturnValue"], oc["Object"])
    eq = lib_pure(KML, "KismetMathLibrary", "EqualEqual_ClassClass", x + 200, y,
                  [("A", "class", dict(sub=OBJ)), ("B", "class", dict(sub=OBJ, extra=f'DefaultObject="{LEGS_PP}",')),
                   ("ReturnValue", "bool", dict(out=True))])
    g.link(oc["ReturnValue"], eq["A"])
    return eq["ReturnValue"]


def delay(x, y, seconds, comment):
    dl = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
              [f"FunctionReference=(MemberParent={KSL},MemberName=\"Delay\")"])
    dl.pin("execute", "exec")
    dl.pin("then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "Completed", "Completed"),')
    dl.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
    dl.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
    dl.pin("Duration", "real", subcat="float", extra=f'DefaultValue="{seconds:.6f}",')
    dl.pin("LatentInfo", "struct", sub=LATENT, hidden=True)
    return dl


def set_yaw_follow(x, y, as_pc, value, comment):
    n = other_set(PAWN, "bUseControllerRotationYaw", "bool", x, y, as_pc, comment, default=value)
    return n


def pp_swap(x, y, label, prev, as_pc, new_class_literal=None, new_class_pin=None):
    """Put a post-process anim class on the player mesh, the only safe Blueprint way
    (ImmersiveDialogue 2.1 BUILD 5.7): save hidden bones, override None, shadow mesh,
    override = class, mesh back, enable, FOV render back on, re-hide bones.
    Returns the last exec node."""
    mesh = other_get(CHAR, "Mesh", "object", x - 200, y + 600, as_pc, sub=SKM)
    # Array_Clear (a Set with an empty array input does not compile: "Array inputs must have an input wired")
    clr = Node(g, BG + "K2Node_CallArrayFunction", nm("K2Node_CallArrayFunction"), x, y, f"hidden bones: clear ({label})",
               ["FunctionReference=(MemberParent=\"/Script/CoreUObject.Class'/Script/Engine.KismetArrayLibrary'\",MemberName=\"Array_Clear\")"])
    exec_pins(clr)
    clr.pin("self", "object", sub=cls("/Script/Engine.KismetArrayLibrary"), hidden=True,
            extra='DefaultObject="/Script/Engine.Default__KismetArrayLibrary",')
    clr.pin("TargetArray", "name")
    clr.pins["TargetArray"].container = "Array"
    arr0 = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x - 100, y + 200, "",
                ['VariableReference=(MemberName="HiddenBones",bSelfContext=True)'])
    arr0.pin("HiddenBones", "name", out=True)
    arr0.pins["HiddenBones"].container = "Array"
    arr0.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    g.link(arr0["HiddenBones"], clr["TargetArray"])
    g.link(prev["then"], clr["execute"])
    # scan bones
    nb = member_pure(SKM, "GetNumBones", x + 100, y + 300, mesh, [("ReturnValue", "int", dict(out=True))])
    last = lib_pure(KML, "KismetMathLibrary", "Subtract_IntInt", x + 300, y + 300,
                    [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="1",')),
                     ("ReturnValue", "int", dict(out=True))])
    g.link(nb["ReturnValue"], last["A"])
    loop = Node(g, BG + "K2Node_MacroInstance", nm("K2Node_MacroInstance"), x + 300, y, f"scan bones ({label})",
                ["MacroGraphReference=(MacroGraph=\"/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop'\","
                 "GraphBlueprint=\"/Script/Engine.Blueprint'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros'\","
                 "GraphGuid=55C904AF4B45FE1761FB55A8DB9FB801)"])
    loop.pin("execute", "exec")
    loop.pin("FirstIndex", "int", extra='DefaultValue="0",')
    loop.pin("LastIndex", "int")
    loop.pin("LoopBody", "exec", out=True)
    loop.pin("Index", "int", out=True)
    loop.pin("Completed", "exec", out=True)
    g.link(clr["then"], loop["execute"])
    g.link(last["ReturnValue"], loop["LastIndex"])
    bn = member_pure(SKM, "GetBoneName", x + 600, y + 300, mesh,
                     [("BoneIndex", "int", dict(extra='DefaultValue="0",')), ("ReturnValue", "name", dict(out=True))])
    g.link(loop["Index"], bn["BoneIndex"])
    # IsBoneHiddenByName is not pure: it needs its own exec pins
    hid = member_call(SKM, "IsBoneHiddenByName", x + 500, y - 200, mesh, "",
                      [("BoneName", "name", dict(extra='DefaultValue="None",')), ("ReturnValue", "bool", dict(out=True))])
    g.link(bn["ReturnValue"], hid["BoneName"])
    g.link(loop["LoopBody"], hid["execute"])
    brh = branch(x + 750, y - 200, f"bone hidden? ({label})", hid["ReturnValue"])
    g.link(hid["then"], brh["execute"])
    add = Node(g, BG + "K2Node_CallArrayFunction", nm("K2Node_CallArrayFunction"), x + 1000, y - 200, "",
               ["FunctionReference=(MemberParent=\"/Script/CoreUObject.Class'/Script/Engine.KismetArrayLibrary'\",MemberName=\"Array_Add\")"])
    exec_pins(add)
    add.pin("self", "object", sub=cls("/Script/Engine.KismetArrayLibrary"), hidden=True,
            extra='DefaultObject="/Script/Engine.Default__KismetArrayLibrary",')
    add.pin("TargetArray", "name")
    add.pins["TargetArray"].container = "Array"
    add.pin("NewItem", "name")
    add.pin("ReturnValue", "int", out=True)
    g.link(brh["then"], add["execute"])
    arr = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x + 800, y - 60, "",
               ['VariableReference=(MemberName="HiddenBones",bSelfContext=True)'])
    arr.pin("HiddenBones", "name", out=True)
    arr.pins["HiddenBones"].container = "Array"
    arr.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    g.link(arr["HiddenBones"], add["TargetArray"])
    g.link(bn["ReturnValue"], add["NewItem"])
    # save mesh
    sm = self_set("SavedMesh", "object", x + 700, y, f"save mesh ({label})", sub=SKMESH)
    g.link(other_get(SKM, "SkeletalMeshAsset", "object", x + 650, y + 450, mesh, sub=SKMESH), sm["SavedMesh"])
    g.link(loop["Completed"], sm["execute"])

    def set_pp(xx, comment, literal=None, pin=None):
        n = member_call(SKM, "SetOverridePostProcessAnimBP", xx, y, mesh, comment,
                        [("InPostProcessAnimBlueprint", "class", dict(sub=ANIMI, extra=f'DefaultObject="{literal}",' if literal else "")),
                         ("ReinitAnimInstances", "bool", dict(extra='DefaultValue="false",'))])
        n.pins["InPostProcessAnimBlueprint"].wrapper = True
        if pin is not None:
            g.link(pin, n["InPostProcessAnimBlueprint"])
        return n

    def set_mesh(xx, comment, literal=None, pin=None):
        n = member_call(SKM, "SetSkeletalMeshAsset", xx, y, mesh, comment,
                        [("NewMesh", "object", dict(sub=SKMESH, extra=f'DefaultObject="{literal}",' if literal else ""))])
        if pin is not None:
            g.link(pin, n["NewMesh"])
        return n

    off = set_pp(x + 1000, f"layer: none ({label})")
    sh = set_mesh(x + 1300, f"swap to shadow ({label})", literal=SHADOW)
    on = set_pp(x + 1600, f"layer: set ({label})", literal=new_class_literal, pin=new_class_pin)
    back = set_mesh(x + 1900, f"swap back ({label})", pin=self_get("SavedMesh", "object", x + 1850, y + 250, sub=SKMESH))
    en = other_set(SKM, "bDisablePostProcessBlueprint", "bool", x + 2200, y, mesh, f"layer enabled ({label})", default="false")
    fov = member_call(PC, "ToggleFOVAndForegroundRender", x + 2500, y, as_pc, f"fov render back ({label})",
                      [("bEnable", "bool", dict(extra='DefaultValue="true",'))])
    chain(sm, off, sh, on, back, en, fov)
    # re-hide bones
    fe = Node(g, BG + "K2Node_MacroInstance", nm("K2Node_MacroInstance"), x + 2800, y, f"rehide bones ({label})",
              ["MacroGraphReference=(MacroGraph=\"/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'\","
               "GraphBlueprint=\"/Script/Engine.Blueprint'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros'\","
               "GraphGuid=99DBFD5540A796041F72A5A9DA655026)"])
    fe.pin("Exec", "exec")
    fe.pin("Array", "name")
    fe.pins["Array"].container = "Array"
    fe.pin("LoopBody", "exec", out=True)
    fe.pin("Array Element", "name", out=True)
    fe.pin("Array Index", "int", out=True)
    fe.pin("Completed", "exec", out=True)
    g.link(fov["then"], fe["Exec"])
    arr2 = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x + 2700, y + 250, "",
                ['VariableReference=(MemberName="HiddenBones",bSelfContext=True)'])
    arr2.pin("HiddenBones", "name", out=True)
    arr2.pins["HiddenBones"].container = "Array"
    arr2.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    g.link(arr2["HiddenBones"], fe["Array"])
    hb = member_call(SKM, "HideBoneByName", x + 3100, y - 200, mesh, "",
                     [("BoneName", "name", dict(extra='DefaultValue="None",')),
                      ("PhysBodyOption", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/Engine.EPhysBodyOp'\"",
                                                      extra='DefaultValue="PBO_None",'))])
    g.link(fe["LoopBody"], hb["execute"])
    g.link(fe["Array Element"], hb["BoneName"])
    tail = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), x + 3100, y, f"layer swapped ({label})")
    tail.pin("execute", "exec")
    tail.pin("then_0", "exec", out=True)
    g.link(fe["Completed"], tail["execute"])
    return {"then": tail["then_0"]}   # chain() continues from here


# =====================================================================
# Tick
# =====================================================================
g.box("EdGraphNode_Comment_900", -80, -140, 900, 520, "Tick: player")
tick = Node(g, BG + "K2Node_Event", nm("K2Node_Event"), 0, 0, "",
            [f"EventReference=(MemberParent={ACTOR},MemberName=\"ReceiveTick\")", "bOverrideFunction=True"])
tick.pin("OutputDelegate", "delegate", out=True)
tick.pins["OutputDelegate"].member_ref = f'MemberParent={ACTOR},MemberName="ReceiveTick"'
tick.pin("then", "exec", out=True)
tick.pin("DeltaSeconds", "real", subcat="float", out=True)
tc = player_cast(300, 0, "tick", [tick["then"]])
as_pc = tc["AsPC"]
sq = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), 600, 0, "tick steps")
sq.pin("execute", "exec")
for k in range(9):
    sq.pin(f"then_{k}", "exec", out=True)
g.link(tc["then"], sq["execute"])

# shared pure values for the tick
seated_flag = other_get(PC, "bInContextualAction", "bool", 700, 300, as_pc,
                        friendly='PinFriendlyName=NSLOCTEXT("UObjectDisplayNames", "PC:bInContextualAction", "In Contextual Action"),')
mesh = other_get(CHAR, "Mesh", "object", 700, 420, as_pc, sub=SKM)
anim = member_pure(SKM, "GetAnimInstance", 900, 420, mesh, [("ReturnValue", "object", dict(sub=ANIMI, out=True))])["ReturnValue"]
move = other_get(CHAR, "CharacterMovement", "object", 700, 540, as_pc, sub=CMC)
# build 34: the post-process layer probe nodes are emitted only with the old layer code (they referenced
# ABP_ImmCampSeatedLegs, deleted for the release)
if USE_LEGS_LAYER:
    pp_inst = member_pure(SKM, "GetPostProcessInstance", 900, 660, mesh, [("ReturnValue", "object", dict(sub=ANIMI, out=True))])["ReturnValue"]
    pp_cls = lib_pure(GS, "GameplayStatics", "GetObjectClass", 1100, 660,
                      [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "class", dict(sub=OBJ, out=True))])
    g.link(pp_inst, pp_cls["Object"])
    inst_eq = lib_pure(KML, "KismetMathLibrary", "EqualEqual_ClassClass", 1300, 660,
                       [("A", "class", dict(sub=OBJ)), ("B", "class", dict(sub=OBJ, extra=f'DefaultObject="{LEGS_PP}",')),
                        ("ReturnValue", "bool", dict(out=True))])
    g.link(pp_cls["ReturnValue"], inst_eq["A"])
    installed = inst_eq["ReturnValue"]

# ---- 0: save look limits once ----
X0, Y0 = 1200, -1400
g.box("EdGraphNode_Comment_901", X0 - 80, Y0 - 120, 1900, 560, "Save look limits once (standing)")
c0 = b_and(X0 - 200, Y0 + 200, b_not(X0 - 400, Y0 + 160, self_get("LimitsSaved", "bool", X0 - 600, Y0 + 160)),
           b_and(X0 - 400, Y0 + 280, b_not(X0 - 600, Y0 + 260, seated_flag),
                 b_not(X0 - 600, Y0 + 340, self_get("SeatedMode", "bool", X0 - 800, Y0 + 340))))
br0 = branch(X0, Y0, "limits not saved yet?", c0)
g.link(sq["then_0"], br0["execute"])
cm0 = cam_mgr(X0 + 200, Y0 + 260)
prev = br0
sets0 = []
for k, (prop, var) in enumerate([("ViewPitchMin", "DefPitchMin"), ("ViewPitchMax", "DefPitchMax"),
                                 ("ViewYawMin", "DefYawMin"), ("ViewYawMax", "DefYawMax")]):
    s = self_set(var, "real", X0 + 300 + 280 * k, Y0, "save standing look limits" if k == 0 else "", subcat="double")
    g.link(other_get(PCM, prop, "real", X0 + 240 + 280 * k, Y0 + 180, cm0, subcat="float"), s[var])
    sets0.append(s)
g.link(br0["then"], sets0[0]["execute"])
chain(*sets0)
done0 = self_set("LimitsSaved", "bool", X0 + 1450, Y0, "limits saved", default="true")
chain(sets0[-1], done0)

# ---- 1: release vanilla hold ----
X1, Y1 = 1200, -700
g.box("EdGraphNode_Comment_902", X1 - 80, Y1 - 120, 900, 400, "Release vanilla hold (stood up from the vanilla sit)")
c1 = b_and(X1 - 200, Y1 + 200, self_get("VanillaHold", "bool", X1 - 400, Y1 + 160),
           b_and(X1 - 300, Y1 + 300, b_not(X1 - 400, Y1 + 260, seated_flag),
                 b_not(X1 - 400, Y1 + 360, self_get("GuitarPending", "bool", X1 - 600, Y1 + 360))))
br1 = branch(X1, Y1, "vanilla sit over?", c1)
g.link(sq["then_1"], br1["execute"])
s1 = self_set("VanillaHold", "bool", X1 + 300, Y1, "vanilla hold: off", default="false")
g.link(br1["then"], s1["execute"])
ca_restore(X1 + 600, Y1, s1["then"], "vanilla sit over")

# ---- key sync: copy the player's own keys into the seated context (once per world) ----
# The game applies Options > Controls rebinds per context from CustomizeControls.cfg; it never writes
# a PlayerContextualAction section, so our IMC_PlayerCA rows keep the default keys. The game-path
# IMC_Exploration object carries the player's keys: map each of its keys for the item / PDA actions
# into the game-path IMC_PlayerCA too (MapKey), then rebuild. Quick-slot tap / hold come from the
# IA assets' own triggers.
XK, YK = 1200, -2800
g.box("EdGraphNode_Comment_909", XK - 900, YK - 300, 5200, 1500, "Key sync: the player's own keys while seated (once)")
IMC_CLS = cls("/Script/EnhancedInput.InputMappingContext")
EAKM = "\"/Script/CoreUObject.ScriptStruct'/Script/EnhancedInput.EnhancedActionKeyMapping'\""
SOP = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.SoftObjectPath'\""
KIL = cls("/Script/Engine.KismetInputLibrary")
EIL = cls("/Script/EnhancedInput.EnhancedInputLibrary")
IMC_DIR = "/Game/_Stalker_2/data/input/InputMappingContexts/"
WANT = [IA_DIR.replace("Delayable/", "") + "IA_OpenPDA.IA_OpenPDA", IA_DIR.replace("Delayable/", "") + "IA_Inventory.IA_Inventory",
        IA_DIR + "IA_QuickSlot1.IA_QuickSlot1", IA_DIR + "IA_QuickSlot2.IA_QuickSlot2",
        IA_DIR + "IA_QuickSlot3.IA_QuickSlot3", IA_DIR + "IA_QuickSlot4.IA_QuickSlot4",
        IA_DIR.replace("Delayable/", "") + "IA_ItemSelector.IA_ItemSelector"]


def load_imc(x, y, name, prev_then, comment):
    mk = lib_pure(KSL, "KismetSystemLibrary", "MakeSoftObjectPath", x, y + 250,
                  [("PathString", "string", dict(extra=f'DefaultValue="{IMC_DIR}{name}.{name}",')),
                   ("ReturnValue", "struct", dict(sub=SOP, out=True))])
    cv = lib_pure(KSL, "KismetSystemLibrary", "Conv_SoftObjPathToSoftObjRef", x + 250, y + 250,
                  [("SoftObjectPath", "struct", dict(sub=SOP)), ("ReturnValue", "softobject", dict(sub=OBJ, out=True))])
    cv.pins["SoftObjectPath"].ref = True
    cv.pins["SoftObjectPath"].const = True
    g.link(mk["ReturnValue"], cv["SoftObjectPath"])
    ld = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x + 150, y, comment,
                        [f"FunctionReference=(MemberParent={KSL},MemberName=\"LoadAsset_Blocking\")"]))
    ld.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
    ld.pin("Asset", "softobject", sub=OBJ)
    ld.pin("ReturnValue", "object", sub=OBJ, out=True)
    g.link(cv["ReturnValue"], ld["Asset"])
    g.link(prev_then, ld["execute"])
    c = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), x + 450, y, f"{name} (game path)",
                       [f"TargetType={IMC_CLS}"]))
    c.pin("CastFailed", "exec", out=True)
    c.pin("Object", "object", sub=OBJ)
    c.pin("AsInputMappingContext", "object", sub=IMC_CLS, out=True)
    c.pin("bSuccess", "bool", out=True)
    g.link(ld["ReturnValue"], c["Object"])
    g.link(ld["then"], c["execute"])
    return c


def key_sync(prev_then):
    brk_ = branch(XK - 700, YK, "keys not synced yet?", b_not(XK - 800, YK + 200, self_get("KeysSynced", "bool", XK - 900, YK + 200)))
    g.link(prev_then, brk_["execute"])
    done = self_set("KeysSynced", "bool", XK - 450, YK, "sync once per world", default="true")
    g.link(brk_["then"], done["execute"])
    exp = load_imc(XK - 250, YK, "IMC_Exploration", done["then"], "player's keys")
    ca = load_imc(XK + 350, YK, "IMC_PlayerCA", exp["then"], "seated context")
    mp = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), XK + 900, YK + 250, "",
              [f'VariableReference=(MemberParent={IMC_CLS},MemberName="Mappings")'])
    mp.pin("Mappings", "struct", sub=EAKM, out=True)
    mp.pins["Mappings"].container = "Array"
    mp.pin("self", "object", sub=IMC_CLS, extra=TGT)
    g.link(exp["AsInputMappingContext"], mp["self"])
    fe = Node(g, BG + "K2Node_MacroInstance", nm("K2Node_MacroInstance"), XK + 1100, YK, "each exploration row",
              ["MacroGraphReference=(MacroGraph=\"/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'\","
               "GraphBlueprint=\"/Script/Engine.Blueprint'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros'\","
               "GraphGuid=99DBFD5540A796041F72A5A9DA655026)"])
    fe.pin("Exec", "exec")
    fe.pin("Array", "struct", sub=EAKM)
    fe.pins["Array"].container = "Array"
    fe.pin("LoopBody", "exec", out=True)
    fe.pin("Array Element", "struct", sub=EAKM, out=True)
    fe.pin("Array Index", "int", out=True)
    fe.pin("Completed", "exec", out=True)
    prev = ca
    for k, ia in enumerate(WANT):
        un = member_call(IMC_CLS, "UnmapAllKeysFromAction", XK + 900 + 200 * k, YK - 250, ca["AsInputMappingContext"],
                         "drop default keys" if k == 0 else "", [("Action", "object", dict(sub=cls("/Script/EnhancedInput.InputAction"),
                                                                                            extra=f'DefaultObject="{ia}",'))])
        un.pins["Action"].const = True
        g.link(prev["then"], un["execute"])
        prev = un
    g.link(prev["then"], fe["Exec"])
    g.link(mp["Mappings"], fe["Array"])
    bs = Node(g, BG + "K2Node_BreakStruct", nm("K2Node_BreakStruct"), XK + 1400, YK + 250, "",
              [f"StructType={EAKM}", "bMadeAfterOverridePinRemoval=True"])
    bs.pin("EnhancedActionKeyMapping", "struct", sub=EAKM)
    bs.pin("Action", "object", sub=cls("/Script/EnhancedInput.InputAction"), out=True)
    bs.pin("Key", "struct", sub=KEY, out=True)
    g.link(fe["Array Element"], bs["EnhancedActionKeyMapping"])
    # wanted action?
    cond = None
    for k, ia in enumerate(WANT):
        eq = lib_pure(KML, "KismetMathLibrary", "EqualEqual_ObjectObject", XK + 1700, YK + 250 + 80 * k,
                      [("A", "object", dict(sub=OBJ)), ("B", "object", dict(sub=OBJ, extra=f'DefaultObject="{ia}",')),
                       ("ReturnValue", "bool", dict(out=True))])
        g.link(bs["Action"], eq["A"])
        cond = eq["ReturnValue"] if cond is None else b_or(XK + 1950, YK + 250 + 80 * k, cond, eq["ReturnValue"])
    kv = lib_pure(KIL, "KismetInputLibrary", "Key_IsValid", XK + 1900, YK + 850,
                  [("Key", "struct", dict(sub=KEY)), ("ReturnValue", "bool", dict(out=True))])
    kv.pins["Key"].ref = True
    kv.pins["Key"].const = True
    g.link(bs["Key"], kv["Key"])
    brw = branch(XK + 2300, YK - 150, "item / PDA key?", b_and(XK + 2200, YK + 700, cond, kv["ReturnValue"]))
    g.link(fe["LoopBody"], brw["execute"])
    mk = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), XK + 2600, YK - 150, "add the player's key",
                        [f"FunctionReference=(MemberParent={IMC_CLS},MemberName=\"MapKey\")"]))
    mk.pin("self", "object", sub=IMC_CLS, extra=TGT)
    mk.pin("Action", "object", sub=cls("/Script/EnhancedInput.InputAction"))
    mk.pin("ToKey", "struct", sub=KEY)
    mk.pin("ReturnValue", "struct", sub=EAKM, out=True)
    mk.pins["ReturnValue"].ref = True
    g.link(ca["AsInputMappingContext"], mk["self"])
    g.link(bs["Action"], mk["Action"])
    g.link(bs["Key"], mk["ToKey"])
    g.link(brw["then"], mk["execute"])
    rb = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), XK + 2600, YK + 150, "apply",
                        [f"FunctionReference=(MemberParent={EIL},MemberName=\"RequestRebuildControlMappingsUsingContext\")"]))
    rb.pin("self", "object", sub=EIL, hidden=True, extra='DefaultObject="/Script/EnhancedInput.Default__EnhancedInputLibrary",')
    rb.pin("Context", "object", sub=IMC_CLS)
    rb.pins["Context"].const = True
    rb.pin("bForceImmediately", "bool", extra='DefaultValue="true",')
    g.link(ca["AsInputMappingContext"], rb["Context"])
    g.link(fe["Completed"], rb["execute"])
    return brk_


# ---- 2: take over the vanilla sit once settled ----
X2, Y2 = 1200, 0
g.box("EdGraphNode_Comment_903", X2 - 80, Y2 - 320, 7600, 1100, "Take over the vanilla sit once settled")
section = member_pure(ANIMI, "Montage_GetCurrentSection", X2 - 700, Y2 + 440, anim,
                      [("Montage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')),
                       ("ReturnValue", "name", dict(out=True))])["ReturnValue"]
c2 = b_and(X2 - 200, Y2 + 240,
           b_and(X2 - 400, Y2 + 200, seated_flag, b_not(X2 - 600, Y2 + 240, self_get("SeatedMode", "bool", X2 - 800, Y2 + 240))),
           b_and(X2 - 400, Y2 + 360, b_not(X2 - 600, Y2 + 340, self_get("VanillaHold", "bool", X2 - 800, Y2 + 340)),
                 name_eq(X2 - 500, Y2 + 440, section, "Idle")))
loc2 = member_pure(ACTOR, "K2_GetActorLocation", X2 - 900, Y2 + 600, as_pc, [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"]
mv2 = lib_pure(KML, "KismetMathLibrary", "Subtract_VectorVector", X2 - 700, Y2 + 600,
               [("A", "struct", dict(sub=VEC)), ("B", "struct", dict(sub=VEC)), ("ReturnValue", "struct", dict(sub=VEC, out=True))])
g.link(loc2, mv2["A"])
g.link(self_get("LastLoc", "struct", X2 - 900, Y2 + 700, sub=VEC), mv2["B"])
mvl = lib_pure(KML, "KismetMathLibrary", "VSize", X2 - 500, Y2 + 600, [("A", "struct", dict(sub=VEC)), ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(mv2["ReturnValue"], mvl["A"])
still = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X2 - 300, Y2 + 600,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.05",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(mvl["ReturnValue"], still["A"])
c2 = b_and(X2 - 100, Y2 + 500, c2, still["ReturnValue"])
br2 = branch(X2, Y2, "vanilla sit settled and still?", c2)
g.link(sq["then_2"], br2["execute"])
save_t = self_set("TargetSaved", "object", X2 + 300, Y2, "remember seat", sub=ICOMP)
g.link(member_pure(PC, "GetInteractionTarget", X2 + 240, Y2 + 200, as_pc,
                   [("ReturnValue", "object", dict(sub=ICOMP, out=True))])["ReturnValue"], save_t["TargetSaved"])
save_y = self_set("SeatYaw", "real", X2 + 600, Y2, "remember seat facing", subcat="double")
rot = member_pure(ACTOR, "K2_GetActorRotation", X2 + 400, Y2 + 360, as_pc, [("ReturnValue", "struct", dict(sub=ROT, out=True))])
brk = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X2 + 560, Y2 + 360,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(rot["ReturnValue"], brk["InRot"])
g.link(brk["Yaw"], save_y["SeatYaw"])
rst = member_call(PC, "ResetInteractionTarget", X2 + 900, Y2, as_pc, "end vanilla interaction")
inp = member_call(PC, "EnableInputAfterInteraction", X2 + 1200, Y2, as_pc, "normal controls back")
yaw_off = set_yaw_follow(X2 + 1500, Y2, as_pc, "true", "view turns the body (camera hangs off the body)")
rest = member_call(OBJC, "ChangeMainHandWeapon", X2 + 1050, Y2 - 200, as_pc, "put the weapon away (bare hands)",
                   [("MainHandEquipment", "byte", dict(sub=HANDENUM, extra='DefaultValue="None",')),
                    ("HideWeaponTimeLimit", "real", dict(subcat="float", extra='DefaultValue="0.000000",')),
                    ("bShouldSkipAnimation", "bool", dict(extra='DefaultValue="true",'))])
hide = member_call(PC, "DisableInteractions", X2 + 1350, Y2 - 200, as_pc, "no interaction prompts while seated")
fovr = member_call(PC, "ToggleFOVAndForegroundRender", X2 + 1650, Y2 - 200, as_pc, "first-person view and hand render back",
                   [("bEnable", "bool", dict(extra='DefaultValue="true",'))])
tsq = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X2 + 150, Y2 - 300, "keys, then take over")
tsq.pin("execute", "exec")
tsq.pin("then_0", "exec", out=True)
tsq.pin("then_1", "exec", out=True)
g.link(br2["then"], tsq["execute"])
key_sync(tsq["then_0"])
g.link(ca_restore(X2 + 150, Y2 - 1400, tsq["then_1"], "takeover"), save_t["execute"])
rwt = member_call(OBJC, "RemoveWeaponFromHands", X2 + 1050, Y2 - 200, as_pc, "weapon out of the hands")
svs = member_call(PC, "SaveStatesBeforeInteraction", X2 + 1350, Y2 - 400, as_pc, "store the weapon like the vanilla sit")
cam2 = cam_of(X2 + 1300, Y2 - 650, as_pc)
crr = other_get(SC_, "RelativeRotation", "struct", X2 + 1450, Y2 - 650, cam2, sub=ROT)
crb = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X2 + 1650, Y2 - 650,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(crr, crb["InRot"])
scp = self_set("CamRelP", "real", X2 + 1800, Y2 - 450, "camera's own rotation (pitch)", subcat="double")
g.link(crb["Pitch"], scp["CamRelP"])
scy = self_set("CamRelY", "real", X2 + 2050, Y2 - 450, "camera's own rotation (yaw)", subcat="double")
g.link(crb["Yaw"], scy["CamRelY"])
shd2 = other_get(PC, "ShadowMeshComponent", "object", X2 + 2200, Y2 - 850, as_pc, sub=SKM)
srr = other_get(SC_, "RelativeRotation", "struct", X2 + 2350, Y2 - 850, shd2, sub=ROT)
srb = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X2 + 2500, Y2 - 850,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(srr, srb["InRot"])
ssy = self_set("ShadowRelY", "real", X2 + 2300, Y2 - 450, "shadow's own yaw", subcat="double")
g.link(srb["Yaw"], ssy["ShadowRelY"])
cam2b = cam_of(X2 + 2600, Y2 - 1100, as_pc)
cwr = member_pure(SC_, "K2_GetComponentRotation", X2 + 2750, Y2 - 1100, cam2b, [("ReturnValue", "struct", dict(sub=ROT, out=True))])
cwb = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X2 + 2950, Y2 - 1100,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(cwr["ReturnValue"], cwb["InRot"])
stp_ = self_set("TakeP", "real", X2 + 2600, Y2 - 800, "view at the sit end (pitch)", subcat="double")
g.link(cwb["Pitch"], stp_["TakeP"])
sty_ = self_set("TakeY", "real", X2 + 2850, Y2 - 800, "view at the sit end (yaw)", subcat="double")
g.link(cwb["Yaw"], sty_["TakeY"])
gpc3 = lib_pure(GS, "GameplayStatics", "GetPlayerController", X2 + 3000, Y2 - 650,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                 ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
scr2 = member_call(cls("/Script/Engine.Controller"), "SetControlRotation", X2 + 3100, Y2 - 800, gpc3, "look where the camera already looks",
                   [("NewRotation", "struct", dict(sub=ROT))])
scr2.pins["NewRotation"].ref = True
scr2.pins["NewRotation"].const = True
g.link(make_rot(X2 + 3000, Y2 - 950, pitch_pin=self_get("TakeP", "real", X2 + 2850, Y2 - 1000, subcat="double"), yaw_pin=self_get("TakeY", "real", X2 + 2850, Y2 - 900, subcat="double")), scr2["NewRotation"])
vh0 = self_set("ViewHold", "int", X2 + 3350, Y2 - 800, "hold that view for a few frames", default="4")
sloc = self_set("SeatLoc", "struct", X2 + 3600, Y2 - 800, "where the vanilla sit put us", sub=VEC)
g.link(member_pure(ACTOR, "K2_GetActorLocation", X2 + 3450, Y2 - 600, as_pc, [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"], sloc["SeatLoc"])
sby0 = self_set("BodyYaw", "real", X2 + 2500, Y2 - 450, "body facing = the seat", subcat="double")
g.link(brk["Yaw"], sby0["BodyYaw"])
keep_loc = set_actor_loc(X2 + 3850, Y2 - 800, as_pc, self_get("SeatLoc", "struct", X2 + 3700, Y2 - 600, sub=VEC), "stay on the seat spot")
chain(save_t, save_y, stp_, sty_, sloc, rst, hide, fovr, inp, keep_loc, rwt, scp, scy, ssy, sby0, scr2, vh0, yaw_off)

self_n = Node(g, BG + "K2Node_Self", nm("K2Node_Self"), X2 + 2000, Y2 + 300, "")
self_n.pin("self", "object", subcat="self", out=True)
prereq = member_call(cls("/Script/Engine.ActorComponent"), "AddTickPrerequisiteActor", X2 + 2100, Y2, mesh,
                     "our tick before the body", [("PrerequisiteActor", "object", dict(sub=ACTOR))])
g.link(self_n["self"], prereq["PrerequisiteActor"])
on2 = self_set("SeatedMode", "bool", X2 + 2400, Y2, "seated mode: on", default="true")
flag_off = other_set(PC, "bInContextualAction", "bool", X2 + 1650, Y2 + 220, as_pc, "leave the vanilla sit state", default="false")
pa = play_rest(X2 + 1950, Y2, "resting seated pose", flag_off)
pa0 = self_set("PoseAdditive", "bool", X2 + 2150, Y2 + 200, "pose: resting", default="false")
chain(yaw_off, flag_off)
chain(pa, pa0, prereq, on2)
# The legs layer goes on only once the vanilla interaction is fully over (a mesh swap during the
# sit crashed the game: builds 7-10, PC.IsVaulting reading 0xa00).
if USE_LEGS_LAYER:
    dly = delay(X2 + 2700, Y2, 1.5, "let the vanilla sit finish")
    g.link(on2["then"], dly["execute"])
    goc = lib_pure(GS, "GameplayStatics", "GetObjectClass", X2 + 2900, Y2 + 300,
                   [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "class", dict(sub=OBJ, out=True))])
    g.link(pp_inst, goc["Object"])
    ccast = Node(g, BG + "K2Node_ClassDynamicCast", nm("K2Node_ClassDynamicCast"), X2 + 3000, Y2, "previous layer class",
                 [f"TargetType={ANIMCLS}"])
    exec_pins(ccast)
    ccast.pin("CastFailed", "exec", out=True)
    ccast.pin("Class", "class", sub=OBJ)
    ccast.pin("AsAnimInstanceClass", "class", sub=ANIMCLS, out=True)
    ccast.pin("bSuccess", "bool", out=True)
    g.link(goc["ReturnValue"], ccast["Class"])
    still = branch(X2 + 2850, Y2, "still seated, sit state gone?",
                   b_and(X2 + 2700, Y2 + 200,
                         b_and(X2 + 2600, Y2 + 160, self_get("SeatedMode", "bool", X2 + 2400, Y2 + 160), b_not(X2 + 2400, Y2 + 240, installed)),
                         b_not(X2 + 2500, Y2 + 320, seated_flag)))
    g.link(dly["then"], still["execute"])
    g.link(still["then"], ccast["execute"])
    spc = self_set("SavedPPClass", "class", X2 + 3300, Y2, "save previous layer", sub=ANIMCLS)
    g.link(ccast["AsAnimInstanceClass"], spc["SavedPPClass"])
    g.link(ccast["then"], spc["execute"])
    spc_none = self_set("SavedPPClass", "class", X2 + 3300, Y2 + 180, "no previous layer", sub=ANIMCLS)
    g.link(ccast["CastFailed"], spc_none["execute"])
    merge = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X2 + 3600, Y2, "install legs layer")
    merge.pin("execute", "exec")
    merge.pin("then_0", "exec", out=True)
    g.link(spc["then"], merge["execute"])
    g.link(spc_none["then"], merge["execute"])
    lay_in = pp_swap(X2 + 3900, Y2, "install", {"then": merge["then_0"]}, as_pc, new_class_literal=LEGS_PP)
    stopv = member_call(CHAR, "StopAnimMontage", X2 + 7200, Y2, as_pc, "sit montage off (legs layer holds the pose)",
                        [("AnimMontage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",'))])
    chain(lay_in, stopv)


# ---- 3: keep seated ----
X3, Y3 = 1200, 900
g.box("EdGraphNode_Comment_904", X3 - 80, Y3 - 320, 3400, 1300, "Keep seated: no walking, look limits, pose")
c3 = b_and(X3 - 200, Y3 + 200, self_get("SeatedMode", "bool", X3 - 400, Y3 + 160),
           b_not(X3 - 400, Y3 + 260, self_get("Standing", "bool", X3 - 600, Y3 + 260)))
br3 = branch(X3, Y3, "in seated mode?", c3)
g.link(sq["then_3"], br3["execute"])
dis = member_call(CMC, "DisableMovement", X3 + 300, Y3, move, "no walking")
cm3 = cam_mgr(X3 + 560, Y3 + 300)
lim = []
seat_yaw = self_get("SeatYaw", "real", X3 + 700, Y3 + 420, subcat="double")
for k, (prop, val) in enumerate([("ViewPitchMin", PITCH_MIN), ("ViewPitchMax", PITCH_MAX), ("ViewYawMin", None), ("ViewYawMax", None)]):
    s = other_set(PCM, prop, "real", X3 + 600 + 280 * k, Y3, cm3, "seated look limits" if k == 0 else "",
                  default=f"{val:.6f}" if val is not None else None, subcat="float")
    if prop == "ViewYawMin":
        g.link(dbl_op(X3 + 900 + 280 * k - 200, Y3 + 420, "Subtract_DoubleDouble", seat_yaw, YAW_HALF), s[prop])
    if prop == "ViewYawMax":
        g.link(dbl_op(X3 + 900 + 280 * k - 200, Y3 + 520, "Add_DoubleDouble", seat_yaw, YAW_HALF), s[prop])
    lim.append(s)
flag3 = other_set(PC, "bInContextualAction", "bool", X3 + 150, Y3 + 250, as_pc, "sit state off (on during a direct guitar try)", default="false")
g.link(self_get("GuitarDirect", "bool", X3 + 50, Y3 + 400), flag3["bInContextualAction"])
g.link(br3["then"], flag3["execute"])
g.link(flag3["then"], dis["execute"])
chain(dis, *lim)
# arms busy? PDA, backpack, or an action montage (food, drink, medkit, artifact: all in MainActionSlot)
q_pda = member_pure(PC, "IsUsingPDA", X3 + 1600, Y3 + 300, as_pc, [("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
q_bag = member_pure(PC, "IsUsingBackpack", X3 + 1600, Y3 + 380, as_pc, [("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
q_act = member_pure(ANIMI, "IsSlotActive", X3 + 1600, Y3 + 460, anim,
                    [("SlotNodeName", "name", dict(extra='DefaultValue="MainActionSlot",')), ("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
q_def = member_pure(ANIMI, "IsSlotActive", X3 + 1600, Y3 + 540, anim,
                    [("SlotNodeName", "name", dict(extra='DefaultValue="DefaultSlot",')), ("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
q_up = member_pure(ANIMI, "IsSlotActive", X3 + 1600, Y3 + 620, anim,
                   [("SlotNodeName", "name", dict(extra='DefaultValue="UpperBody",')), ("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
hand3 = member_pure(OBJC, "GetMainHandEquipType", X3 + 1400, Y3 + 700, as_pc,
                    [("ReturnValue", "byte", dict(sub=HANDENUM, out=True))])["ReturnValue"]
h0 = lib_pure(KML, "KismetMathLibrary", "EqualEqual_ByteByte", X3 + 1600, Y3 + 700,
              [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')),
               ("ReturnValue", "bool", dict(out=True))])
g.link(hand3, h0["A"])
busy = b_or(X3 + 2000, Y3 + 400, b_or(X3 + 1850, Y3 + 340, q_pda, q_bag),
            b_and(X3 + 1900, Y3 + 700, h0["ReturnValue"],
            b_or(X3 + 1850, Y3 + 500, q_act, b_or(X3 + 1750, Y3 + 580, q_def, q_up))))
itm = self_get("ItemMontage", "object", X3 + 900, Y3 + 1300, sub=MONTCLS)
iplay = member_pure(ANIMI, "Montage_IsPlaying", X3 + 1100, Y3 + 1300, anim, [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "bool", dict(out=True))])
iplay.pins["Montage"].const = True
g.link(itm, iplay["Montage"])
isec = member_pure(ANIMI, "Montage_GetCurrentSection", X3 + 1100, Y3 + 1400, anim,
                   [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "name", dict(out=True))])
isec.pins["Montage"].const = True
g.link(itm, isec["Montage"])
ipos = member_pure(ANIMI, "Montage_GetPosition", X3 + 1100, Y3 + 1500, anim,
                   [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "real", dict(subcat="float", out=True))])
ipos.pins["Montage"].const = True
g.link(itm, ipos["Montage"])
ilen = member_pure(ANIMSEQB, "GetPlayLength", X3 + 1100, Y3 + 1600, itm, [("ReturnValue", "real", dict(subcat="float", out=True))])
irem = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X3 + 1300, Y3 + 1550,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(ilen["ReturnValue"], irem["A"])
g.link(ipos["ReturnValue"], irem["B"])
ilast = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X3 + 1500, Y3 + 1550,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.5",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(irem["ReturnValue"], ilast["A"])
# build 45: Montage_IsPlaying(None) means "any montage playing" and a None length is 0: with no item captured yet
# the test read "ending" and blocked every item. Require a captured montage that is not our own pose.
ival = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X3 + 900, Y3 + 1700,
                [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(itm, ival["Object"])
inot = lib_pure(KML, "KismetMathLibrary", "NotEqual_ObjectObject", X3 + 900, Y3 + 1800,
                [("A", "object", dict(sub=OBJ)), ("B", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(itm, inot["A"])
g.link(self_get("PoseMontage", "object", X3 + 700, Y3 + 1850, sub=MONTCLS), inot["B"])
iok = b_and(X3 + 1100, Y3 + 1750, ival["ReturnValue"], inot["ReturnValue"])
ending = b_and(X3 + 1700, Y3 + 1400, b_and(X3 + 1500, Y3 + 1700, iok, iplay["ReturnValue"]), b_or(X3 + 1600, Y3 + 1450, name_eq(X3 + 1400, Y3 + 1400, isec["ReturnValue"], "Out"), ilast["ReturnValue"]))
busy = b_and(X3 + 1850, Y3 + 1200, busy, b_not(X3 + 1800, Y3 + 1300, ending))
brb = branch(X3 + 1800, Y3, "arms busy? (item not in its last 0.5 s)", busy)
hsq = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X3 + 1500, Y3 - 400, "weapon re-equipped?")
hsq.pin("execute", "exec")
hsq.pin("then_0", "exec", out=True)
hsq.pin("then_1", "exec", out=True)
g.link(lim[-1]["then"], hsq["execute"])
hne3 = lib_pure(KML, "KismetMathLibrary", "NotEqual_ByteByte", X3 + 1500, Y3 - 150,
                [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(hand3, hne3["A"])
g.link(self_get("SavedHand", "byte", X3 + 1300, Y3 - 100, sub=HANDENUM), hne3["B"])
nz3 = lib_pure(KML, "KismetMathLibrary", "NotEqual_ByteByte", X3 + 1500, Y3 - 50,
               [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "bool", dict(out=True))])
g.link(hand3, nz3["A"])
brwe = branch(X3 + 1700, Y3 - 400, "weapon just came out?", b_and(X3 + 1650, Y3 - 100, hne3["ReturnValue"], nz3["ReturnValue"]))
g.link(hsq["then_0"], brwe["execute"])
rwe = member_call(OBJC, "RemoveWeaponFromHands", X3 + 2000, Y3 - 400, as_pc, "hide it at once")
g.link(brwe["then"], rwe["execute"])
# build 43: also cut the re-equip animation itself (MG_fp_udp_equip etc., MainActionSlot): it keys a different
# hip / leg pose than the item stance and threw the seated legs 20 cm and the hips up 4-9 cm (trace, build 42)
seq_eq = member_call(ANIMI, "StopSlotAnimation", X3 + 2300, Y3 - 400, anim, "no re-equip animation while seated", [
    ("InBlendOutTime", "real", dict(subcat="float", extra='DefaultValue="0.300000",')),
    ("SlotNodeName", "name", dict(extra='DefaultValue="MainActionSlot",'))])
g.link(rwe["then"], seq_eq["execute"])
shd = self_set("SavedHand", "byte", X3 + 1700, Y3 - 250, "remember the hand", sub=HANDENUM)
g.link(hand3, shd["SavedHand"])
g.link(hsq["then_1"], shd["execute"])
g.link(shd["then"], brb["execute"])
now3 = lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X3 + 2000, Y3 + 650,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])
# busy: remember when, switch to the free-arms (additive) pose once
lat = self_set("LastActionTime", "real", X3 + 2100, Y3 - 200, "arms busy now", subcat="double")
g.link(now3["ReturnValue"], lat["LastActionTime"])
g.link(brb["then"], lat["execute"])
brf = branch(X3 + 2400, Y3 - 200, "resting pose on?", b_not(X3 + 2300, Y3 - 50, self_get("PoseAdditive", "bool", X3 + 2200, Y3 - 50)))
g.link(lat["then"], brf["execute"])
cur_m = member_pure(ANIMI, "GetCurrentActiveMontage", X3 + 2450, Y3 - 450, anim, [("ReturnValue", "object", dict(sub=MONTCLS, out=True))])["ReturnValue"]
sim = self_set("ItemMontage", "object", X3 + 2550, Y3 - 350, "the item animation", sub=MONTCLS)
g.link(cur_m, sim["ItemMontage"])
g.link(brf["then"], sim["execute"])
paf = play_additive(X3 + 2700, Y3 - 200, "free arms (additive legs)", sim, None, 0.1)
pa1 = self_set("PoseAdditive", "bool", X3 + 3000, Y3 - 200, "pose: free arms", default="true")
g.link(paf["then"], pa1["execute"])
par1 = self_set("PoseAR", "bool", X3 + 3250, Y3 - 200, "free arms on the item stance", default="true")
g.link(pa1["then"], par1["execute"])
# idle: back to resting 0.4 s after the last busy tick; also heal a lost resting pose
since3 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X3 + 2200, Y3 + 650,
                  [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                   ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now3["ReturnValue"], since3["A"])
g.link(self_get("LastActionTime", "real", X3 + 2000, Y3 + 750, subcat="double"), since3["B"])
calm = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X3 + 2400, Y3 + 650,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.1",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(since3["ReturnValue"], calm["A"])
sitplay = member_pure(ANIMI, "Montage_IsPlaying", X3 + 2400, Y3 + 800, anim,
                      [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "bool", dict(out=True))])
sitplay.pins["Montage"].const = True
g.link(self_get("PoseMontage", "object", X3 + 2200, Y3 + 850, sub=MONTCLS), sitplay["Montage"])
back_rest = b_or(X3 + 2800, Y3 + 500,
                 b_and(X3 + 2600, Y3 + 450, self_get("PoseAdditive", "bool", X3 + 2400, Y3 + 450), calm["ReturnValue"]),
                 b_and(X3 + 2600, Y3 + 600, b_not(X3 + 2400, Y3 + 550, self_get("PoseAdditive", "bool", X3 + 2200, Y3 + 550)),
                       b_not(X3 + 2600, Y3 + 800, sitplay["ReturnValue"])))
brr = branch(X3 + 2400, Y3 + 200, "back to resting?", back_rest)
isq = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X3 + 2100, Y3 + 200, "idle: weapon away, then pose")
isq.pin("execute", "exec")
isq.pin("then_0", "exec", out=True)
isq.pin("then_1", "exec", out=True)
g.link(brb["else"], isq["execute"])
hand = member_pure(OBJC, "GetMainHandEquipType", X3 + 2100, Y3 + 1000, as_pc,
                   [("ReturnValue", "byte", dict(sub=HANDENUM, out=True))])["ReturnValue"]
hne = lib_pure(KML, "KismetMathLibrary", "NotEqual_ByteByte", X3 + 2400, Y3 + 1000,
               [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "bool", dict(out=True))])
g.link(hand, hne["A"])
since_w = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X3 + 2400, Y3 + 1150,
                   [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                    ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now3["ReturnValue"], since_w["A"])
g.link(self_get("LastPutAway", "real", X3 + 2200, Y3 + 1250, subcat="double"), since_w["B"])
cool = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X3 + 2600, Y3 + 1150,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.5",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(since_w["ReturnValue"], cool["A"])
brw = branch(X3 + 2400, Y3 + 950, "weapon out?", b_and(X3 + 2300, Y3 + 1100, hne["ReturnValue"], cool["ReturnValue"]))
# build 23: not linked (RemoveWeaponFromHands never changed the hand; every 1.5 s it may jitter the pose)
away = member_call(OBJC, "RemoveWeaponFromHands", X3 + 2700, Y3 + 950, as_pc, "put it away (again)")
g.link(brw["then"], away["execute"])
lpa = self_set("LastPutAway", "real", X3 + 3000, Y3 + 950, "tried just now", subcat="double")
g.link(now3["ReturnValue"], lpa["LastPutAway"])
g.link(away["then"], lpa["execute"])
g.link(isq["then_1"], brr["execute"])
brh = branch(X3 + 2550, Y3 + 200, "coming from free arms?", self_get("PoseAdditive", "bool", X3 + 2450, Y3 + 350))
g.link(brr["then"], brh["execute"])
pr = play_rest_eased(X3 + 2700, Y3 + 200, "resting seated pose (arms settle, 1.5 s)", {"then": brh["then"]}, 1.5)
prh = play_rest(X3 + 2700, Y3 + 450, "resting pose lost: back at once", {"then": brh["else"]}, 0.01)
g.link(prh["then"], self_set("PoseAdditive", "bool", X3 + 3350, Y3 + 450, "pose: resting (heal)", default="false")["execute"])
pa2 = self_set("PoseAdditive", "bool", X3 + 3000, Y3 + 200, "pose: resting", default="false")
rwr = member_call(OBJC, "RemoveWeaponFromHands", X3 + 2850, Y3 + 400, as_pc, "weapon out of the hands again")
g.link(pr["then"], rwr["execute"])
g.link(rwr["then"], pa2["execute"])

# ---- 4: pose frame from the view yaw ----
X4, Y4 = 1200, 4600 + 1400
g.box("EdGraphNode_Comment_910", X4 - 80, Y4 - 200, 2800, 1400, "Seated pose follows the view (legs stay put)")
c4 = b_and(X4 + 100, Y4 + 250, self_get("SeatedMode", "bool", X4 - 100, Y4 + 250),
           b_not(X4 - 100, Y4 + 350, self_get("Standing", "bool", X4 - 300, Y4 + 350)))
br4 = branch(X4 + 300, Y4, "seated? (pose)", c4)
g.link(sq["then_4"], br4["execute"])
# build 26: the controller's own rotation. PC.GetControlRotation (pawn) returns the camera's view, which
# this pose itself drives: a feedback loop that shook the view at rest (probe burst, build 25).
pc4 = lib_pure(GS, "GameplayStatics", "GetPlayerController", X4 - 150, Y4 + 500,
               [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
crot = member_pure(ACTOR, "K2_GetActorRotation", X4 + 100, Y4 + 500, as_pc, [("ReturnValue", "struct", dict(sub=ROT, out=True))])
cbrk = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X4 + 350, Y4 + 500,
                [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                 ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(crot["ReturnValue"], cbrk["InRot"])
dyaw = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X4 + 600, Y4 + 500,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(self_get("BodyYaw", "real", X4 + 450, Y4 + 550, subcat="double"), dyaw["A"])
g.link(self_get("SeatYaw", "real", X4 + 450, Y4 + 650, subcat="double"), dyaw["B"])
nax = lib_pure(KML, "KismetMathLibrary", "NormalizeAxis", X4 + 850, Y4 + 500,
               [("Angle", "real", dict(subcat="float", extra='DefaultValue="0.0",')), ("ReturnValue", "real", dict(subcat="float", out=True))])
g.link(dyaw["ReturnValue"], nax["Angle"])
mrc = lib_pure(KML, "KismetMathLibrary", "MapRangeClamped", X4 + 1100, Y4 + 500,
               [("Value", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("InRangeA", "real", dict(subcat="double", extra='DefaultValue="-75.0",')),
                ("InRangeB", "real", dict(subcat="double", extra='DefaultValue="75.0",')),
                ("OutRangeA", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("OutRangeB", "real", dict(subcat="double", extra='DefaultValue="0.995",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(nax["ReturnValue"], mrc["Value"])
# resting table: position = row * 23/30 + (clamp(pitch) + 60) / 150, row = snap(clamp(yaw) + 75, 0.25) / 0.25 (build 35)
def kml(member, x, y, pins):
    return lib_pure(KML, "KismetMathLibrary", member, x, y, pins)


def dpin(n, default="0.0"):
    return (n, "real", dict(subcat="double", extra=f'DefaultValue="{default}",'))


RET = ("ReturnValue", "real", dict(subcat="double", out=True))
ycl = kml("FClamp", X4 + 1100, Y4 + 800, [dpin("Value"), dpin("Min", "-75.0"), dpin("Max", "75.0"), RET])
g.link(nax["ReturnValue"], ycl["Value"])
yad = kml("Add_DoubleDouble", X4 + 1300, Y4 + 800, [dpin("A"), dpin("B", "75.0"), RET])
g.link(ycl["ReturnValue"], yad["A"])
yrd = kml("GridSnap_Float", X4 + 1500, Y4 + 800, [dpin("Location"), dpin("GridSize", "0.25"), RET])
g.link(yad["ReturnValue"], yrd["Location"])
yrow = kml("Multiply_DoubleDouble", X4 + 1700, Y4 + 800, [dpin("A"), dpin("B", "3.066666667"), RET])
g.link(yrd["ReturnValue"], yrow["A"])
pbrk = cbrk  # control rotation pitch
pna = kml("NormalizeAxis", X4 + 850, Y4 + 1000, [("Angle", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                                                ("ReturnValue", "real", dict(subcat="float", out=True))])
AIP4 = cls("/Script/Stalker2.AnimInstancePlayer")
CDS = "\"/Script/CoreUObject.ScriptStruct'/Script/Stalker2.AnimPlayerCameraData'\""
c4c = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), X4 + 700, Y4 - 150, "player anim (look pitch)", [f"TargetType={AIP4}"]))
c4c.pin("CastFailed", "exec", out=True)
c4c.pin("Object", "object", sub=OBJ)
c4c.pin("AsAnimInstancePlayer", "object", sub=AIP4, out=True)
c4c.pin("bSuccess", "bool", out=True)
g.link(anim, c4c["Object"])
cd4 = other_get(AIP4, "CameraData", "struct", X4 + 400, Y4 + 1150, c4c["AsAnimInstancePlayer"], sub=CDS)
bk4 = Node(g, BG + "K2Node_BreakStruct", nm("K2Node_BreakStruct"), X4 + 600, Y4 + 1150, "", [f"StructType={CDS}", "bMadeAfterOverridePinRemoval=True"])
bk4.pin("AnimPlayerCameraData", "struct", sub=CDS)
bk4.pin("ClampedControlPitch", "real", subcat="float", out=True)
g.link(cd4, bk4["AnimPlayerCameraData"])
lvp = kml("MapRangeUnclamped", X4 + 650, Y4 + 1000, [dpin("Value"), dpin("InRangeA", "0.0"), dpin("InRangeB", "1.0"),
                                                      dpin("OutRangeA", "90.0"), dpin("OutRangeB", "-90.0"), RET])
g.link(bk4["ClampedControlPitch"], lvp["Value"])
g.link(lvp["ReturnValue"], pna["Angle"])
pmap = kml("MapRangeClamped", X4 + 1100, Y4 + 1000, [dpin("Value"), dpin("InRangeA", "-60.0"), dpin("InRangeB", "50.0"),
                                                     dpin("OutRangeA", "0.0"), dpin("OutRangeB", "0.733333333"), RET])
g.link(pna["ReturnValue"], pmap["Value"])
rpos = kml("Add_DoubleDouble", X4 + 1900, Y4 + 900, [dpin("A"), dpin("B"), RET])
g.link(yrow["ReturnValue"], rpos["A"])
g.link(pmap["ReturnValue"], rpos["B"])
selp = kml("SelectFloat", X4 + 2100, Y4 + 600, [dpin("A"), dpin("B"), ("bPickA", "bool", dict(extra='DefaultValue="false",')), RET])
g.link(mrc["ReturnValue"], selp["A"])
g.link(rpos["ReturnValue"], selp["B"])
g.link(self_get("PoseAdditive", "bool", X4 + 1900, Y4 + 700), selp["bPickA"])
setpos = member_call(ANIMI, "Montage_SetPosition", X4 + 1400, Y4, anim, "frame = view yaw", [
    ("Montage", "object", dict(sub=MONTCLS)), ("NewPosition", "real", dict(subcat="float", extra='DefaultValue="0.0",'))])
setpos.pins["Montage"].const = True
g.link(self_get("PoseMontage", "object", X4 + 1200, Y4 + 300, sub=MONTCLS), setpos["Montage"])
# build 32: land exactly on the frame whatever the montage's rate: the anim update after this tick advances it by
# DeltaSeconds * rate (the pause does not hold in game: probe showed @1.00 and a drift of one frame time)
rate4 = member_pure(ANIMI, "Montage_GetPlayRate", X4 + 1700, Y4 + 1300, anim,
                    [("Montage", "object", dict(sub=MONTCLS)), ("ReturnValue", "real", dict(subcat="float", out=True))])
rate4.pins["Montage"].const = True
g.link(self_get("PoseMontage", "object", X4 + 1500, Y4 + 1400, sub=MONTCLS), rate4["Montage"])
adv4 = kml("Multiply_DoubleDouble", X4 + 1900, Y4 + 1300, [dpin("A"), dpin("B"), RET])
g.link(tick["DeltaSeconds"], adv4["A"])
g.link(rate4["ReturnValue"], adv4["B"])
pre4 = kml("Subtract_DoubleDouble", X4 + 2100, Y4 + 1200, [dpin("A"), dpin("B"), RET])
g.link(selp["ReturnValue"], pre4["A"])
g.link(adv4["ReturnValue"], pre4["B"])
g.link(pre4["ReturnValue"], setpos["NewPosition"])
stance_ar = b_or(X4 - 300, Y4 - 1400, b_or(X4 - 450, Y4 - 1450, q_act, b_or(X4 - 600, Y4 - 1450, q_def, q_up)), nz3["ReturnValue"])
neq_st = lib_pure(KML, "KismetMathLibrary", "NotEqual_BoolBool", X4 - 150, Y4 - 1400,
                  [("A", "bool", dict(extra='DefaultValue="false",')), ("B", "bool", dict(extra='DefaultValue="false",')),
                   ("ReturnValue", "bool", dict(out=True))])
g.link(stance_ar, neq_st["A"])
g.link(self_get("PoseAR", "bool", X4 - 300, Y4 - 1300), neq_st["B"])
brst = branch(X4 + 50, Y4 - 1400, "free arms on the wrong stance?",
              b_and(X4, Y4 - 1250, self_get("PoseAdditive", "bool", X4 - 150, Y4 - 1250), neq_st["ReturnValue"]))
sti = self_set("StanceTicks", "int", X4 + 350, Y4 - 1600, "wrong stance: one more tick")
sti_add = lib_pure(KML, "KismetMathLibrary", "Add_IntInt", X4 + 200, Y4 - 1750,
                   [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="1",')), ("ReturnValue", "int", dict(out=True))])
g.link(self_get("StanceTicks", "int", X4 + 50, Y4 - 1750), sti_add["A"])
g.link(sti_add["ReturnValue"], sti["StanceTicks"])
g.link(br4["then"], brst["execute"])   # build 42: this wire was lost in build 41 (step 4 never ran: body not held, pose at row 0)
g.link(brst["then"], sti["execute"])
stz = self_set("StanceTicks", "int", X4 + 350, Y4 - 1150, "stance matches", default="0")
g.link(brst["else"], stz["execute"])
g.link(stz["then"], c4c["execute"])
long_st = lib_pure(KML, "KismetMathLibrary", "Greater_IntInt", X4 + 500, Y4 - 1750,
                   [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="20",')), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("StanceTicks", "int", X4 + 350, Y4 - 1800), long_st["A"])
brlong = branch(X4 + 600, Y4 - 1600, "wrong for 20 ticks?", long_st["ReturnValue"])
g.link(sti["then"], brlong["execute"])
g.link(brlong["else"], c4c["execute"])
stz2 = self_set("StanceTicks", "int", X4 + 850, Y4 - 1600, "", default="0")
g.link(brlong["then"], stz2["execute"])
brwh = branch(X4 + 350, Y4 - 1400, "item / weapon stance?", stance_ar)
g.link(stz2["then"], brwh["execute"])
p_ar = play_additive(X4 + 650, Y4 - 1550, "free arms: item stance", {"then": brwh["then"]}, None, 0.25)
p_bh = play_additive(X4 + 650, Y4 - 1300, "free arms: empty hands", {"then": brwh["else"]}, SIT_ADD_BH, 0.25)
s_ar = self_set("PoseAR", "bool", X4 + 1650, Y4 - 1400, "stance of the free-arms table")
g.link(stance_ar, s_ar["PoseAR"])
g.link(p_ar["then"], s_ar["execute"])
g.link(p_bh["then"], s_ar["execute"])
g.link(s_ar["then"], c4c["execute"])
# (brst else -> stance matches -> c4c, above)
# ---- 8: remember where the actor is, for the "still?" test of the next tick ----
sll = self_set("LastLoc", "struct", 400, 12000, "position this tick", sub=VEC)
g.link(member_pure(ACTOR, "K2_GetActorLocation", 250, 12200, as_pc, [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"], sll["LastLoc"])
g.link(sq["then_8"], sll["execute"])
pz4 = member_call(ANIMI, "Montage_SetPlayRate", X4 + 1150, Y4 - 150, anim, "keep it paused", [
    ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="0.000100",'))])
pz4.pins["Montage"].const = True
g.link(self_get("PoseMontage", "object", X4 + 1000, Y4 + 150, sub=MONTCLS), pz4["Montage"])
actor_yaw = cbrk["Yaw"]
targ = kml("SelectFloat", X4 + 700, Y4 - 700, [dpin("A"), dpin("B"), ("bPickA", "bool", dict(extra='DefaultValue="false",')), RET])
g.link(actor_yaw, targ["A"])
g.link(self_get("SeatYaw", "real", X4 + 550, Y4 - 600, subcat="double"), targ["B"])
g.link(self_get("PoseAdditive", "bool", X4 + 550, Y4 - 500), targ["bPickA"])
dd = kml("Subtract_DoubleDouble", X4 + 900, Y4 - 700, [dpin("A"), dpin("B"), RET])
g.link(targ["ReturnValue"], dd["A"])
g.link(self_get("BodyYaw", "real", X4 + 750, Y4 - 800, subcat="double"), dd["B"])
dn = kml("NormalizeAxis", X4 + 1100, Y4 - 700, [("Angle", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                                                ("ReturnValue", "real", dict(subcat="float", out=True))])
g.link(dd["ReturnValue"], dn["Angle"])
rate_b = kml("SelectFloat", X4 + 700, Y4 - 1000, [dpin("A", "10.0"), dpin("B", "2.5"), ("bPickA", "bool", dict(extra='DefaultValue="false",')), RET])
g.link(self_get("PoseAdditive", "bool", X4 + 550, Y4 - 1050), rate_b["bPickA"])
al = kml("Multiply_DoubleDouble", X4 + 900, Y4 - 900, [dpin("A"), dpin("B"), RET])
g.link(tick["DeltaSeconds"], al["A"])
g.link(rate_b["ReturnValue"], al["B"])
alc = kml("FMin", X4 + 1100, Y4 - 900, [dpin("A"), dpin("B", "1.0"), RET])
g.link(al["ReturnValue"], alc["A"])
stp = kml("Multiply_DoubleDouble", X4 + 1300, Y4 - 800, [dpin("A"), dpin("B"), RET])
g.link(dn["ReturnValue"], stp["A"])
g.link(alc["ReturnValue"], stp["B"])
eased = kml("Add_DoubleDouble", X4 + 1500, Y4 - 800, [dpin("A"), dpin("B"), RET])
g.link(self_get("BodyYaw", "real", X4 + 1350, Y4 - 900, subcat="double"), eased["A"])
g.link(stp["ReturnValue"], eased["B"])
# once the camera is back on the head during an action, the body follows the view exactly
follow = kml("SelectFloat", X4 + 1700, Y4 - 800, [dpin("A"), dpin("B"), ("bPickA", "bool", dict(extra='DefaultValue="false",')), RET])
g.link(actor_yaw, follow["A"])
g.link(eased["ReturnValue"], follow["B"])
g.link(b_and(X4 + 1550, Y4 - 650, self_get("PoseAdditive", "bool", X4 + 1400, Y4 - 650),
             b_not(X4 + 1400, Y4 - 580, self_get("CamUnhooked", "bool", X4 + 1250, Y4 - 580))), follow["bPickA"])
sby = self_set("BodyYaw", "real", X4 + 1900, Y4 - 1000, "body facing: eased", subcat="double")
g.link(follow["ReturnValue"], sby["BodyYaw"])
g.link(c4c["then"], sby["execute"])
g.link(sby["then"], pz4["execute"])
g.link(pz4["then"], setpos["execute"])
mesh4 = other_get(CHAR, "Mesh", "object", X4 + 1900, Y4 + 150, as_pc, sub=SKM)
by4 = self_get("BodyYaw", "real", X4 + 1700, Y4 - 500, subcat="double")
hold = set_rot("K2_SetWorldRotation", X4 + 2000, Y4 - 350, mesh4, make_rot(X4 + 1850, Y4 - 500, yaw_pin=by4), "body facing = BodyYaw")
g.link(setpos["then"], hold["execute"])
# the shadow body is its own component under the actor (build 36: a second shadow turned with the view)
shd4 = other_get(PC, "ShadowMeshComponent", "object", X4 + 2100, Y4 - 700, as_pc, sub=SKM)
dbl_add = lib_pure(KML, "KismetMathLibrary", "Add_DoubleDouble", X4 + 2000, Y4 - 850,
                   [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                    ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(by4, dbl_add["A"])
g.link(self_get("ShadowRelY", "real", X4 + 1850, Y4 - 750, subcat="double"), dbl_add["B"])
hsh = set_rot("K2_SetWorldRotation", X4 + 2300, Y4 - 700, shd4, make_rot(X4 + 2150, Y4 - 850, yaw_pin=dbl_add["ReturnValue"]), "shadow with the body")
g.link(hold["then"], hsh["execute"])
# aligned = action pose and the body within 1 deg of the view
off4 = kml("Subtract_DoubleDouble", X4 + 2200, Y4 + 500, [dpin("A"), dpin("B"), RET])
g.link(actor_yaw, off4["A"])
g.link(by4, off4["B"])
offn = kml("NormalizeAxis", X4 + 2400, Y4 + 500, [("Angle", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                                                 ("ReturnValue", "real", dict(subcat="float", out=True))])
g.link(off4["ReturnValue"], offn["Angle"])
offa = kml("Abs", X4 + 2600, Y4 + 500, [dpin("A"), RET])
g.link(offn["ReturnValue"], offa["A"])
near = kml("Less_DoubleDouble", X4 + 2800, Y4 + 500, [dpin("A"), dpin("B", "1.0"), ("ReturnValue", "bool", dict(out=True))])
g.link(offa["ReturnValue"], near["A"])
bral = branch(X4 + 2600, Y4 - 150, "action and body faces the view?",
              b_and(X4 + 2900, Y4 + 350, self_get("PoseAdditive", "bool", X4 + 2750, Y4 + 300), near["ReturnValue"]))
g.link(hsh["then"], bral["execute"])
cam4 = cam_of(X4 + 2100, Y4 + 150, as_pc)
# not aligned: camera unhooked (once), pointed at the view every tick
bru = branch(X4 + 2900, Y4 - 700, "camera still hooked?", b_not(X4 + 2800, Y4 - 550, self_get("CamUnhooked", "bool", X4 + 2650, Y4 - 550)))
g.link(bral["else"], bru["execute"])
unh = set_abs_rot(X4 + 3200, Y4 - 700, cam4, "true", "camera unhooked from the body (once)")
g.link(bru["then"], unh["execute"])
unf = self_set("CamUnhooked", "bool", X4 + 3500, Y4 - 700, "camera unhooked", default="true")
g.link(unh["then"], unf["execute"])
view = set_rot("K2_SetWorldRotation", X4 + 3800, Y4 - 350, cam4,
               make_rot(X4 + 3650, Y4 - 500, pitch_pin=pna["ReturnValue"], yaw_pin=actor_yaw), "camera = the view")
vhq = kml("Greater_IntInt", X4 + 3500, Y4 - 950, [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="0",')),
                                                 ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("ViewHold", "int", X4 + 3350, Y4 - 950), vhq["A"])
brvh = branch(X4 + 3650, Y4 - 700, "still holding the sit-end view?", vhq["ReturnValue"])
g.link(unf["then"], brvh["execute"])
g.link(bru["else"], brvh["execute"])
g.link(brvh["else"], view["execute"])
held = set_rot("K2_SetWorldRotation", X4 + 3950, Y4 - 900, cam4,
               make_rot(X4 + 3800, Y4 - 1050, pitch_pin=self_get("TakeP", "real", X4 + 3650, Y4 - 1100, subcat="double"),
                        yaw_pin=self_get("TakeY", "real", X4 + 3650, Y4 - 1000, subcat="double")), "camera = the sit-end view")
g.link(brvh["then"], held["execute"])
vdec = kml("Subtract_IntInt", X4 + 4100, Y4 - 1100, [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="1",')),
                                                   ("ReturnValue", "int", dict(out=True))])
g.link(self_get("ViewHold", "int", X4 + 3950, Y4 - 1150), vdec["A"])
vdn = self_set("ViewHold", "int", X4 + 4250, Y4 - 900, "one frame less")
g.link(vdec["ReturnValue"], vdn["ViewHold"])
g.link(held["then"], vdn["execute"])
# aligned: camera back on the head (once); from then on the body follows the view exactly (BodyYaw above)
brh4 = branch(X4 + 2900, Y4 + 150, "camera unhooked? (action)", self_get("CamUnhooked", "bool", X4 + 2750, Y4 + 200))
g.link(bral["then"], brh4["execute"])
cr4 = make_rot(X4 + 3100, Y4 + 450, self_get("CamRelP", "real", X4 + 2950, Y4 + 550, subcat="double"),
               self_get("CamRelY", "real", X4 + 2950, Y4 + 650, subcat="double"))
hk1 = set_abs_rot(X4 + 3200, Y4 + 150, cam4, "false", "camera back on the head")
g.link(brh4["then"], hk1["execute"])
hk2 = set_rot("K2_SetRelativeRotation", X4 + 3500, Y4 + 150, cam4, cr4, "")
g.link(hk1["then"], hk2["execute"])
hk3 = self_set("CamUnhooked", "bool", X4 + 3800, Y4 + 150, "camera hooked", default="false")
g.link(hk2["then"], hk3["execute"])

# =====================================================================
# Stand up: move / jump / interact
# =====================================================================
XS, YS = 0, 2400
g.box("EdGraphNode_Comment_905", XS - 80, YS - 640, 11700, 1600, "Stand up (move, jump or interact while seated)")
evs = []
for k, ia in enumerate(["IA_PlayerCAExit", "IA_LocomotionForward", "IA_Jump", "IA_Interact"]):  # the build 7-13 crashes were the post-process swaps
    ev = Node(g, "/Script/InputBlueprintNodes.K2Node_EnhancedInputAction", nm("K2Node_EnhancedInputAction"), XS, YS + 220 * k, "",
              [f"InputAction=\"/Script/EnhancedInput.InputAction'{IA_DIR}{ia}.{ia}'\""])
    for e in ("Triggered", "Started", "Ongoing", "Canceled", "Completed"):
        ev.pin(e, "exec", out=True)
    if ia == "IA_LocomotionForward":
        ev.pin("ActionValue", "struct", sub=V2D, out=True)
    elif ia == "IA_PlayerCAExit":
        ev.pin("ActionValue", "bool", out=True)
    else:
        ev.pin("ActionValue", "bool", out=True)
    ev.pin("ElapsedSeconds", "real", subcat="double", out=True, adv=True)
    ev.pin("TriggeredSeconds", "real", subcat="double", out=True, adv=True)
    ev.pin("InputAction", "object", sub=IA_CLS, out=True)
    evs.append(ev["Started"])
sc = player_cast(XS + 500, YS, "stand", evs)
cs = b_and(XS + 600, YS + 300, self_get("SeatedMode", "bool", XS + 400, YS + 280),
           b_not(XS + 400, YS + 380, self_get("Standing", "bool", XS + 200, YS + 380)))
brs = branch(XS + 800, YS, "seated? (stand)", cs)
g.link(sc["then"], brs["execute"])
st1 = self_set("Standing", "bool", XS + 1100, YS, "standing: on", default="true")
st2 = self_set("SeatedMode", "bool", XS + 1350, YS, "seated mode: off", default="false")
yaw_on = set_yaw_follow(XS + 1600, YS, sc["AsPC"], "true", "body follows mouse again")
anim_s = member_pure(SKM, "GetAnimInstance", XS + 1700, YS + 450, other_get(CHAR, "Mesh", "object", XS + 1500, YS + 450, sc["AsPC"], sub=SKM),
                     [("ReturnValue", "object", dict(sub=ANIMI, out=True))])["ReturnValue"]
ps = play_sit(XS + 5300, YS, sc["AsPC"], "Out", "stand-up animation")
dl = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), XS + 5600, YS, "wait for stand-up",
          [f"FunctionReference=(MemberParent={KSL},MemberName=\"Delay\")"])
dl.pin("execute", "exec")
dl.pin("then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "Completed", "Completed"),')
dl.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
dl.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
dl.pin("Duration", "real", subcat="float", extra=f'DefaultValue="{STAND_DELAY:.6f}",')
dl.pin("LatentInfo", "struct", sub=LATENT, hidden=True)
mvs = member_call(CMC, "SetMovementMode", XS + 9800, YS, other_get(CHAR, "CharacterMovement", "object", XS + 9700, YS + 300, sc["AsPC"], sub=CMC),
                  "walking again", [("NewMovementMode", "byte", dict(sub=MOVEMODE, extra='DefaultValue="MOVE_Walking",')),
                                    ("NewCustomMode", "byte", dict(extra='DefaultValue="0",'))])
g.link(brs["then"], st1["execute"])
sa_s = stop_additive(XS + 1900, YS + 250, "seated pose off", yaw_on, other_get(CHAR, "Mesh", "object", XS + 1600, YS + 500, sc["AsPC"], sub=SKM) if False else anim_s)
show_s = member_call(PC, "EnableInteractions", XS + 1350, YS + 250, sc["AsPC"], "interaction prompts back")
rel_s = body_release(XS + 1100, YS - 700, sc["AsPC"], st2, "stand")
chain(st1, st2)
chain(rel_s, show_s, yaw_on)
chain(sa_s, ps, dl)
g.link(dl["then"], mvs["execute"])
lastr = restore_limits(XS + 10100, YS, "stand", mvs)
st3 = self_set("Standing", "bool", XS + 11300, YS, "standing: off", default="false")
eq_s = member_call(PC, "EquipLastHeldItem", XS + 10900, YS + 250, sc["AsPC"], "weapon back")
rss = member_call(PC, "RestoreStatesAfterInteraction", XS + 10600, YS + 250, sc["AsPC"], "weapon state back")
pcs = lib_pure(GS, "GameplayStatics", "GetPlayerController", XS + 11000, YS + 500,
               [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
rmi = member_call(cls("/Script/Engine.Controller"), "ResetIgnoreMoveInput", XS + 11100, YS + 250, pcs, "movement input back")
imc_s = load_imc(XS + 11400, YS - 400, "IMC_PlayerCA", {"then": None}["then"] if False else rmi["then"], "seated controls (game path)")
EILPS_S = cls("/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem")
sub_s = Node(g, BG + "K2Node_GetSubsystemFromPC", nm("K2Node_GetSubsystemFromPC"), XS + 11700, YS - 150, "", [f"CustomClass={EILPS_S}"])
sub_s.pin("PlayerController", "object", sub=cls("/Script/Engine.PlayerController"))
sub_s.pin("ReturnValue", "object", sub=EILPS_S, out=True)
g.link(pcs, sub_s["PlayerController"])
rmc = member_call(cls("/Script/EnhancedInput.EnhancedInputSubsystemInterface"), "RemoveMappingContext", XS + 12000, YS - 400, sub_s["ReturnValue"],
                  "seated controls off", [("MappingContext", "object", dict(sub=cls("/Script/EnhancedInput.InputMappingContext"))),
                                          ("Options", "struct", dict(sub="\"/Script/CoreUObject.ScriptStruct'/Script/EnhancedInput.ModifyContextOptions'\""))])
rmc.pins["self"].cat = "interface"
rmc.pins["MappingContext"].const = True
rmc.pins["Options"].ref = True
rmc.pins["Options"].const = True
g.link(imc_s["AsInputMappingContext"], rmc["MappingContext"])
g.link(imc_s["then"], rmc["execute"])
g.link(rmc["then"], st3["execute"])
chain(lastr, eq_s, rmi)

# =====================================================================
# Guitar: G hands back to the vanilla sit
# =====================================================================
XG, YG = 0, 3900
g.box("EdGraphNode_Comment_906", XG - 80, YG - 640, 9000, 1600, "Guitar: G hands back to the vanilla sit")
gk = Node(g, BG + "K2Node_InputKey", nm("K2Node_InputKey"), XG, YG, "",
          ["InputKey=G", "bConsumeInput=False"])
gk.pin("Pressed", "exec", out=True)
gk.pin("Released", "exec", out=True)
gk.pin("Key", "struct", sub=KEY, out=True)
gc = player_cast(XG + 500, YG, "guitar", [gk["Pressed"]])
cg = b_and(XG + 600, YG + 300, b_and(XG + 500, YG + 200, self_get("SeatedMode", "bool", XG + 300, YG + 180),
                                    b_not(XG + 300, YG + 240, self_get("GuitarDirect", "bool", XG + 100, YG + 240))),
           b_not(XG + 400, YG + 380, self_get("Standing", "bool", XG + 200, YG + 380)))
brg = branch(XG + 800, YG, "seated? (guitar)", cg)
g.link(gc["then"], brg["execute"])
g1 = self_set("SeatedMode", "bool", XG + 1100, YG, "seated mode: off (guitar)", default="false")
g2 = self_set("VanillaHold", "bool", XG + 1350, YG, "vanilla hold: on", default="true")
gm = member_call(CMC, "SetMovementMode", XG + 1600, YG, other_get(CHAR, "CharacterMovement", "object", XG + 1500, YG + 300, gc["AsPC"], sub=CMC),
                 "walking mode back (guitar)", [("NewMovementMode", "byte", dict(sub=MOVEMODE, extra='DefaultValue="MOVE_Walking",')),
                                                ("NewCustomMode", "byte", dict(extra='DefaultValue="0",'))])
gd1 = self_set("GuitarDirect", "bool", XG + 1100, YG - 700, "guitar: try direct", default="true")
g.link(brg["then"], g1["execute"])
gdt = self_set("LastPutAway", "real", XG + 1350, YG - 700, "direct try time", subcat="double")
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", XG + 1250, YG - 900,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"],
       gdt["LastPutAway"])
gdf = other_set(PC, "bInContextualAction", "bool", XG + 1600, YG - 700, gc["AsPC"], "sit state on (guitar)", default="true")
chain(gd1, gdt, gdf)
yaw_g = set_yaw_follow(XG + 1850, YG, gc["AsPC"], "true", "body follows mouse again (guitar)")
show_g = member_call(PC, "EnableInteractions", XG + 1350, YG + 250, gc["AsPC"], "interaction prompts back (guitar)")
gp0 = self_set("GuitarPending", "bool", XG + 1350, YG - 250, "guitar requested", default="true")
gt0 = self_set("LastPutAway", "real", XG + 1600, YG - 250, "guitar request time", subcat="double")
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", XG + 1500, YG - 450,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"],
       gt0["LastPutAway"])
chain(g1, g2, gp0, gt0, show_g, gm, yaw_g)
lastg = restore_limits(XG + 2100, YG, "guitar", yaw_g)
anim_g = member_pure(SKM, "GetAnimInstance", XG + 3100, YG + 450, other_get(CHAR, "Mesh", "object", XG + 2900, YG + 450, gc["AsPC"], sub=SKM),
                     [("ReturnValue", "object", dict(sub=ANIMI, out=True))])["ReturnValue"]
dlg = delay(XG + 3600, YG, 0.05, "one frame")
g.link(lastg["then"], dlg["execute"])
back = member_call(PC, "SetInteractionTarget", XG + 7500, YG, gc["AsPC"], "resume vanilla sit",
                   [("Target", "object", dict(sub=ICOMP))])
g.link(self_get("TargetSaved", "object", XG + 7400, YG + 260, sub=ICOMP), back["Target"])
eq_g = member_call(PC, "EquipLastHeldItem", XG + 3750, YG + 250, gc["AsPC"], "weapon back (vanilla sit stores it)")
gpc2 = lib_pure(GS, "GameplayStatics", "GetPlayerController", XG + 3700, YG + 600,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                 ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
mkr = lib_pure(KML, "KismetMathLibrary", "MakeRotator", XG + 3900, YG + 600,
               [("Roll", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                ("Pitch", "real", dict(subcat="float", extra='DefaultValue="-15.0",')),
                ("Yaw", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                ("ReturnValue", "struct", dict(sub=ROT, out=True))])
g.link(self_get("SeatYaw", "real", XG + 3700, YG + 800, subcat="double"), mkr["Yaw"])
scr = member_call(cls("/Script/Engine.Controller"), "SetControlRotation", XG + 4100, YG, gpc2, "face the seat",
                  [("NewRotation", "struct", dict(sub=ROT))])
scr.pins["NewRotation"].ref = True
scr.pins["NewRotation"].const = True
g.link(mkr["ReturnValue"], scr["NewRotation"])
sar = member_call(ACTOR, "K2_SetActorRotation", XG + 4400, YG, gc["AsPC"], "turn to the seat now", [
    ("NewRotation", "struct", dict(sub=ROT)), ("bTeleportPhysics", "bool", dict(extra='DefaultValue="true",')),
    ("ReturnValue", "bool", dict(out=True))])
g.link(make_rot(XG + 4300, YG + 600, yaw_pin=self_get("SeatYaw", "real", XG + 4150, YG + 700, subcat="double")), sar["NewRotation"])
g.link(dlg["then"], scr["execute"])
g.link(scr["then"], sar["execute"])
rel_g = body_release(XG + 4700, YG, gc["AsPC"], sar, "guitar")
loc_g = set_actor_loc(XG + 6200, YG, gc["AsPC"], self_get("SeatLoc", "struct", XG + 6050, YG + 250, sub=VEC), "on the seat spot")
g.link(rel_g["then"], loc_g["execute"])
ca_g = member_pure(cls("/Script/Engine.ActorComponent"), "GetOwner", XG + 6300, YG + 500,
                   self_get("TargetSaved", "object", XG + 6150, YG + 500, sub=ICOMP), [("ReturnValue", "object", dict(sub=ACTOR, out=True))])["ReturnValue"]
ca_loc = member_pure(ACTOR, "K2_GetActorLocation", XG + 6500, YG + 600, ca_g, [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"]
sca = self_set("CAOrig", "struct", XG + 6500, YG, "the seat point's own spot", sub=VEC)
g.link(ca_loc, sca["CAOrig"])
g.link(loc_g["then"], sca["execute"])
sca_o = self_set("CAActor", "object", XG + 6750, YG, "the seat point", sub=ACTOR)
g.link(ca_g, sca_o["CAActor"])
g.link(sca["then"], sca_o["execute"])
my_loc = member_pure(ACTOR, "K2_GetActorLocation", XG + 6800, YG + 700, gc["AsPC"], [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"]
mbk = lib_pure(KML, "KismetMathLibrary", "BreakVector", XG + 7000, YG + 700,
               [("InVec", "struct", dict(sub=VEC)), ("X", "real", dict(subcat="double", out=True)), ("Y", "real", dict(subcat="double", out=True)),
                ("Z", "real", dict(subcat="double", out=True))])
g.link(my_loc, mbk["InVec"])
cbk = lib_pure(KML, "KismetMathLibrary", "BreakVector", XG + 7000, YG + 900,
               [("InVec", "struct", dict(sub=VEC)), ("X", "real", dict(subcat="double", out=True)), ("Y", "real", dict(subcat="double", out=True)),
                ("Z", "real", dict(subcat="double", out=True))])
g.link(ca_loc, cbk["InVec"])
mkv_ = lib_pure(KML, "KismetMathLibrary", "MakeVector", XG + 7200, YG + 800,
                [("X", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("Y", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("Z", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("ReturnValue", "struct", dict(sub=VEC, out=True))])
g.link(mbk["X"], mkv_["X"])
g.link(mbk["Y"], mkv_["Y"])
g.link(cbk["Z"], mkv_["Z"])
mv_ca = set_actor_loc(XG + 7000, YG, self_get("CAActor", "object", XG + 6850, YG + 250, sub=ACTOR), mkv_["ReturnValue"], "seat point under us (for the hand-back)")
g.link(sca_o["then"], mv_ca["execute"])
cam_on = self_set("CAMoved", "bool", XG + 7300, YG, "seat point moved", default="true")
g.link(mv_ca["then"], cam_on["execute"])
g.link(cam_on["then"], back["execute"])

gpc = lib_pure(GS, "GameplayStatics", "GetPlayerController", XG + 7800, YG + 450,
               [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)),
                ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])
EILPS = cls("/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem")
EISI = cls("/Script/EnhancedInput.EnhancedInputSubsystemInterface")
sub_n = Node(g, BG + "K2Node_GetSubsystemFromPC", nm("K2Node_GetSubsystemFromPC"), XG + 8100, YG + 450, "",
             [f"CustomClass={EILPS}"])
sub_n.pin("PlayerController", "object", sub=cls("/Script/Engine.PlayerController"))
sub_n.pin("ReturnValue", "object", sub=EILPS, out=True)
g.link(gpc["ReturnValue"], sub_n["PlayerController"])
IAV = "\"/Script/CoreUObject.ScriptStruct'/Script/EnhancedInput.InputActionValue'\""
mkv = lib_pure(cls("/Script/EnhancedInput.EnhancedInputLibrary"), "EnhancedInputLibrary", "MakeInputActionValueOfType", XG + 8100, YG + 650,
               [("X", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                ("Y", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("Z", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("ValueType", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/EnhancedInput.EInputActionValueType'\"", extra='DefaultValue="Boolean",')),
                ("ReturnValue", "struct", dict(sub=IAV, out=True))])
mkv.pins["self"].extra = 'DefaultObject="/Script/EnhancedInput.Default__EnhancedInputLibrary",'
inj = member_call(EISI, "InjectInputForAction", XG + 8400, YG, sub_n["ReturnValue"], "press the guitar action", [
    ("Action", "object", dict(sub=IA_CLS, extra=f'DefaultObject="{IA_GUITAR}",')),
    ("RawValue", "struct", dict(sub=IAV)),
    ("Modifiers", "object", dict(sub=cls("/Script/EnhancedInput.InputModifier"))),
    ("Triggers", "object", dict(sub=cls("/Script/EnhancedInput.InputTrigger")))])
inj.pins["Action"].const = True
inj.pins["self"].cat = "interface"
for an in ("Modifiers", "Triggers"):
    inj.pins[an].container = "Array"
    inj.pins[an].ref = True
    inj.pins[an].const = True
g.link(mkv["ReturnValue"], inj["RawValue"])
# ---- 5: guitar pending: skip the vanilla sit-down, then press the guitar action once it idles ----
X5, Y5 = 1200, 7600
g.box("EdGraphNode_Comment_911", X5 - 80, Y5 - 200, 3000, 1000, "Guitar: skip the sit-down, then press the guitar action")
br5 = branch(X5 + 300, Y5, "guitar pending?", self_get("GuitarPending", "bool", X5 - 100, Y5 + 250))
g.link(sq["then_5"], br5["execute"])
sec5 = member_pure(ANIMI, "Montage_GetCurrentSection", X5 + 300, Y5 + 450, anim,
                   [("Montage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')),
                    ("ReturnValue", "name", dict(out=True))])["ReturnValue"]
now5 = lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X5 + 100, Y5 + 650,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])
age5 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X5 + 300, Y5 + 650,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now5["ReturnValue"], age5["A"])
g.link(self_get("LastPutAway", "real", X5 + 100, Y5 + 750, subcat="double"), age5["B"])
old5 = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X5 + 500, Y5 + 650,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="8.0",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(age5["ReturnValue"], old5["A"])
brto = branch(X5 + 500, Y5 - 150, "guitar request too old?", old5["ReturnValue"])
g.link(br5["then"], brto["execute"])
gto = self_set("GuitarPending", "bool", X5 + 800, Y5 - 300, "give up (8 s)", default="false")
g.link(brto["then"], gto["execute"])
brin = branch(X5 + 600, Y5, "sitting down?", name_eq(X5 + 500, Y5 + 300, sec5, "In"))
g.link(brto["else"], brin["execute"])


def sit_rate(x, y, rate, comment):
    n = member_call(ANIMI, "Montage_SetPlayRate", x, y, anim, comment, [
        ("Montage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')),
        ("NewPlayRate", "real", dict(subcat="float", extra=f'DefaultValue="{rate:.6f}",'))])
    n.pins["Montage"].const = True
    return n


gp5 = member_pure(ANIMI, "Montage_GetPosition", X5 + 700, Y5 + 600, anim,
                  [("Montage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')), ("ReturnValue", "real", dict(subcat="float", out=True))])
gp5.pins["Montage"].const = True
early5 = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X5 + 900, Y5 + 600,
                  [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="3.9",')),
                   ("ReturnValue", "bool", dict(out=True))])
g.link(gp5["ReturnValue"], early5["A"])
brea = branch(X5 + 900, Y5 - 100, "sit-down still early?", early5["ReturnValue"])
g.link(brin["then"], brea["execute"])
skp = member_call(ANIMI, "Montage_SetPosition", X5 + 1200, Y5 - 100, anim, "to the end of the sit-down", [
    ("Montage", "object", dict(sub=MONT, extra=f'DefaultObject="{SIT}",')), ("NewPosition", "real", dict(subcat="float", extra='DefaultValue="3.930000",'))])
skp.pins["Montage"].const = True
g.link(brea["then"], skp["execute"])
bridle = branch(X5 + 900, Y5 + 150, "seated idle?", b_and(X5 + 850, Y5 + 450, name_eq(X5 + 800, Y5 + 350, sec5, "Idle"), seated_flag))
g.link(brin["else"], bridle["execute"])
gdone = self_set("GuitarPending", "bool", X5 + 1200, Y5 + 150, "guitar: once", default="false")
g.link(bridle["then"], gdone["execute"])
g.link(gdone["then"], inj["execute"])
gti = self_set("LastPutAway", "real", X5 + 1800, Y5 + 150, "guitar pressed at", subcat="double")
g.link(now5["ReturnValue"], gti["LastPutAway"])
g.link(inj["then"], gti["execute"])

# ---- 6: guitar put away (vanilla sit idling, no guitar, 3 s after the press): back to our seated mode ----
X6, Y6 = 1200, 8900
g.box("EdGraphNode_Comment_912", X6 - 80, Y6 - 200, 2600, 1100, "Guitar put away: back to our seated mode")
AIP = cls("/Script/Stalker2.AnimInstancePlayer")
GDS = "\"/Script/CoreUObject.ScriptStruct'/Script/Stalker2.AnimPlayerGuitarData'\""
pc6 = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), X6 - 400, Y6, "player anim (guitar state)", [f"TargetType={AIP}"]))
pc6.pin("CastFailed", "exec", out=True)
pc6.pin("Object", "object", sub=OBJ)
pc6.pin("AsAnimInstancePlayer", "object", sub=AIP, out=True)
pc6.pin("bSuccess", "bool", out=True)
g.link(anim, pc6["Object"])
gd6 = other_get(AIP, "GuitarData", "struct", X6 - 150, Y6 + 500, pc6["AsAnimInstancePlayer"], sub=GDS)
bk6 = Node(g, BG + "K2Node_BreakStruct", nm("K2Node_BreakStruct"), X6 + 100, Y6 + 500, "",
           [f"StructType={GDS}", "bMadeAfterOverridePinRemoval=True"])
bk6.pin("AnimPlayerGuitarData", "struct", sub=GDS)
bk6.pin("bPlayingGuitar", "bool", out=True)
g.link(gd6, bk6["AnimPlayerGuitarData"])
age6 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X6 + 100, Y6 + 750,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now5["ReturnValue"], age6["A"])
g.link(self_get("LastPutAway", "real", X6 - 100, Y6 + 850, subcat="double"), age6["B"])
late6 = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X6 + 300, Y6 + 750,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="6.0",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(age6["ReturnValue"], late6["A"])  # fallback: the guitar never came out
c6 = b_and(X6 + 600, Y6 + 300,
           b_and(X6 + 450, Y6 + 250, self_get("VanillaHold", "bool", X6 + 250, Y6 + 200),
                 b_not(X6 + 250, Y6 + 300, self_get("GuitarPending", "bool", X6 + 50, Y6 + 300))),
           b_and(X6 + 450, Y6 + 400,
                 b_and(X6 + 350, Y6 + 450, seated_flag, b_not(X6 + 350, Y6 + 550, bk6["bPlayingGuitar"])),
                 b_or(X6 + 350, Y6 + 650, self_get("LayerTried", "bool", X6 + 150, Y6 + 650), late6["ReturnValue"])))
br6 = branch(X6 + 800, Y6, "guitar put away?", c6)
g.link(sq["then_6"], pc6["execute"])
seen6 = self_set("LayerTried", "bool", X6 + 800, Y6 - 250, "guitar seen", default="true")
brs6 = branch(X6 + 500, Y6 - 250, "guitar out?", b_and(X6 + 400, Y6 - 100, self_get("VanillaHold", "bool", X6 + 200, Y6 - 100), bk6["bPlayingGuitar"]))
g.link(pc6["then"], brs6["execute"])
g.link(brs6["then"], seen6["execute"])
g.link(brs6["else"], br6["execute"])
rel6 = self_set("VanillaHold", "bool", X6 + 1100, Y6, "vanilla hold: off (seated mode takes over again)", default="false")
g.link(br6["then"], rel6["execute"])
unseen6 = self_set("LayerTried", "bool", X6 + 1400, Y6, "guitar seen: reset", default="false")
g.link(rel6["then"], unseen6["execute"])
g.link(gdf["then"], inj["execute"])

# ---- 7: direct guitar: guitar out -> hand the body to it; no guitar after 1 s -> vanilla hand-back;
#         guitar put away -> seated mode again ----
X7, Y7 = 1200, 10300
g.box("EdGraphNode_Comment_913", X7 - 80, Y7 - 400, 4200, 1500, "Guitar straight from the seated mode")
sq7 = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X7, Y7, "direct guitar")
sq7.pin("execute", "exec")
sq7.pin("then_0", "exec", out=True)
sq7.pin("then_1", "exec", out=True)
g.link(sq["then_7"], sq7["execute"])
play7 = bk6["bPlayingGuitar"]
br7 = branch(X7 + 300, Y7 - 200, "direct try running?", self_get("GuitarDirect", "bool", X7 + 100, Y7 - 50))
g.link(sq7["then_0"], br7["execute"])
br7p = branch(X7 + 600, Y7 - 200, "guitar out?", play7)
g.link(br7["then"], br7p["execute"])
d7a = self_set("GuitarDirect", "bool", X7 + 900, Y7 - 350, "direct try: done", default="false")
d7b = self_set("GuitarDirectOn", "bool", X7 + 1150, Y7 - 350, "direct guitar on", default="true")
d7c = self_set("LayerTried", "bool", X7 + 1400, Y7 - 350, "guitar seen", default="true")
d7d = self_set("SeatedMode", "bool", X7 + 1650, Y7 - 350, "seated mode: paused (guitar)", default="false")
g.link(br7p["then"], d7a["execute"])
chain(d7a, d7b, d7c, d7d)
sa7 = stop_additive(X7 + 1900, Y7 - 350, "our pose off (guitar)", d7d, anim)
age7 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X7 + 600, Y7 + 300,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now5["ReturnValue"], age7["A"])
g.link(self_get("LastPutAway", "real", X7 + 400, Y7 + 400, subcat="double"), age7["B"])
late7 = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X7 + 800, Y7 + 300,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(age7["ReturnValue"], late7["A"])
br7l = branch(X7 + 900, Y7 - 50, "no guitar after 1 s?", late7["ReturnValue"])
g.link(br7p["else"], br7l["execute"])
f7a = self_set("GuitarDirect", "bool", X7 + 1200, Y7 - 50, "direct try: failed", default="false")
f7b = other_set(PC, "bInContextualAction", "bool", X7 + 1450, Y7 - 50, as_pc, "sit state off again", default="false")
g.link(br7l["then"], f7a["execute"])
chain(f7a, f7b)
g.link(f7b["then"], g1["execute"])    # fall back: the vanilla hand-back
# put away
br7o = branch(X7 + 300, Y7 + 500, "direct guitar put away?",
              b_and(X7 + 200, Y7 + 650, self_get("GuitarDirectOn", "bool", X7, Y7 + 650), b_not(X7, Y7 + 750, play7)))
g.link(sq7["then_1"], br7o["execute"])
o7a = self_set("GuitarDirectOn", "bool", X7 + 600, Y7 + 500, "direct guitar off", default="false")
o7b = self_set("LayerTried", "bool", X7 + 850, Y7 + 500, "guitar seen: reset", default="false")
o7c = other_set(PC, "bInContextualAction", "bool", X7 + 1100, Y7 + 500, as_pc, "sit state off", default="false")
o7d = self_set("PoseAdditive", "bool", X7 + 1350, Y7 + 500, "pose: resting", default="false")
o7e = self_set("SeatedMode", "bool", X7 + 1600, Y7 + 500, "seated mode: back", default="true")
g.link(br7o["then"], o7a["execute"])
chain(o7a, o7b, o7c, o7d, o7e)

write(sys.argv[1], g.text())
print("ok", len(g.nodes), "nodes")
