"""Generates the AnimGraph of Runtime/ABP_ImmCampSeatedLegs (post-process anim BP) as paste text.

v2 (build 15), installed once per world shortly after load and never swapped again:
  Input Pose -> Save Cached Pose "GameInput"
  Use Cached "GameInput" -> LBB blend mask lower_body_blend_mask <- sit idle
                         -> LBB branch jnt_camera <- sit idle            = seated pose
  Use Cached "GameInput" -> Linked Anim Graph, tag "Previous" (default class ABP_ImmCampPassThrough;
                            the actor links ImmersiveDialogue's class here at install) = previous layer
  Blend Poses by bool (Active Value bound to the Seated variable): True = seated pose, False = previous
  -> Output Pose (wired by hand), Input Pose added by hand (LinkedInputPose nodes don't paste).
Node templates are lifted from the game's own AnimBP_Player / AnimBP_player_bh and ImmersiveDialogue's
ABP_ImmDlgBody exports (t3d_lift.py). The Linked Anim Graph node is written from engine knowledge.
Usage: python gen_abp_seated_legs.py <scratch dir with the exports> <out.txt>
"""
import sys, re
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from t3d_lift import Lifted, link
from bp_t3d import G, write, T, F

D = sys.argv[1]
SIT = "/Script/Engine.AnimSequence'/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/AS_fp_ca_gd_bonfire_sit_idle.AS_fp_ca_gd_bonfire_sit_idle'"
PASS = "/Script/Engine.AnimBlueprintGeneratedClass'/ImmersiveCampfires/Runtime/ABP_ImmCampPassThrough.ABP_ImmCampPassThrough_C'"
CACHE = "GameInput"
POSE = "\"/Script/CoreUObject.ScriptStruct'/Script/Engine.PoseLink'\""


def no_bindings(l):
    return "" if l.strip().startswith("PropertyBindings=") else l


def seq(l):
    return re.sub(r'Node=\(Sequence="[^"]*"\)', f'Node=(Sequence="{SIT}")', no_bindings(l))


def cam_filter(l):
    return no_bindings(l).replace('BoneName="VB jnt_camera",BlendDepth=1', 'BoneName="jnt_camera",BlendDepth=0')


def save_cache(l):
    return re.sub(r'CacheName="[^"]*"', f'CacheName="{CACHE}"', no_bindings(l))


def use_cache(l):
    l = no_bindings(l)
    l = re.sub(r'SaveCachedPoseNode="[^"]*"',
               "SaveCachedPoseNode=\"/Script/AnimGraph.AnimGraphNode_SaveCachedPose'ABP_ImmCampSeatedLegs:AnimGraph.AnimGraphNode_SaveCachedPose_900'\"", l)
    return re.sub(r'NameOfCache="[^"]*"', f'NameOfCache="{CACHE}"', l)


def bool_seated(l):
    if l.strip().startswith("PropertyBindings="):
        l = re.sub(r'PathAsText="[^"]*"', 'PathAsText="Seated"', l)
        l = re.sub(r'PropertyPath=\([^)]*\)', 'PropertyPath=("Seated")', l)
    return l


IMM = f"{D}/immdlg_body.t3d"
PLY = f"{D}/AnimBP_Player.t3d"
BH = f"{D}/AnimBP_player_bh.t3d"
save = Lifted(IMM, "ABP_ImmDlgBody.ABP_ImmDlgBody:AnimGraph.AnimGraphNode_SaveCachedPose_0", "AnimGraphNode_SaveCachedPose_900", -700, 0, save_cache)
use1 = Lifted(IMM, "ABP_ImmDlgBody.ABP_ImmDlgBody:AnimGraph.AnimGraphNode_UseCachedPose_1", "AnimGraphNode_UseCachedPose_900", -400, 0, use_cache)
use2 = Lifted(IMM, "ABP_ImmDlgBody.ABP_ImmDlgBody:AnimGraph.AnimGraphNode_UseCachedPose_1", "AnimGraphNode_UseCachedPose_901", -400, 500, use_cache)
sit1 = Lifted(PLY, "AnimBP_Player.AnimBP_Player:AnimGraph.AnimGraphNode_SequencePlayer_0", "AnimGraphNode_SequencePlayer_900", -400, 150, seq)
sit2 = Lifted(PLY, "AnimBP_Player.AnimBP_Player:AnimGraph.AnimGraphNode_SequencePlayer_0", "AnimGraphNode_SequencePlayer_901", 0, 250, seq)
legs = Lifted(PLY, "AnimBP_Player.AnimBP_Player:AnimGraph.AnimGraphNode_StateMachine_3.Moving.AnimStateNode_1.Run.AnimGraphNode_LayeredBoneBlend_3",
              "AnimGraphNode_LayeredBoneBlend_900", 0, 0, no_bindings)
cam = Lifted(BH, "AnimBP_player_bh.AnimBP_player_bh:WeaponLayer.AnimGraphNode_LayeredBoneBlend_2",
             "AnimGraphNode_LayeredBoneBlend_901", 350, 0, cam_filter)
blend = Lifted(IMM, "ABP_ImmDlgBody.ABP_ImmDlgBody:AnimGraph.AnimGraphNode_BlendListByBool_9", "AnimGraphNode_BlendListByBool_900", 750, 200, bool_seated)


class Linked:
    """Linked Anim Graph node (no template in the exports)."""
    name = "AnimGraphNode_LinkedAnimGraph_900"

    def __init__(self):
        self.pin_ids = {"InPose": G(), "Pose": G()}
        self.links = {}

    def pin_line(self, name, out):
        l = ""
        if name in self.links:
            l = "LinkedTo=(" + "".join(f"{n.name} {n.pin_ids[p]}," for n, p in self.links[name]) + "),"
        d = 'Direction="EGPD_Output",' if out else ""
        return (f'   CustomProperties Pin (PinId={self.pin_ids[name]},PinName="{name}",{d}PinType.PinCategory="struct",'
                f'PinType.PinSubCategory="",PinType.PinSubCategoryObject={POSE},{T}{l}' + F % ("False", "False"))

    def text(self):
        return [f'Begin Object Class=/Script/AnimGraph.AnimGraphNode_LinkedAnimGraph Name="{self.name}"',
                f'   Node=(Tag="Previous",InstanceClass="{PASS}")',
                "   NodePosX=0", "   NodePosY=500", f"   NodeGuid={G()}",
                '   bCommentBubbleVisible=True', '   NodeComment="previous layer (ImmersiveDialogue) chained here"',
                self.pin_line("InPose", False), self.pin_line("Pose", True), "End Object"]


lag = Linked()
link(save, "Pose", save, "Pose") if False else None
link(use1, "Pose", legs, "BasePose")
link(sit1, "Pose", legs, "BlendPoses_0")
link(legs, "Pose", cam, "BasePose")
link(sit2, "Pose", cam, "BlendPoses_0")
link(cam, "Pose", blend, "BlendPose_0")
link(use2, "Pose", lag, "InPose")
link(lag, "Pose", blend, "BlendPose_1")

out = []
for n in (save, use1, use2, sit1, sit2, legs, cam, lag, blend):
    out += [l for l in n.text() if l != ""]
out += ['Begin Object Class=/Script/UnrealEd.EdGraphNode_Comment Name="EdGraphNode_Comment_900"',
        "   NodePosX=-800", "   NodePosY=-150", "   NodeWidth=1900", "   NodeHeight=850",
        '   NodeComment="Seated legs over the game pose; previous layer otherwise"', "End Object"]
write(sys.argv[2], out)
print("ok", sorted(blend.pin_ids))
