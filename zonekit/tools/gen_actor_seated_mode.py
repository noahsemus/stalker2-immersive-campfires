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


POSE_PLAYS = []   # build 71: (node, "rest" | "add"); their start time is linked to the right table frame at the end


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
    POSE_PLAYS.append((n, "rest" if asset == SIT_REST else "add"))
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


def body_release(x, y, pc_pin, prev, label, keep_cam=False):
    """Mesh back under the actor, camera back on its bone (relative rotation saved at the takeover).
    keep_cam: only the mesh and the shadow (the stand-up keeps the camera unhooked until up)."""
    mesh_ = other_get(CHAR, "Mesh", "object", x, y + 300, pc_pin, sub=SKM)
    m = set_rot("K2_SetRelativeRotation", x + 200, y, mesh_, make_rot(x + 50, y + 450), f"body follows the actor again ({label})")
    shd_ = other_get(PC, "ShadowMeshComponent", "object", x + 900, y + 300, pc_pin, sub=SKM)
    sh = set_rot("K2_SetRelativeRotation", x + 1100, y, shd_,
                 make_rot(x + 950, y + 450, yaw_pin=self_get("ShadowRelY", "real", x + 800, y + 550, subcat="double")), f"shadow follows the actor again ({label})")
    g.link(prev["then"], m["execute"])
    if keep_cam:
        chain(m, sh)
        return sh
    cam_ = cam_of(x + 300, y + 450, pc_pin)
    a = set_abs_rot(x + 500, y, cam_, "false", f"camera back on the head ({label})")
    cr = make_rot(x + 600, y + 450, self_get("CamRelP", "real", x + 450, y + 550, subcat="double"),
                  self_get("CamRelY", "real", x + 450, y + 650, subcat="double"))
    c = set_rot("K2_SetRelativeRotation", x + 800, y, cam_, cr, "")
    hk = self_set("CamUnhooked", "bool", x + 1400, y, "camera hooked", default="false")
    chain(m, a, c, sh, hk)
    return hk


def blend_args(x, y, seconds, option="HermiteCubic"):
    n = Node(g, BG + "K2Node_MakeStruct", nm("K2Node_MakeStruct"), x, y, "", [f"StructType={ABA}", "bMadeAfterOverridePinRemoval=True"])
    n.pin("BlendTime", "real", subcat="float", extra=f'DefaultValue="{seconds:.6f}",')
    n.pin("BlendOption", "byte", sub="\"/Script/CoreUObject.Enum'/Script/Engine.EAlphaBlendOption'\"", extra=f'DefaultValue="{option}",')
    n.pin("CustomCurve", "object", sub=cls("/Script/Engine.CurveFloat"))
    n.pin("AlphaBlendArgs", "struct", sub=ABA, out=True)
    return n["AlphaBlendArgs"]


def play_rest_eased(x, y, comment, prev, seconds, option="ExpOut"):
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
    POSE_PLAYS.append((n, "rest"))
    g.link(blend_args(x - 250, y + 350, seconds, option), n["BlendIn"])
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


def hands_hidden(x, y, prev_then, pc_pin, hidden, label):
    """SetHiddenInGame on the in-hands mesh and the left-hand item mesh. Returns the last node."""
    nodes = []
    for k, getter in enumerate(("GetWeaponInHandsMeshComponent", "GetSecondaryHandItemMeshComponent")):
        comp = member_pure(OBJC, getter, x + 300 * k, y + 250, pc_pin, [("ReturnValue", "object", dict(sub=SKM, out=True))])["ReturnValue"]
        n = member_call(cls("/Script/Engine.SceneComponent"), "SetHiddenInGame", x + 300 * k, y, comp,
                        f"{'hide' if hidden else 'show'} what the hands hold ({label})" if k == 0 else "",
                        [("NewHidden", "bool", dict(extra=f'DefaultValue="{hidden}",')),
                         ("bPropagateToChildren", "bool", dict(extra='DefaultValue="true",'))])
        nodes.append(n)
    g.link(prev_then, nodes[0]["execute"])
    g.link(nodes[0]["then"], nodes[1]["execute"])
    return nodes[1]



MHT = "\"/Script/CoreUObject.Enum'/Script/Stalker2.EMainHandEquipmentType'\""


def bare_hands(x, y, pc_pin, prev_then, label):
    """StandHand = the hand type if it is a weapon (not None); main hand -> None, no animation. Returns the last node."""
    ht = member_pure(OBJC, "GetMainHandEquipType", x, y + 300, pc_pin, [("ReturnValue", "byte", dict(sub=HANDENUM, out=True))])["ReturnValue"]
    nz = lib_pure(KML, "KismetMathLibrary", "NotEqual_ByteByte", x + 200, y + 300,
                  [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')), ("ReturnValue", "bool", dict(out=True))])
    g.link(ht, nz["A"])
    br = branch(x + 200, y, f"a weapon in hand? ({label})", nz["ReturnValue"])
    g.link(prev_then, br["execute"])
    sv = self_set("StandHand", "byte", x + 450, y, f"weapon to give back on stand-up ({label})", sub=HANDENUM)
    g.link(ht, sv["StandHand"])
    g.link(br["then"], sv["execute"])
    ch = member_call(OBJC, "ChangeMainHandWeapon", x + 700, y, pc_pin, f"bare hands ({label})", [
        ("MainHandEquipment", "byte", dict(sub=MHT, extra='DefaultValue="None",')),
        ("HideWeaponTimeLimit", "real", dict(subcat="float", extra='DefaultValue="0.000000",')),
        ("bShouldSkipAnimation", "bool", dict(extra='DefaultValue="true",'))])
    g.link(sv["then"], ch["execute"])
    sq_ = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), x + 1000, y, "")
    sq_.pin("execute", "exec")
    sq_.pin("then_0", "exec", out=True)
    g.link(ch["then"], sq_["execute"])
    g.link(br["else"], sq_["execute"])
    return {"then": sq_["then_0"]}


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
for k in range(11):
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
hh_t = lib_pure(KML, "KismetMathLibrary", "Add_DoubleDouble", X2 + 3900, Y2 - 1000,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.5",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X2 + 3750, Y2 - 1100,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"], hh_t["A"])
hh0 = self_set("HintHideUntil", "real", X2 + 4050, Y2 - 800, "hide the guitar hint a moment longer", subcat="double")
g.link(hh_t["ReturnValue"], hh0["HintHideUntil"])
chain(save_t, save_y, stp_, sty_, sloc, rst, hide)
g.link(hide["then"], fovr["execute"])   # build 69: no bare-hands switch
chain(fovr, inp, keep_loc, rwt, scp, scy, ssy, sby0, scr2, vh0, hh0, yaw_off)

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


def release(x, y, prev_then, label, need_time):
    """If an item is held: play it on (rate 1) and forget it. need_time: only once the rest pose is fully in."""
    fv = lib_pure(KSL, "KismetSystemLibrary", "IsValid", x, y + 250, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
    g.link(self_get("FrozenMontage", "object", x - 150, y + 250, sub=MONTCLS), fv["Object"])
    cond = fv["ReturnValue"]
    if need_time:
        el = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", x, y + 350,
                      [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                       ("ReturnValue", "real", dict(subcat="double", out=True))])
        g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", x - 200, y + 350,
                        [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"], el["A"])
        g.link(self_get("FrozenT", "real", x - 200, y + 450, subcat="double"), el["B"])
        gt = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", x + 150, y + 350,
                      [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.7",')),
                       ("ReturnValue", "bool", dict(out=True))])
        g.link(el["ReturnValue"], gt["A"])
        held = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", x + 150, y + 450,
                        [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                         ("ReturnValue", "bool", dict(out=True))])
        g.link(self_get("FrozenT", "real", x, y + 500, subcat="double"), held["A"])
        cond = b_and(x + 250, y + 300, cond, b_and(x + 200, y + 400, gt["ReturnValue"], held["ReturnValue"]))
    br = branch(x + 300, y, f"item held? ({label})", cond)
    g.link(prev_then, br["execute"])
    rr = member_call(ANIMI, "Montage_SetPlayRate", x + 600, y, anim, f"let the held item finish ({label})", [
        ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="1.000000",'))])
    rr.pins["Montage"].const = True
    g.link(self_get("FrozenMontage", "object", x + 450, y + 250, sub=MONTCLS), rr["Montage"])
    g.link(br["then"], rr["execute"])
    cl = self_set("FrozenMontage", "object", x + 900, y, "", sub=MONTCLS)
    g.link(rr["then"], cl["execute"])
    sq_ = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), x + 1150, y, "")
    sq_.pin("execute", "exec")
    sq_.pin("then_0", "exec", out=True)
    g.link(cl["then"], sq_["execute"])
    g.link(br["else"], sq_["execute"])
    return sq_["then_0"]


# ---- 3: keep seated ----
X3, Y3 = 1200, 900
g.box("EdGraphNode_Comment_904", X3 - 80, Y3 - 320, 3400, 1300, "Keep seated: no walking, look limits, pose")
c3 = b_and(X3 - 200, Y3 + 200, self_get("SeatedMode", "bool", X3 - 400, Y3 + 160),
           b_not(X3 - 400, Y3 + 260, self_get("Standing", "bool", X3 - 600, Y3 + 260)))
br3 = branch(X3, Y3, "in seated mode?", c3)
g.link(sq["then_3"], br3["execute"])
# build 55: back to DisableMovement (mode None). Build 49's walking mode was for the Sleeping Bag Mod, whose refusal
# turned out to be its location check (step 9 handles the bag); in walking mode the body dropped during item animations.
dis = member_call(CMC, "DisableMovement", X3 + 300, Y3, move, "no walking while seated")
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
cmb = member_pure(ANIMI, "GetCurrentActiveMontage", X3 + 1300, Y3 + 850, anim, [("ReturnValue", "object", dict(sub=MONTCLS, out=True))])["ReturnValue"]
cmbn = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 1450, Y3 + 850,
                [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(cmb, cmbn["Object"])
cmbe = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 1600, Y3 + 850,
                [("SearchIn", "string"), ("Substring", "string", dict(extra='DefaultValue="equip",')),
                 ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(cmbn["ReturnValue"], cmbe["SearchIn"])
cmbu = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 1600, Y3 + 950,
                [("SearchIn", "string"), ("Substring", "string", dict(extra='DefaultValue="_use",')),
                 ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(cmbn["ReturnValue"], cmbu["SearchIn"])
# build 76: hands free OR an item animation (MG_fp_<item>_use) even with the weapon type kept, never a draw / holster
imn = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 1450, Y3 + 1050,
               [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(self_get("ItemMontage", "object", X3 + 1300, Y3 + 1050, sub=MONTCLS), imn["Object"])
imu = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 1600, Y3 + 1050,
               [("SearchIn", "string"), ("Substring", "string", dict(extra='DefaultValue="_use",')),
                ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                ("ReturnValue", "bool", dict(out=True))])
g.link(imn["ReturnValue"], imu["SearchIn"])
q_lh = member_pure(ANIMI, "IsSlotActive", X3 + 1600, Y3 + 1150, anim,
                   [("SlotNodeName", "name", dict(extra='DefaultValue="LeftHand",')), ("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
q_rh = member_pure(ANIMI, "IsSlotActive", X3 + 1600, Y3 + 1250, anim,
                   [("SlotNodeName", "name", dict(extra='DefaultValue="RightHand",')), ("ReturnValue", "bool", dict(out=True))])["ReturnValue"]
hand_slots_item = b_and(X3 + 1800, Y3 + 1200, b_or(X3 + 1750, Y3 + 1200, q_lh, q_rh), b_or(X3 + 1750, Y3 + 1100, cmbu["ReturnValue"], imu["ReturnValue"]))
not_weapon_anim = b_and(X3 + 1800, Y3 + 850, b_or(X3 + 1750, Y3 + 900, h0["ReturnValue"], b_or(X3 + 1700, Y3 + 950, cmbu["ReturnValue"], imu["ReturnValue"])),
                        b_not(X3 + 1750, Y3 + 800, cmbe["ReturnValue"]))
busy = b_or(X3 + 2000, Y3 + 400, b_or(X3 + 1850, Y3 + 340, q_pda, q_bag),
            b_and(X3 + 1900, Y3 + 700, not_weapon_anim,
            b_or(X3 + 1850, Y3 + 500, b_or(X3 + 1800, Y3 + 450, q_act, hand_slots_item), b_or(X3 + 1750, Y3 + 580, q_def, q_up))))
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
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.15",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(irem["ReturnValue"], ilast["A"])
# build 79: every item animation ends by reaching the hands forward to where the weapon would be (its last 0.1-1.1 s,
# measured from the game's sequences: frames where both hands close in on the final pose, zonekit README). Seated
# there is no weapon: that reach was the "hand goes out and forward, then eases into the lap" (and the injector's
# hands going up). The arms now leave the item just before its reach starts.
REACH = [("antirad", 0.25), ("bandage", 0.18), ("beer", 0.18), ("bread", 0.82), ("canned_food", 0.45),
         ("condensed_milk", 1.12), ("energy_drink", 0.28), ("medkit", 0.38), ("pills", 0.31), ("sausage", 0.15),
         ("vodka", 0.38), ("water", 0.18), ("backpack", 0.30)]
rnm = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 700, Y3 + 2400,
               [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(itm, rnm["Object"])
thr = None
known = None
for k, (word, secs) in enumerate(REACH):
    cn = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 900, Y3 + 2400 + 90 * k,
                  [("SearchIn", "string"), ("Substring", "string", dict(extra=f'DefaultValue="{word}",')),
                   ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                   ("ReturnValue", "bool", dict(out=True))])
    g.link(rnm["ReturnValue"], cn["SearchIn"])
    sf = lib_pure(KML, "KismetMathLibrary", "SelectFloat", X3 + 1100, Y3 + 2400 + 90 * k,
                  [("A", "real", dict(subcat="double", extra=f'DefaultValue="{secs}",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.3",')),
                   ("bPickA", "bool", dict(extra='DefaultValue="false",')), ("ReturnValue", "real", dict(subcat="double", out=True))])
    g.link(cn["ReturnValue"], sf["bPickA"])
    known = cn["ReturnValue"] if known is None else b_or(X3 + 1050, Y3 + 2440 + 90 * k, known, cn["ReturnValue"])
    if thr is not None:
        g.link(thr, sf["B"])
    thr = sf["ReturnValue"]
g.link(thr, ilast["B"])
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
sp3t = member_pure(SC_, "GetSocketTransform", X3 + 500, Y3 + 3600, mesh,
                   [("InSocketName", "name", dict(extra='DefaultValue="jnt_spine_03",')),
                    ("TransformSpace", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/Engine.ERelativeTransformSpace'\"", extra='DefaultValue="RTS_World",')),
                    ("ReturnValue", "struct", dict(sub="\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Transform'\"", out=True))])["ReturnValue"]


def hand_local(x, y, sock):
    hl = member_pure(SKM, "GetSocketLocation", x, y + 100, mesh,
                     [("InSocketName", "name", dict(extra=f'DefaultValue="{sock}",')), ("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"]
    it = lib_pure(KML, "KismetMathLibrary", "InverseTransformLocation", x + 200, y,
                  [("T", "struct", dict(sub="\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Transform'\"")), ("Location", "struct", dict(sub=VEC)),
                   ("ReturnValue", "struct", dict(sub=VEC, out=True))])
    g.link(sp3t, it["T"])
    g.link(hl, it["Location"])
    return it["ReturnValue"]


HL = hand_local(X3 + 700, Y3 + 3600, "jnt_l_hand")
HR = hand_local(X3 + 700, Y3 + 3800, "jnt_r_hand")


def speed(x, y, cur, var):
    sb = lib_pure(KML, "KismetMathLibrary", "Subtract_VectorVector", x, y,
                  [("A", "struct", dict(sub=VEC)), ("B", "struct", dict(sub=VEC)), ("ReturnValue", "struct", dict(sub=VEC, out=True))])
    g.link(cur, sb["A"])
    g.link(self_get(var, "struct", x - 150, y + 100, sub=VEC), sb["B"])
    vs = lib_pure(KML, "KismetMathLibrary", "VSize", x + 150, y, [("A", "struct", dict(sub=VEC)), ("ReturnValue", "real", dict(subcat="double", out=True))])
    g.link(sb["ReturnValue"], vs["A"])
    dv = lib_pure(KML, "KismetMathLibrary", "Divide_DoubleDouble", x + 300, y,
                  [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                   ("ReturnValue", "real", dict(subcat="double", out=True))])
    g.link(vs["ReturnValue"], dv["A"])
    mx = lib_pure(KML, "KismetMathLibrary", "FMax", x + 300, y + 100,
                  [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.001",')),
                   ("ReturnValue", "real", dict(subcat="double", out=True))])
    g.link(tick["DeltaSeconds"], mx["A"])
    g.link(mx["ReturnValue"], dv["B"])
    return dv["ReturnValue"]


spd = lib_pure(KML, "KismetMathLibrary", "FMax", X3 + 1500, Y3 + 3700,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(speed(X3 + 1000, Y3 + 3600, HL, "PrevLH"), spd["A"])
g.link(speed(X3 + 1000, Y3 + 3800, HR, "PrevRH"), spd["B"])
fast = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X3 + 1700, Y3 + 3700,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="60.0",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(spd["ReturnValue"], fast["A"])
last1 = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X3 + 1700, Y3 + 3850,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(irem["ReturnValue"], last1["A"])
fast_now = b_and(X3 + 1900, Y3 + 3750, b_and(X3 + 1850, Y3 + 3700, fast["ReturnValue"], last1["ReturnValue"]),
                 b_and(X3 + 1850, Y3 + 3850, b_not(X3 + 1750, Y3 + 3950, known), b_and(X3 + 1750, Y3 + 4050, iok, iplay["ReturnValue"])))
ftp = lib_pure(KML, "KismetMathLibrary", "Add_IntInt", X3 + 1900, Y3 + 3950,
               [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="1",')), ("ReturnValue", "int", dict(out=True))])
g.link(self_get("FastTicks", "int", X3 + 1750, Y3 + 4150), ftp["A"])
ftsel = lib_pure(KML, "KismetMathLibrary", "SelectInt", X3 + 2050, Y3 + 3900,
                 [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="0",')),
                  ("bPickA", "bool", dict(extra='DefaultValue="false",')), ("ReturnValue", "int", dict(out=True))])
g.link(ftp["ReturnValue"], ftsel["A"])
g.link(fast_now, ftsel["bPickA"])
reach_live = lib_pure(KML, "KismetMathLibrary", "GreaterEqual_IntInt", X3 + 1900, Y3 + 4250,
                      [("A", "int", dict(extra='DefaultValue="0",')), ("B", "int", dict(extra='DefaultValue="2",')), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("FastTicks", "int", X3 + 1750, Y3 + 4250), reach_live["A"])
ending = b_and(X3 + 1700, Y3 + 1400, b_and(X3 + 1500, Y3 + 1700, iok, iplay["ReturnValue"]),
               b_or(X3 + 1600, Y3 + 1500, ilast["ReturnValue"], reach_live["ReturnValue"]))   # build 77: no "Out" rule; build 80/82: live reach
# build 60: the drink is stopped by the game (blends out, never reaches its own end): its blend-out showed the
# stance's raised left hand before the rest pose came in. A stopped item montage ends the action too.
stopped = b_and(X3 + 1500, Y3 + 1900, b_and(X3 + 1400, Y3 + 1950, iok, b_not(X3 + 1300, Y3 + 2000, iplay["ReturnValue"])),
                b_not(X3 + 1400, Y3 + 2050, b_or(X3 + 1300, Y3 + 2100, q_pda, q_bag)))
# build 61: one-handed drinks end as the free left hand starts rising back to the weapon grip (probe, build 60: the
# energy drink lifts it 27 cm from 45% of the animation on; that was the "pop", not the montage's blend-out)
nm_it = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 900, Y3 + 2300,
                 [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(itm, nm_it["Object"])
drink = None
for k, word in enumerate(("energy_drink", "water", "vodka", "beer")):
    cn = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 1100, Y3 + 2300 + 100 * k,
                  [("SearchIn", "string"), ("Substring", "string", dict(extra=f'DefaultValue="{word}",')),
                   ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                   ("ReturnValue", "bool", dict(out=True))])
    g.link(nm_it["ReturnValue"], cn["SearchIn"])
    drink = cn["ReturnValue"] if drink is None else b_or(X3 + 1300, Y3 + 2300 + 100 * k, drink, cn["ReturnValue"])
lh_loc = member_pure(SKM, "GetSocketLocation", X3 + 700, Y3 + 2700, mesh,
                     [("InSocketName", "name", dict(extra='DefaultValue="jnt_l_hand",')), ("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"]
lhb = lib_pure(KML, "KismetMathLibrary", "BreakVector", X3 + 900, Y3 + 2700,
               [("InVec", "struct", dict(sub=VEC)), ("X", "real", dict(subcat="double", out=True)), ("Y", "real", dict(subcat="double", out=True)),
                ("Z", "real", dict(subcat="double", out=True))])
g.link(lh_loc, lhb["InVec"])
acb = lib_pure(KML, "KismetMathLibrary", "BreakVector", X3 + 900, Y3 + 2850,
               [("InVec", "struct", dict(sub=VEC)), ("X", "real", dict(subcat="double", out=True)), ("Y", "real", dict(subcat="double", out=True)),
                ("Z", "real", dict(subcat="double", out=True))])
g.link(member_pure(ACTOR, "K2_GetActorLocation", X3 + 700, Y3 + 2850, as_pc, [("ReturnValue", "struct", dict(sub=VEC, out=True))])["ReturnValue"], acb["InVec"])
lhz = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X3 + 1100, Y3 + 2750,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(lhb["Z"], lhz["A"])
g.link(acb["Z"], lhz["B"])
LHZ = lhz["ReturnValue"]
lmin8 = lib_pure(KML, "KismetMathLibrary", "Add_DoubleDouble", X3 + 1100, Y3 + 2900,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="8.0",')),
                  ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(self_get("LHMin", "real", X3 + 900, Y3 + 3000, subcat="double"), lmin8["A"])
rise = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X3 + 1300, Y3 + 2800,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(LHZ, rise["A"])
g.link(lmin8["ReturnValue"], rise["B"])
frac = lib_pure(KML, "KismetMathLibrary", "Divide_DoubleDouble", X3 + 1300, Y3 + 1650,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(ipos["ReturnValue"], frac["A"])
g.link(ilen["ReturnValue"], frac["B"])
late = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X3 + 1500, Y3 + 1650,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.4",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(frac["ReturnValue"], late["A"])
drink_end_pre = b_and(X3 + 1600, Y3 + 2700, b_and(X3 + 1500, Y3 + 2650, b_and(X3 + 1400, Y3 + 2600, iok, iplay["ReturnValue"]), drink),
                      late["ReturnValue"])
drink_end = b_and(X3 + 1600, Y3 + 2500, b_and(X3 + 1500, Y3 + 2450, b_and(X3 + 1400, Y3 + 2400, iok, iplay["ReturnValue"]), drink),
                  b_and(X3 + 1500, Y3 + 2600, late["ReturnValue"], rise["ReturnValue"]))
# build 62: an item we already ended stays ended while its animation still runs (build 61 re-entered free arms every
# other tick after a drink ended early: the body bobbed and the drink jittered)
endm = self_get("EndedMontage", "object", X3 + 1300, Y3 + 3100, sub=MONTCLS)
eact = member_pure(ANIMI, "Montage_IsActive", X3 + 1500, Y3 + 3100, anim, [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "bool", dict(out=True))])
eact.pins["Montage"].const = True
g.link(endm, eact["Montage"])
evld = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X3 + 1500, Y3 + 3200, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(endm, evld["Object"])
still_ended = b_and(X3 + 1700, Y3 + 3150, evld["ReturnValue"], eact["ReturnValue"])
ending = b_or(X3 + 1750, Y3 + 1500, b_or(X3 + 1650, Y3 + 1600, ending, stopped), still_ended)   # build 64: drink_end only locks the left arm
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
cur_n = member_pure(ANIMI, "GetCurrentActiveMontage", X3 + 2100, Y3 - 900, anim, [("ReturnValue", "object", dict(sub=MONTCLS, out=True))])["ReturnValue"]
nv = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X3 + 2300, Y3 - 950, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(cur_n, nv["Object"])
ne1 = lib_pure(KML, "KismetMathLibrary", "NotEqual_ObjectObject", X3 + 2300, Y3 - 850,
               [("A", "object", dict(sub=OBJ)), ("B", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(cur_n, ne1["A"])
g.link(self_get("PoseMontage", "object", X3 + 2100, Y3 - 800, sub=MONTCLS), ne1["B"])
ne2 = lib_pure(KML, "KismetMathLibrary", "NotEqual_ObjectObject", X3 + 2300, Y3 - 750,
               [("A", "object", dict(sub=OBJ)), ("B", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(cur_n, ne2["A"])
g.link(self_get("ItemMontage", "object", X3 + 2100, Y3 - 700, sub=MONTCLS), ne2["B"])
ne3 = lib_pure(KML, "KismetMathLibrary", "NotEqual_ObjectObject", X3 + 2300, Y3 - 650,
               [("A", "object", dict(sub=OBJ)), ("B", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(cur_n, ne3["A"])
g.link(self_get("LHMontage", "object", X3 + 2100, Y3 - 600, sub=MONTCLS), ne3["B"])
brn = branch(X3 + 2500, Y3 - 1000, "newer item animation? (free arms on)",
             b_and(X3 + 2450, Y3 - 800, b_and(X3 + 2400, Y3 - 850, nv["ReturnValue"], b_and(X3 + 2350, Y3 - 900, ne1["ReturnValue"], ne3["ReturnValue"])),
                   b_and(X3 + 2350, Y3 - 700, ne2["ReturnValue"], self_get("PoseAdditive", "bool", X3 + 2200, Y3 - 650))))
lmn = lib_pure(KML, "KismetMathLibrary", "FMin", X3 + 2200, Y3 - 1300,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(LHZ, lmn["A"])
g.link(self_get("LHMin", "real", X3 + 2000, Y3 - 1250, subcat="double"), lmn["B"])
slm = self_set("LHMin", "real", X3 + 2250, Y3 - 1150, "lowest left hand of this item", subcat="double")
g.link(lmn["ReturnValue"], slm["LHMin"])
g.link(lat["then"], slm["execute"])
sft2 = self_set("FastTicks", "int", X3 + 2300, Y3 - 1700, "fast hand ticks in the item's last second")
g.link(ftsel["ReturnValue"], sft2["FastTicks"])
spl = self_set("PrevLH", "struct", X3 + 2550, Y3 - 1700, "left hand (chest space)", sub=VEC)
g.link(HL, spl["PrevLH"])
spr = self_set("PrevRH", "struct", X3 + 2800, Y3 - 1700, "right hand (chest space)", sub=VEC)
g.link(HR, spr["PrevRH"])
g.link(slm["then"], sft2["execute"])
chain(sft2, spl, spr)
g.link(spr["then"], brn["execute"])
sim2 = self_set("ItemMontage", "object", X3 + 2800, Y3 - 1000, "follow the newer item animation", sub=MONTCLS)
g.link(cur_n, sim2["ItemMontage"])
g.link(brn["then"], sim2["execute"])
g.link(sim2["then"], brf["execute"])
g.link(brn["else"], brf["execute"])
cur_m = member_pure(ANIMI, "GetCurrentActiveMontage", X3 + 2450, Y3 - 450, anim, [("ReturnValue", "object", dict(sub=MONTCLS, out=True))])["ReturnValue"]
sim = self_set("ItemMontage", "object", X3 + 2550, Y3 - 350, "the item animation", sub=MONTCLS)
g.link(cur_m, sim["ItemMontage"])
lhr = self_set("LHMin", "real", X3 + 2450, Y3 - 550, "left hand: new item", subcat="double")
g.link(LHZ, lhr["LHMin"])
g.link(release(X3 + 2300, Y3 - 3000, brf["then"], "new item", False), lhr["execute"])
ftz = self_set("FastTicks", "int", X3 + 2600, Y3 - 550, "new item: no fast ticks yet", default="0")
g.link(lhr["then"], ftz["execute"])
g.link(ftz["then"], sim["execute"])
shw_f = hands_hidden(X3 + 2650, Y3 - 650, sim["then"], as_pc, "false", "item starts")
pa1 = self_set("PoseAdditive", "bool", X3 + 3000, Y3 - 200, "pose: free arms", default="true")
# build 67: drinks get their own table (make_sit_drink.py): the left arm stays in the lap instead of lifting
DRINK_TABLES = []   # build 69: off (see make_sit_drink.py); was energy_drink, water, vodka, beer
nm_d = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 3000, Y3 - 2300,
                [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(self_get("ItemMontage", "object", X3 + 2850, Y3 - 2300, sub=MONTCLS), nm_d["Object"])
prev_else = shw_f["then"]
for k, (word, short) in enumerate(DRINK_TABLES):
    cn = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 3200, Y3 - 2300 + 120 * k,
                  [("SearchIn", "string"), ("Substring", "string", dict(extra=f'DefaultValue="{word}",')),
                   ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                   ("ReturnValue", "bool", dict(out=True))])
    g.link(nm_d["ReturnValue"], cn["SearchIn"])
    bd = branch(X3 + 3400, Y3 - 2300 + 250 * k, f"a {word}?", cn["ReturnValue"])
    g.link(prev_else, bd["execute"])
    asset = f"/ImmersiveCampfires/Runtime/AS_ImmCamp_SitDrink_{short}.AS_ImmCamp_SitDrink_{short}"
    pd = play_additive(X3 + 3700, Y3 - 2300 + 250 * k, f"free arms: seated {word}", {"then": bd["then"]}, asset, 0.1)
    sdt = self_set("DrinkTable", "bool", X3 + 4500, Y3 - 2300 + 250 * k, "drink table on", default="true")
    g.link(pd["then"], sdt["execute"])
    g.link(sdt["then"], pa1["execute"])
    prev_else = bd["else"]
paf = play_additive(X3 + 3300, Y3 - 200, "free arms (additive legs)", {"then": prev_else}, None, 0.1)
sdf = self_set("DrinkTable", "bool", X3 + 3650, Y3 - 350, "no drink table", default="false")
g.link(paf["then"], sdf["execute"])
g.link(sdf["then"], pa1["execute"])
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
# build 68: "ended" is about one PLAY of the item: EndedMontage is the montage asset, and the next use of the same
# item plays the same asset, so it read as already ended (second drink / second backpack: no free arms). Forget it
# as soon as that play is over.
eact2 = member_pure(ANIMI, "Montage_IsActive", X3 + 2100, Y3 + 1650, anim, [("Montage", "object", dict(sub=MONT)), ("ReturnValue", "bool", dict(out=True))])
eact2.pins["Montage"].const = True
g.link(self_get("EndedMontage", "object", X3 + 1900, Y3 + 1650, sub=MONTCLS), eact2["Montage"])
evl2 = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X3 + 2100, Y3 + 1750, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("EndedMontage", "object", X3 + 1900, Y3 + 1750, sub=MONTCLS), evl2["Object"])
brE = branch(X3 + 2300, Y3 + 1500, "ended item's play over?", b_and(X3 + 2250, Y3 + 1700, evl2["ReturnValue"], b_not(X3 + 2200, Y3 + 1800, eact2["ReturnValue"])))
eqm = member_pure(ANIMI, "GetCurrentActiveMontage", X3 + 1700, Y3 + 2000, anim, [("ReturnValue", "object", dict(sub=MONTCLS, out=True))])["ReturnValue"]
eqn = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X3 + 1900, Y3 + 2000,
               [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(eqm, eqn["Object"])
eqc = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 2100, Y3 + 2000,
               [("SearchIn", "string"), ("Substring", "string", dict(extra='DefaultValue="equip",')),
                ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                ("ReturnValue", "bool", dict(out=True))])
g.link(eqn["ReturnValue"], eqc["SearchIn"])
sqI = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X3 + 2150, Y3 + 1350, "idle checks")
sqI.pin("execute", "exec")
sqI.pin("then_0", "exec", out=True)
sqI.pin("then_1", "exec", out=True)
g.link(isq["then_0"], sqI["execute"])
# build 74: only the weapon DRAW the game plays after an item; never an unequip (two-handed items like the
# antirad injector first take the left hand off the weapon with an unequip montage; cutting it cancelled the item)
equn = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "Contains", X3 + 2100, Y3 + 2150,
                [("SearchIn", "string"), ("Substring", "string", dict(extra='DefaultValue="unequip",')),
                 ("bUseCase", "bool", dict(extra='DefaultValue="false",')), ("bSearchFromEnd", "bool", dict(extra='DefaultValue="false",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(eqn["ReturnValue"], equn["SearchIn"])
brQ = branch(X3 + 2300, Y3 + 1900, "the game's weapon draw? (not an unequip)", b_and(X3 + 2250, Y3 + 2100, eqc["ReturnValue"], b_not(X3 + 2200, Y3 + 2200, equn["ReturnValue"])))
g.link(sqI["then_0"], brQ["execute"])
cutq = member_call(ANIMI, "StopSlotAnimation", X3 + 2600, Y3 + 1900, anim, "cut it at once (arms resting)", [
    ("InBlendOutTime", "real", dict(subcat="float", extra='DefaultValue="0.050000",')),
    ("SlotNodeName", "name", dict(extra='DefaultValue="MainActionSlot",'))])
g.link(brQ["then"], cutq["execute"])
fzv = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X3 + 1500, Y3 + 3100, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("FrozenMontage", "object", X3 + 1350, Y3 + 3100, sub=MONTCLS), fzv["Object"])
fzneg = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X3 + 1500, Y3 + 3200,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("FrozenT", "real", X3 + 1350, Y3 + 3200, subcat="double"), fzneg["A"])
fzpos = member_pure(ANIMI, "Montage_GetPosition", X3 + 1300, Y3 + 3300, anim,
                    [("Montage", "object", dict(sub=MONTCLS)), ("ReturnValue", "real", dict(subcat="float", out=True))])
fzpos.pins["Montage"].const = True
g.link(self_get("FrozenMontage", "object", X3 + 1150, Y3 + 3300, sub=MONTCLS), fzpos["Montage"])
fzlen = member_pure(ANIMSEQB, "GetPlayLength", X3 + 1300, Y3 + 3400, self_get("FrozenMontage", "object", X3 + 1150, Y3 + 3400, sub=MONTCLS),
                    [("ReturnValue", "real", dict(subcat="float", out=True))])
fzrem = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X3 + 1500, Y3 + 3350,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                  ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(fzlen["ReturnValue"], fzrem["A"])
g.link(fzpos["ReturnValue"], fzrem["B"])
fzend = lib_pure(KML, "KismetMathLibrary", "Less_DoubleDouble", X3 + 1650, Y3 + 3350,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.04",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(fzrem["ReturnValue"], fzend["A"])
brFZ = branch(X3 + 1800, Y3 + 3100, "item in its last frames, not held yet?",
              b_and(X3 + 1750, Y3 + 3250, b_and(X3 + 1700, Y3 + 3200, fzv["ReturnValue"], fzneg["ReturnValue"]), fzend["ReturnValue"]))
g.link(sqI["then_1"], brFZ["execute"])
hold = member_call(ANIMI, "Montage_SetPlayRate", X3 + 2100, Y3 + 3100, anim, "hold the item's final pose (no stance swap under the blend)", [
    ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="0.000100",'))])
hold.pins["Montage"].const = True
g.link(self_get("FrozenMontage", "object", X3 + 1950, Y3 + 3250, sub=MONTCLS), hold["Montage"])
g.link(brFZ["then"], hold["execute"])
hft = self_set("FrozenT", "real", X3 + 2400, Y3 + 3100, "held since", subcat="double")
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X3 + 2250, Y3 + 3250,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"], hft["FrozenT"])
g.link(hold["then"], hft["execute"])
sqFZ = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X3 + 2650, Y3 + 3100, "")
sqFZ.pin("execute", "exec")
sqFZ.pin("then_0", "exec", out=True)
g.link(hft["then"], sqFZ["execute"])
g.link(brFZ["else"], sqFZ["execute"])
g.link(release(X3 + 1900, Y3 + 2400, sqFZ["then_0"], "rest pose in", True), brE["execute"])
g.link(brE["then"], self_set("EndedMontage", "object", X3 + 2600, Y3 + 1500, "forget the ended item", sub=MONTCLS)["execute"])
g.link(isq["then_1"], brr["execute"])
brh = branch(X3 + 2550, Y3 + 200, "coming from free arms?", self_get("PoseAdditive", "bool", X3 + 2450, Y3 + 350))
g.link(brr["then"], brh["execute"])
# build 59: the item's last part slowed to a quarter as the arms settle: the drink's ending lifts the free left hand
# back toward the weapon grip, which showed through the start of the rest blend ("hand pops up, then down")
# build 61: the item is forgotten when the arms go back to rest: a stale ItemMontage that had stopped read as "item
# ending" for the next item (probe, build 60: water from the backpack never got free arms, the rest-pose heal killed it)
sen = self_set("EndedMontage", "object", X3 + 2450, Y3 - 100, "item done: remember it as ended", sub=MONTCLS)
g.link(self_get("ItemMontage", "object", X3 + 2300, Y3 + 50, sub=MONTCLS), sen["EndedMontage"])
sfz = self_set("FrozenMontage", "object", X3 + 2450, Y3 - 400, "item to hold at its end", sub=MONTCLS)
g.link(self_get("ItemMontage", "object", X3 + 2300, Y3 - 250, sub=MONTCLS), sfz["FrozenMontage"])
g.link(brh["then"], sfz["execute"])
frz = member_call(ANIMI, "Montage_SetPlayRate", X3 + 2200, Y3 - 700, anim, "hold the item before its reach", [
    ("Montage", "object", dict(sub=MONTCLS)), ("NewPlayRate", "real", dict(subcat="float", extra='DefaultValue="0.000100",'))])
frz.pins["Montage"].const = True
g.link(self_get("ItemMontage", "object", X3 + 2050, Y3 - 550, sub=MONTCLS), frz["Montage"])
g.link(sfz["then"], frz["execute"])
sft = self_set("FrozenT", "real", X3 + 2700, Y3 - 400, "held since", subcat="double")
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X3 + 2550, Y3 - 250,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"], sft["FrozenT"])
g.link(frz["then"], sft["execute"])
g.link(sft["then"], sen["execute"])
slw = self_set("ItemMontage", "object", X3 + 2600, Y3 - 100, "item done: forget it", sub=MONTCLS)
g.link(sen["then"], slw["execute"])
hid_r = hands_hidden(X3 + 2650, Y3 + 100, slw["then"], as_pc, "true", "item done")
pr = play_rest_eased(X3 + 3300, Y3 + 200, "resting seated pose (arms settle, 0.55 s ease in-out)", hid_r, 0.55, "HermiteCubic")   # build 84: faster (tester)
prh = play_rest(X3 + 2700, Y3 + 450, "resting pose lost: back at once", {"then": brh["else"]}, 0.01)
hpa = self_set("PoseAdditive", "bool", X3 + 3350, Y3 + 450, "pose: resting (heal)", default="false")
hdt = self_set("DrinkTable", "bool", X3 + 3200, Y3 + 600, "no drink table (heal)", default="false")
g.link(prh["then"], hdt["execute"])
g.link(hdt["then"], hpa["execute"])
g.link(hpa["then"], self_set("ItemMontage", "object", X3 + 3600, Y3 + 450, "no item (heal)", sub=MONTCLS)["execute"])
pa2 = self_set("PoseAdditive", "bool", X3 + 3000, Y3 + 200, "pose: resting", default="false")
rwr = member_call(OBJC, "RemoveWeaponFromHands", X3 + 2850, Y3 + 400, as_pc, "weapon out of the hands again")
# build 83: no RemoveWeaponFromHands here. Probe (build 82): on the frame the resting pose started, the hips moved
# 8 cm forward / 4 cm up and both hands ~30 cm forward and up in ONE frame, then eased into the lap: this call swaps
# the game's arm/stance layer under our free-arms legs at once (the "hand reaches out" and the body jump). The
# weapon the game draws after the item is still put away (rwe, "weapon just came out?") once the rest pose is in.
g.link(pr["then"], pa2["execute"])
g.link(pa2["then"], self_set("DrinkTable", "bool", X3 + 3250, Y3 + 300, "no drink table (rest)", default="false")["execute"])

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
dpos = member_pure(ANIMI, "Montage_GetPosition", X4 + 1300, Y4 + 1600, anim,
                   [("Montage", "object", dict(sub=MONTCLS)), ("ReturnValue", "real", dict(subcat="float", out=True))])
dpos.pins["Montage"].const = True
g.link(self_get("ItemMontage", "object", X4 + 1100, Y4 + 1650, sub=MONTCLS), dpos["Montage"])
d30 = kml("Multiply_DoubleDouble", X4 + 1500, Y4 + 1600, [dpin("A"), dpin("B", "30.0"), RET])
g.link(dpos["ReturnValue"], d30["A"])
dfl = kml("Subtract_DoubleDouble", X4 + 1650, Y4 + 1600, [dpin("A"), dpin("B", "0.49"), RET])
g.link(d30["ReturnValue"], dfl["A"])
drow = kml("GridSnap_Float", X4 + 1800, Y4 + 1600, [dpin("Location"), dpin("GridSize", "1.0"), RET])
g.link(dfl["ReturnValue"], drow["Location"])
dcl = kml("FMax", X4 + 1950, Y4 + 1600, [dpin("A"), dpin("B", "0.0"), RET])
g.link(drow["ReturnValue"], dcl["A"])
drs = kml("Multiply_DoubleDouble", X4 + 2100, Y4 + 1600, [dpin("A"), dpin("B", "1.033333333"), RET])
g.link(dcl["ReturnValue"], drs["A"])
dsum = kml("Add_DoubleDouble", X4 + 2250, Y4 + 1600, [dpin("A"), dpin("B"), RET])
g.link(drs["ReturnValue"], dsum["A"])
g.link(mrc["ReturnValue"], dsum["B"])
seld = kml("SelectFloat", X4 + 2400, Y4 + 1500, [dpin("A"), dpin("B"), ("bPickA", "bool", dict(extra='DefaultValue="false",')), RET])
g.link(dsum["ReturnValue"], seld["A"])
g.link(mrc["ReturnValue"], seld["B"])
g.link(self_get("DrinkTable", "bool", X4 + 2250, Y4 + 1750), seld["bPickA"])
g.link(seld["ReturnValue"], selp["A"])
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
              b_and(X4, Y4 - 1250, b_and(X4 - 50, Y4 - 1200, self_get("PoseAdditive", "bool", X4 - 150, Y4 - 1250),
                                         b_not(X4 - 150, Y4 - 1150, self_get("DrinkTable", "bool", X4 - 300, Y4 - 1150))), neq_st["ReturnValue"]))
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
# (step 9, hiding the vanilla guitar hint widgets, removed in build 51: it did not hide the hint)

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
hv4 = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X4 + 1250, Y4 - 700, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("FrozenMontage", "object", X4 + 1100, Y4 - 700, sub=MONTCLS), hv4["Object"])
# build 82: also while an item is held at its end with the camera still on the head (the view must not swing)
g.link(b_and(X4 + 1550, Y4 - 650, b_or(X4 + 1450, Y4 - 700, self_get("PoseAdditive", "bool", X4 + 1400, Y4 - 650), hv4["ReturnValue"]),
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
hv = lib_pure(KSL, "KismetSystemLibrary", "IsValid", X4 + 2700, Y4 - 950, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("FrozenMontage", "object", X4 + 2550, Y4 - 950, sub=MONTCLS), hv["Object"])
brHold = branch(X4 + 2750, Y4 - 850, "item held? (camera stays on the head)",
                b_and(X4 + 2700, Y4 - 1050, hv["ReturnValue"], b_not(X4 + 2600, Y4 - 1050, self_get("CamUnhooked", "bool", X4 + 2450, Y4 - 1050))))
g.link(bral["else"], brHold["execute"])
g.link(brHold["else"], bru["execute"])
ucr = lib_pure(KML, "KismetMathLibrary", "BreakRotator", X4 + 3000, Y4 - 1300,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(member_pure(SC_, "K2_GetComponentRotation", X4 + 2800, Y4 - 1300, cam4, [("ReturnValue", "struct", dict(sub=ROT, out=True))])["ReturnValue"], ucr["InRot"])
uP = self_set("UnhookP", "real", X4 + 3000, Y4 - 1050, "camera pitch as it leaves the head", subcat="double")
g.link(ucr["Pitch"], uP["UnhookP"])
uY = self_set("UnhookY", "real", X4 + 3250, Y4 - 1050, "camera yaw as it leaves the head", subcat="double")
g.link(ucr["Yaw"], uY["UnhookY"])
unow = lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X4 + 3300, Y4 - 1200,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])
uT = self_set("UnhookT", "real", X4 + 3500, Y4 - 1050, "when", subcat="double")
g.link(unow["ReturnValue"], uT["UnhookT"])
g.link(bru["then"], uP["execute"])
chain(uP, uY, uT)
unh = set_abs_rot(X4 + 3200, Y4 - 700, cam4, "true", "camera unhooked from the body (once)")
g.link(uT["then"], unh["execute"])
unf = self_set("CamUnhooked", "bool", X4 + 3500, Y4 - 700, "camera unhooked", default="true")
g.link(unh["then"], unf["execute"])
el4 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X4 + 3300, Y4 - 250,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X4 + 3100, Y4 - 250,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"], el4["A"])
g.link(self_get("UnhookT", "real", X4 + 3100, Y4 - 150, subcat="double"), el4["B"])
fr4 = lib_pure(KML, "KismetMathLibrary", "Divide_DoubleDouble", X4 + 3450, Y4 - 250,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.6",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(el4["ReturnValue"], fr4["A"])
cl4 = lib_pure(KML, "KismetMathLibrary", "FClamp", X4 + 3600, Y4 - 250,
               [("Value", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("Min", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("Max", "real", dict(subcat="double", extra='DefaultValue="1.0",')), ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(fr4["ReturnValue"], cl4["Value"])
ea4 = lib_pure(KML, "KismetMathLibrary", "FInterpEaseInOut", X4 + 3750, Y4 - 250,
               [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                ("Alpha", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                ("Exponent", "real", dict(subcat="double", extra='DefaultValue="2.0",')),
                ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(cl4["ReturnValue"], ea4["Alpha"])
rl4 = lib_pure(KML, "KismetMathLibrary", "RLerp", X4 + 3900, Y4 - 250,
               [("A", "struct", dict(sub=ROT)), ("B", "struct", dict(sub=ROT)),
                ("Alpha", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                ("bShortestPath", "bool", dict(extra='DefaultValue="true",')),
                ("ReturnValue", "struct", dict(sub=ROT, out=True))])
g.link(make_rot(X4 + 3700, Y4 - 100, pitch_pin=self_get("UnhookP", "real", X4 + 3550, Y4 - 50, subcat="double"),
                yaw_pin=self_get("UnhookY", "real", X4 + 3550, Y4 + 50, subcat="double")), rl4["A"])
g.link(make_rot(X4 + 3650, Y4 - 500, pitch_pin=pna["ReturnValue"], yaw_pin=actor_yaw), rl4["B"])
g.link(ea4["ReturnValue"], rl4["Alpha"])
view = set_rot("K2_SetWorldRotation", X4 + 3800, Y4 - 350, cam4, rl4["ReturnValue"], "camera = the view (eased in after leaving the head)")
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
yaw_on = set_yaw_follow(XS + 10800, YS + 1200, sc["AsPC"], "true", "body follows mouse again (up)")
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
show_s = member_call(PC, "EnableInteractions", XS + 1350, YS + 250, sc["AsPC"], "interaction prompts back")
sa_s = stop_additive(XS + 1900, YS + 250, "seated pose off", show_s, other_get(CHAR, "Mesh", "object", XS + 1600, YS + 500, sc["AsPC"], sub=SKM) if False else anim_s)
# build 57: the body does not turn on stand-up: the actor turns to where the body faces (BodyYaw) before the mesh
# follows it again; the camera stays ours (absolute) and eases from the seated view to level / body-forward (tick
# step 10), hooked back when up
cam_st = cam_of(XS + 1500, YS - 1700, sc["AsPC"])
cvr = lib_pure(KML, "KismetMathLibrary", "BreakRotator", XS + 1700, YS - 1700,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(member_pure(SC_, "K2_GetComponentRotation", XS + 1550, YS - 1850, cam_st, [("ReturnValue", "struct", dict(sub=ROT, out=True))])["ReturnValue"], cvr["InRot"])
sp0 = self_set("StandP", "real", XS + 1900, YS - 1500, "view pitch at stand-up", subcat="double")
g.link(cvr["Pitch"], sp0["StandP"])
sy0 = self_set("StandY", "real", XS + 2150, YS - 1500, "view yaw at stand-up", subcat="double")
g.link(cvr["Yaw"], sy0["StandY"])
cu0 = set_abs_rot(XS + 2400, YS - 1500, cam_st, "true", "camera ours while getting up")
cu1 = set_rot("K2_SetWorldRotation", XS + 2700, YS - 1500, cam_st,
              make_rot(XS + 2550, YS - 1700, pitch_pin=self_get("StandP", "real", XS + 2400, YS - 1800, subcat="double"),
                       yaw_pin=self_get("StandY", "real", XS + 2400, YS - 1700, subcat="double")), "view unchanged")
cu2 = self_set("CamUnhooked", "bool", XS + 3000, YS - 1500, "camera unhooked (stand-up)", default="true")
face_s = member_call(ACTOR, "K2_SetActorRotation", XS + 3250, YS - 1500, sc["AsPC"], "actor faces the body", [
    ("NewRotation", "struct", dict(sub=ROT)), ("bTeleportPhysics", "bool", dict(extra='DefaultValue="true",')),
    ("ReturnValue", "bool", dict(out=True))])
g.link(make_rot(XS + 3100, YS - 1700, yaw_pin=self_get("BodyYaw", "real", XS + 2950, YS - 1800, subcat="double")), face_s["NewRotation"])
pcl0 = lib_pure(GS, "GameplayStatics", "GetPlayerController", XS + 3400, YS - 1700,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                 ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
lv0 = member_call(cls("/Script/Engine.Controller"), "SetControlRotation", XS + 3550, YS - 1500, pcl0, "aim: level, body-forward",
                  [("NewRotation", "struct", dict(sub=ROT))])
lv0.pins["NewRotation"].ref = True
lv0.pins["NewRotation"].const = True
g.link(make_rot(XS + 3400, YS - 1850, yaw_pin=self_get("BodyYaw", "real", XS + 3250, YS - 1950, subcat="double")), lv0["NewRotation"])
st0t = self_set("StandT", "real", XS + 2150, YS - 1300, "stand-up start time", subcat="double")
g.link(lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", XS + 2000, YS - 1200,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])["ReturnValue"],
       st0t["StandT"])
chain(st2, sp0, sy0, st0t, cu0, cu1, cu2, face_s, lv0)
rel_s = body_release(XS + 1100, YS - 700, sc["AsPC"], lv0, "stand", keep_cam=True)
# build 54: no walking while the stand-up animation plays (seated mode keeps Walking since build 49); the
# "walking again" SetMovementMode after the delay turns it back on
cmc_s = other_get(CHAR, "CharacterMovement", "object", XS + 1100, YS - 1100, sc["AsPC"], sub=CMC)
stp_s = member_call(cls("/Script/Engine.MovementComponent"), "StopMovementImmediately", XS + 1150, YS - 1300, cmc_s, "stop (stand-up)")
dmv_s = member_call(CMC, "DisableMovement", XS + 1400, YS - 1300, cmc_s, "no walking until up")
pcl = lib_pure(GS, "GameplayStatics", "GetPlayerController", XS + 1550, YS - 1100,
               [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("PlayerIndex", "int", dict(extra='DefaultValue="0",')),
                ("ReturnValue", "object", dict(sub=cls("/Script/Engine.PlayerController"), out=True))])["ReturnValue"]
# build 55: no looking around while getting up (vanilla does not allow it either); reset when up
ilk_s = member_call(cls("/Script/Engine.Controller"), "SetIgnoreLookInput", XS + 1650, YS - 1300, pcl, "no looking until up",
                    [("bNewLookInput", "bool", dict(extra='DefaultValue="true",'))])
g.link(st1["then"], stp_s["execute"])
g.link(stp_s["then"], dmv_s["execute"])
g.link(dmv_s["then"], ilk_s["execute"])
g.link(release(XS + 1800, YS - 2400, ilk_s["then"], "stand-up", False), st2["execute"])
shw_s = hands_hidden(XS + 2600, YS - 700, rel_s["then"], sc["AsPC"], "false", "stand")
chain(shw_s, show_s)
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
rli = member_call(cls("/Script/Engine.Controller"), "ResetIgnoreLookInput", XS + 10950, YS + 450, pcs, "looking back")
# build 56: up = look straight ahead (level, the way the body faces); the seated view pitch otherwise came back
ary = lib_pure(KML, "KismetMathLibrary", "BreakRotator", XS + 10500, YS + 900,
               [("InRot", "struct", dict(sub=ROT)), ("Roll", "real", dict(subcat="float", out=True)),
                ("Pitch", "real", dict(subcat="float", out=True)), ("Yaw", "real", dict(subcat="float", out=True))])
g.link(member_pure(ACTOR, "K2_GetActorRotation", XS + 10300, YS + 900, sc["AsPC"], [("ReturnValue", "struct", dict(sub=ROT, out=True))])["ReturnValue"], ary["InRot"])
cam_e = cam_of(XS + 10300, YS + 1500, sc["AsPC"])
he1 = set_abs_rot(XS + 10450, YS + 1300, cam_e, "false", "camera back on the head (up)")
he2 = set_rot("K2_SetRelativeRotation", XS + 10600, YS + 1300, cam_e,
              make_rot(XS + 10450, YS + 1500, self_get("CamRelP", "real", XS + 10300, YS + 1600, subcat="double"),
                       self_get("CamRelY", "real", XS + 10300, YS + 1700, subcat="double")), "")
he3 = self_set("CamUnhooked", "bool", XS + 10750, YS + 1300, "camera hooked (up)", default="false")
lvl = member_call(cls("/Script/Engine.Controller"), "SetControlRotation", XS + 10750, YS + 650, pcs, "look straight ahead",
                  [("NewRotation", "struct", dict(sub=ROT))])
lvl.pins["NewRotation"].ref = True
lvl.pins["NewRotation"].const = True
g.link(make_rot(XS + 10650, YS + 900, yaw_pin=ary["Yaw"]), lvl["NewRotation"])
neSH = lib_pure(KML, "KismetMathLibrary", "NotEqual_ByteByte", XS + 10800, YS + 800,
                [("A", "byte", dict(extra='DefaultValue="0",')), ("B", "byte", dict(extra='DefaultValue="0",')), ("ReturnValue", "bool", dict(out=True))])
g.link(self_get("StandHand", "byte", XS + 10650, YS + 850, sub=HANDENUM), neSH["A"])
brSH = branch(XS + 10950, YS + 650, "a weapon to give back?", neSH["ReturnValue"])
chw = member_call(OBJC, "ChangeMainHandWeapon", XS + 11200, YS + 650, sc["AsPC"], "the weapon back (stand-up)", [
    ("MainHandEquipment", "byte", dict(sub=MHT)),
    ("HideWeaponTimeLimit", "real", dict(subcat="float", extra='DefaultValue="0.000000",')),
    ("bShouldSkipAnimation", "bool", dict(extra='DefaultValue="false",'))])
b2e = Node(g, BG + "K2Node_CastByteToEnum", nm("K2Node_CastByteToEnum"), XS + 11100, YS + 950, "",
           ["Enum=\"/Script/CoreUObject.Enum'/Script/Stalker2.EMainHandEquipmentType'\"", "bSafe=True"])
b2e.pin("Byte", "byte")
b2e.pin("ReturnValue", "byte", sub=MHT, out=True)
g.link(self_get("StandHand", "byte", XS + 10950, YS + 950), b2e["Byte"])
g.link(b2e["ReturnValue"], chw["MainHandEquipment"])
clr = self_set("StandHand", "byte", XS + 11450, YS + 650, "", default="0", sub=HANDENUM)
g.link(brSH["then"], chw["execute"])
g.link(chw["then"], clr["execute"])
sqSH = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), XS + 11700, YS + 650, "")
sqSH.pin("execute", "exec")
sqSH.pin("then_0", "exec", out=True)
g.link(clr["then"], sqSH["execute"])
g.link(brSH["else"], eq_s["execute"])
g.link(eq_s["then"], sqSH["execute"])
# build 85: stood up for the Sleeping Bag Mod -> stay unarmed: the weapon the game put back when the backpack
# closed is taken out of the hands, the hidden hand meshes are shown again (empty), no weapon back
brBag = branch(XS + 10300, YS - 800, "stood up for the sleeping bag? (stay unarmed)", self_get("BagPending", "bool", XS + 10150, YS - 650))
g.link(lastr["then"], brBag["execute"])
g.link(brBag["else"], brSH["execute"])
rwz = member_call(OBJC, "RemoveWeaponFromHands", XS + 10600, YS - 800, sc["AsPC"], "no weapon (sleeping bag)")
g.link(brBag["then"], rwz["execute"])
g.link(hands_hidden(XS + 10900, YS - 800, rwz["then"], sc["AsPC"], "false", "up for the bag")["then"], clr["execute"])
g.link(sqSH["then_0"], lvl["execute"])
chain(lvl, he1, he2, he3, yaw_on, rli, rmi)

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
chain(g1, g2, gp0, gt0, gm, yaw_g)   # build 46: no EnableInteractions (its "Play guitar" hint flashed)
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
shw_g = hands_hidden(XG + 6000, YG - 400, rel_g["then"], gc["AsPC"], "false", "guitar")
g.link(shw_g["then"], loc_g["execute"])
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

# ---- 9 (build 53): Sleeping Bag Mod. Its Config actor (/Sleeping_Bag/Config) reads the bag-use RTPC on tick and
#      allows sleep only in shelters or within 8 m of the campfires on its own list (most campfires are not on it), so
#      at our campfires it refused: a sleepy groan, no popup. We take the use first (its tick waits for ours), stand up,
#      then call its "On Widget Init" (the hours popup; confirm = lay down and sleep). No-op without the mod. ----
X9, Y9 = 400, 12600
g.box("EdGraphNode_Comment_914", X9 - 80, Y9 - 300, 7600, 3100, "Sleeping Bag Mod: the bag used while seated = stand up, then its sleep popup")
sq9 = Node(g, BG + "K2Node_ExecutionSequence", nm("K2Node_ExecutionSequence"), X9, Y9, "sleeping bag steps")
sq9.pin("execute", "exec")
for k in range(5):
    sq9.pin(f"then_{k}", "exec", out=True)
g.link(sq["then_9"], sq9["execute"])
AKRTPC = cls("/Script/AkAudio.AkRtpc")
AKGS = cls("/Script/AkAudio.AkGameplayStatics")
SCR = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.SoftClassPath'\""


def is_valid(x, y, obj_pin):
    n = lib_pure(KSL, "KismetSystemLibrary", "IsValid", x, y, [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "bool", dict(out=True))])
    g.link(obj_pin, n["Object"])
    return n["ReturnValue"]


def soft_path(x, y, path):
    mk = lib_pure(KSL, "KismetSystemLibrary", "MakeSoftObjectPath", x, y,
                  [("PathString", "string", dict(extra=f'DefaultValue="{path}",')), ("ReturnValue", "struct", dict(sub=SOP, out=True))])
    return mk["ReturnValue"]


def lib_call(lib, libname, member, x, y, comment, pins, default_obj):
    n = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
                       [f"FunctionReference=(MemberParent={lib},MemberName=\"{member}\")"]))
    n.pin("self", "object", sub=lib, hidden=True, extra=f'DefaultObject="{default_obj}",')
    for p_ in pins:
        n.pin(*p_[:2], **p_[2])
    return n


# 9a: find the mod's Config actor once per sit (class and RTPC are already loaded when the mod runs)
cfg_ok = is_valid(X9 + 100, Y9 - 100, self_get("SBMUse", "object", X9 - 100, Y9 - 100, sub=AKRTPC))   # build 73: RTPC found = done
# build 70: the look-up (and the tick-order change it makes on the mod's actor) no longer happens on the first
# seated tick: three crashes (builds 58, 59, 69), each on the first sit after loading a save, in a Blueprint call
# made at that moment. Now: while walking around, from 10 s after the world starts, at most every 10 s.
now9 = lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X9 - 300, Y9 + 400,
                [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])
since9 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X9 - 100, Y9 + 400,
                  [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                   ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now9["ReturnValue"], since9["A"])
g.link(self_get("SBMLastTry", "real", X9 - 300, Y9 + 500, subcat="double"), since9["B"])
late9 = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X9 + 100, Y9 + 400,
                 [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="10.0",')),
                  ("ReturnValue", "bool", dict(out=True))])
g.link(since9["ReturnValue"], late9["A"])
c9a = b_and(X9 + 300, Y9 + 250, b_and(X9 + 200, Y9 + 150,
                                      b_not(X9, Y9 + 150, b_or(X9 - 100, Y9 + 150, self_get("SeatedMode", "bool", X9 - 300, Y9 + 120),
                                                               b_or(X9 - 200, Y9 + 200, self_get("VanillaHold", "bool", X9 - 400, Y9 + 180), self_get("Standing", "bool", X9 - 400, Y9 + 240)))),
                                      late9["ReturnValue"]),
            b_not(X9 + 200, Y9 + 300, cfg_ok))
br9a = branch(X9 + 500, Y9, "walking around, mod not found yet, 10 s since the last try?", c9a)
g.link(sq9["then_0"], br9a["execute"])
t9 = self_set("SBMLastTry", "real", X9 + 800, Y9, "tried now", subcat="double")
g.link(now9["ReturnValue"], t9["SBMLastTry"])
g.link(br9a["then"], t9["execute"])
cvo = lib_pure(KSL, "KismetSystemLibrary", "Conv_SoftObjPathToSoftObjRef", X9 + 2800, Y9 + 300,
               [("SoftObjectPath", "struct", dict(sub=SOP)), ("ReturnValue", "softobject", dict(sub=OBJ, out=True))])
cvo.pins["SoftObjectPath"].ref = True
cvo.pins["SoftObjectPath"].const = True
g.link(soft_path(X9 + 2550, Y9 + 300, "/Sleeping_Bag/RTPC/SBM_RTPC_Use.SBM_RTPC_Use"), cvo["SoftObjectPath"])
ldr = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), X9 + 2900, Y9, "its bag-use RTPC",
                     [f"FunctionReference=(MemberParent={KSL},MemberName=\"LoadAsset_Blocking\")"]))
ldr.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
ldr.pin("Asset", "softobject", sub=OBJ)
ldr.pin("ReturnValue", "object", sub=OBJ, out=True)
g.link(cvo["ReturnValue"], ldr["Asset"])
g.link(t9["then"], ldr["execute"])
rcast = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), X9 + 3250, Y9, "an RTPC?", [f"TargetType={AKRTPC}"]))
rcast.pin("CastFailed", "exec", out=True)
rcast.pin("Object", "object", sub=OBJ)
rcast.pin("AsAkRtpc", "object", sub=AKRTPC, out=True)
rcast.pin("bSuccess", "bool", out=True)
g.link(ldr["ReturnValue"], rcast["Object"])
g.link(ldr["then"], rcast["execute"])
suse = self_set("SBMUse", "object", X9 + 3600, Y9, "the bag-use RTPC", sub=AKRTPC)
g.link(rcast["AsAkRtpc"], suse["SBMUse"])
g.link(rcast["then"], suse["execute"])

# 9b: not seated: look up again next sit (if the mod was not there yet)
br9b = branch(X9 + 500, Y9 + 600, "not seated?", b_and(X9 + 300, Y9 + 800, b_not(X9 + 100, Y9 + 800, self_get("SeatedMode", "bool", X9 - 100, Y9 + 800)),
                                                      self_get("SBMTried", "bool", X9 + 100, Y9 + 900)))
g.link(sq9["then_1"], br9b["execute"])
t9b = self_set("SBMTried", "bool", X9 + 800, Y9 + 600, "look up again next sit", default="false")
g.link(br9b["then"], t9b["execute"])

# 9c: seated and the bag just used: take the use, stand up
use_ok = is_valid(X9 + 200, Y9 + 1400, self_get("SBMUse", "object", X9, Y9 + 1400, sub=AKRTPC))
c9c = b_and(X9 + 400, Y9 + 1300, b_and(X9 + 300, Y9 + 1200, self_get("SeatedMode", "bool", X9 + 100, Y9 + 1200),
                                       b_not(X9 + 100, Y9 + 1280, self_get("Standing", "bool", X9 - 100, Y9 + 1280))), use_ok)
br9c = branch(X9 + 500, Y9 + 1100, "seated, mod running?", c9c)
g.link(sq9["then_2"], br9c["execute"])
grt = lib_call(AKGS, "AkGameplayStatics", "GetRTPCValue", X9 + 800, Y9 + 1100, "bag used? (its RTPC on the player)", [
    ("RTPCValue", "object", dict(sub=AKRTPC)), ("PlayingID", "int", dict(extra='DefaultValue="0",')),
    ("InputValueType", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/AkAudio.ERTPCValueType'\"", extra='DefaultValue="GameObject",')),
    ("Value", "real", dict(subcat="float", out=True)),
    ("OutputValueType", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/AkAudio.ERTPCValueType'\"", out=True)),
    ("Actor", "object", dict(sub=ACTOR))], "/Script/AkAudio.Default__AkGameplayStatics")
grt.pins["RTPCValue"].const = True
g.link(self_get("SBMUse", "object", X9 + 650, Y9 + 1350, sub=AKRTPC), grt["RTPCValue"])
g.link(as_pc, grt["Actor"])
g.link(br9c["then"], grt["execute"])
used = lib_pure(KML, "KismetMathLibrary", "Greater_DoubleDouble", X9 + 1150, Y9 + 1350,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.5",')),
                 ("ReturnValue", "bool", dict(out=True))])
g.link(grt["Value"], used["A"])
br9u = branch(X9 + 1300, Y9 + 1100, "bag used?", used["ReturnValue"])
g.link(grt["then"], br9u["execute"])
rrt = lib_call(AKGS, "AkGameplayStatics", "ResetRTPCValue", X9 + 1600, Y9 + 1100, "take the use (the mod never sees it)", [
    ("RTPCValue", "object", dict(sub=AKRTPC)), ("InterpolationTimeMs", "int", dict(extra='DefaultValue="0",')), ("Actor", "object", dict(sub=ACTOR))], "/Script/AkAudio.Default__AkGameplayStatics")
rrt.pins["RTPCValue"].const = True
g.link(self_get("SBMUse", "object", X9 + 1450, Y9 + 1350, sub=AKRTPC), rrt["RTPCValue"])
g.link(as_pc, rrt["Actor"])
g.link(br9u["then"], rrt["execute"])
bpc = member_call(PC, "OnBackpackUseEnded", X9 + 1850, Y9 + 900, as_pc, "close the backpack")
g.link(rrt["then"], bpc["execute"])
bp9 = self_set("BagPending", "bool", X9 + 1950, Y9 + 1100, "sleep popup after standing up", default="true")
rwb = member_call(OBJC, "RemoveWeaponFromHands", X9 + 1950, Y9 + 900, as_pc, "no weapon (sleeping bag)")
g.link(bpc["then"], rwb["execute"])
g.link(rwb["then"], bp9["execute"])
g.link(bp9["then"], sc["execute"])     # into "Stand up" (same as pressing W)

# 9d: stood up: open the mod's sleep popup
c9d = b_and(X9 + 400, Y9 + 1900, b_and(X9 + 300, Y9 + 1800, self_get("BagPending", "bool", X9 + 100, Y9 + 1800),
                                       b_not(X9 + 100, Y9 + 1880, self_get("SeatedMode", "bool", X9 - 100, Y9 + 1880))),
            b_not(X9 + 300, Y9 + 1960, self_get("Standing", "bool", X9 + 100, Y9 + 1960)))
br9d = branch(X9 + 500, Y9 + 1700, "stood up for the bag?", c9d)
g.link(sq9["then_3"], br9d["execute"])
bp9d = self_set("BagPending", "bool", X9 + 800, Y9 + 1700, "bag handled", default="false")
g.link(br9d["then"], bp9d["execute"])
gaa = lib_call(GS, "GameplayStatics", "GetAllActorsOfClass", X9 + 1050, Y9 + 1700, "every actor (once per bag use)",
               [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)),
                ("ActorClass", "class", dict(sub=ACTOR, extra=f'DefaultObject="/Script/Engine.Actor",')),
                ("OutActors", "object", dict(sub=ACTOR, out=True))], "/Script/Engine.Default__GameplayStatics")
gaa.pins["ActorClass"].wrapper = True
gaa.pins["OutActors"].container = "Array"
g.link(bp9d["then"], gaa["execute"])
fe9 = Node(g, BG + "K2Node_MacroInstance", nm("K2Node_MacroInstance"), X9 + 1400, Y9 + 1700, "find the Sleeping Bag Mod's Config",
           ["MacroGraphReference=(MacroGraph=\"/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'\","
            "GraphBlueprint=\"/Script/Engine.Blueprint'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros'\","
            "GraphGuid=99DBFD5540A796041F72A5A9DA655026)"])
fe9.pin("Exec", "exec")
fe9.pin("Array", "object", sub=ACTOR)
fe9.pins["Array"].container = "Array"
fe9.pin("LoopBody", "exec", out=True)
fe9.pin("Array Element", "object", sub=ACTOR, out=True)
fe9.pin("Array Index", "int", out=True)
fe9.pin("Completed", "exec", out=True)
g.link(gaa["OutActors"], fe9["Array"])
g.link(gaa["then"], fe9["Exec"])
opn = lib_pure(KSL, "KismetSystemLibrary", "GetObjectName", X9 + 1700, Y9 + 2050,
               [("Object", "object", dict(sub=OBJ)), ("ReturnValue", "string", dict(out=True))])
g.link(fe9["Array Element"], opn["Object"])
ocn = lib_pure(cls("/Script/Engine.KismetStringLibrary"), "KismetStringLibrary", "StartsWith", X9 + 1900, Y9 + 2050,
               [("SourceString", "string"), ("InPrefix", "string", dict(extra='DefaultValue="Config_C",')),
                ("SearchCase", "byte", dict(sub="\"/Script/CoreUObject.Enum'/Script/CoreUObject.ESearchCase'\"", extra='DefaultValue="IgnoreCase",')),
                ("ReturnValue", "bool", dict(out=True))])
g.link(opn["ReturnValue"], ocn["SourceString"])   # the Sleeping Bag Mod's actor: Config_C_<n>
br9v = branch(X9 + 1750, Y9 + 1700, "the mod's Config, not handled yet?",
              b_and(X9 + 1700, Y9 + 1900, ocn["ReturnValue"], b_not(X9 + 1600, Y9 + 1950, self_get("SBMDone", "bool", X9 + 1450, Y9 + 1950))))
g.link(fe9["LoopBody"], br9v["execute"])
sdn = self_set("SBMDone", "bool", X9 + 2000, Y9 + 1500, "popup asked for", default="true")
g.link(br9v["then"], sdn["execute"])
tmr = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), X9 + 2250, Y9 + 1700, "its sleep popup (On Widget Init)",
           [f"FunctionReference=(MemberParent={KSL},MemberName=\"K2_SetTimer\")"])
exec_pins(tmr)
tmr.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
tmr.pin("Object", "object", sub=OBJ)
tmr.pin("FunctionName", "string", extra='DefaultValue="On Widget Init",')
tmr.pin("Time", "real", subcat="float", extra='DefaultValue="0.200000",')
tmr.pin("bLooping", "bool", extra='DefaultValue="false",')
tmr.pin("ReturnValue", "struct", sub="\"/Script/CoreUObject.ScriptStruct'/Script/Engine.TimerHandle'\"", out=True)
g.link(fe9["Array Element"], tmr["Object"])
g.link(sdn["then"], tmr["execute"])
g.link(fe9["Completed"], self_set("SBMDone", "bool", X9 + 1750, Y9 + 2200, "ready for the next bag use", default="false")["execute"])

# 9e (build 85): getting up for the bag: hands hold nothing visible (shown again when up)
br9e = branch(X9 + 500, Y9 + 2400, "getting up for the bag?", b_and(X9 + 300, Y9 + 2550, self_get("BagPending", "bool", X9 + 100, Y9 + 2500),
                                                                   self_get("Standing", "bool", X9 + 100, Y9 + 2600)))
g.link(sq9["then_4"], br9e["execute"])
hands_hidden(X9 + 800, Y9 + 2400, br9e["then"], as_pc, "true", "getting up for the bag")

# ---- 10 (build 57): getting up: the camera (ours) eases from the seated view to level, body-forward ----
X10, Y10 = 400, 15600
g.box("EdGraphNode_Comment_915", X10 - 80, Y10 - 300, 2600, 1000, "Getting up: view eases to level, body-forward")
br10 = branch(X10 + 300, Y10, "getting up, camera ours?", b_and(X10 + 100, Y10 + 250, self_get("Standing", "bool", X10 - 100, Y10 + 200),
                                                                self_get("CamUnhooked", "bool", X10 - 100, Y10 + 300)))
g.link(sq["then_10"], br10["execute"])
# build 58: eased over the whole stand-up (STAND_EASE s, ease in-out) from the view at the key press; build 57's
# RInterpTo reached forward in about a second
STAND_EASE = 3.5
now10 = lib_pure(KSL, "KismetSystemLibrary", "GetGameTimeInSeconds", X10 + 100, Y10 + 700,
                 [("WorldContextObject", "object", dict(sub=OBJ, hidden=True)), ("ReturnValue", "real", dict(subcat="double", out=True))])
el10 = lib_pure(KML, "KismetMathLibrary", "Subtract_DoubleDouble", X10 + 300, Y10 + 700,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(now10["ReturnValue"], el10["A"])
g.link(self_get("StandT", "real", X10 + 100, Y10 + 800, subcat="double"), el10["B"])
fr10 = lib_pure(KML, "KismetMathLibrary", "Divide_DoubleDouble", X10 + 500, Y10 + 700,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra=f'DefaultValue="{STAND_EASE}",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(el10["ReturnValue"], fr10["A"])
cl10 = lib_pure(KML, "KismetMathLibrary", "FClamp", X10 + 700, Y10 + 700,
                [("Value", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("Min", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("Max", "real", dict(subcat="double", extra='DefaultValue="1.0",')), ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(fr10["ReturnValue"], cl10["Value"])
ea10 = lib_pure(KML, "KismetMathLibrary", "FInterpEaseInOut", X10 + 900, Y10 + 700,
                [("A", "real", dict(subcat="double", extra='DefaultValue="0.0",')), ("B", "real", dict(subcat="double", extra='DefaultValue="1.0",')),
                 ("Alpha", "real", dict(subcat="double", extra='DefaultValue="0.0",')),
                 ("Exponent", "real", dict(subcat="double", extra='DefaultValue="2.0",')),
                 ("ReturnValue", "real", dict(subcat="double", out=True))])
g.link(cl10["ReturnValue"], ea10["Alpha"])
rl10 = lib_pure(KML, "KismetMathLibrary", "RLerp", X10 + 1100, Y10 + 300,
                [("A", "struct", dict(sub=ROT)), ("B", "struct", dict(sub=ROT)),
                 ("Alpha", "real", dict(subcat="float", extra='DefaultValue="0.0",')),
                 ("bShortestPath", "bool", dict(extra='DefaultValue="true",')),
                 ("ReturnValue", "struct", dict(sub=ROT, out=True))])
g.link(make_rot(X10 + 300, Y10 + 300, pitch_pin=self_get("StandP", "real", X10 + 150, Y10 + 300, subcat="double"),
                yaw_pin=self_get("StandY", "real", X10 + 150, Y10 + 400, subcat="double")), rl10["A"])
g.link(make_rot(X10 + 300, Y10 + 500, yaw_pin=self_get("BodyYaw", "real", X10 + 150, Y10 + 550, subcat="double")), rl10["B"])
g.link(ea10["ReturnValue"], rl10["Alpha"])
c10 = set_rot("K2_SetWorldRotation", X10 + 1400, Y10, cam_of(X10 + 1250, Y10 + 450, as_pc), rl10["ReturnValue"], "camera = eased view")
g.link(br10["then"], c10["execute"])

# build 71: every pose table starts on the frame for the current view (it started on frame 0 = view yaw -75 deg,
# pitch -60 until the next tick set it: one wrong frame blended in = the left hand jumping ~25 cm when the arms
# went back to the lap after a drink / the backpack)
for node, kind in POSE_PLAYS:
    g.link(rpos["ReturnValue"] if kind == "rest" else mrc["ReturnValue"], node["InTimeToStartMontageAt"])

write(sys.argv[1], g.text())
print("ok", len(g.nodes), "nodes")
