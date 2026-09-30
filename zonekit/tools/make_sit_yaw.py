"""Builds the two seated poses in the open editor (ue_exec.py), build 21. Both are yaw tables:
31 keys at 30 fps (1.0 s), key i = the pose for a view yaw of -75 + 5*i degrees relative to the
seat. BP_ImmCampActor plays one as a dynamic montage in the FullBody slot and sets its position
from the view yaw every tick (Montage_SetPosition), so the legs stay put while the body turns
with the view.

AS_ImmCamp_SitRest (plain pose, build 22: a yaw x pitch table): the bonfire sit idle frame 0, whole
body turned by -yaw about the root (world-fixed while the actor turns with the view). A plain pose
also overrides jnt_camera, and the view pitch lives only in that bone (build 21: no looking up or
down), so the table has one row per 1 deg of yaw (151 rows) and 23 keys per row for pitch -60..50
in 5 deg steps (interpolated): key = row * 23 + (pitch + 60) / 5, jnt_camera rotation = the pitch.

AS_ImmCamp_SitAdditive (additive, local space, base fp_bh_idle_stand frame 0): used while an
action montage runs (items, PDA, backpack). v3: the hips keep the STANDING rotation and only move
(to the sit hips position, turned by -yaw), so every bone above the hips keeps whatever the game
animates (v2 re-rotated the hips and counter-rotated spine_01, which only cancels on the exact
base pose; on the drink / PDA poses the head ended ~13 cm beside the camera, build 20 probe).
Build 22: the other root children (jnt_item, jnt_weapon, IK hand targets ...) move with the hips too;
the PDA hangs off one of them and stayed at standing height (PDA "not held", build 21).
The legs (hips children) get the root-space sit transforms turned by -yaw; jnt_camera moves by
the same hips offset, so the camera keeps its standing relation to chest, arms and item.
"""
import unreal, math
AL = unreal.AnimationLibrary
EAL = unreal.EditorAssetLibrary
SRC = "/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/AS_fp_ca_gd_bonfire_sit_idle"
# Build 28: additive base = the item stance. Every item / PDA / backpack animation keys the hips 7.4 cm and
# 19 deg away from fp_bh_idle_stand (the same pose as fp_ar_idle_stand), so a bh-based table swung the
# seated legs by that much while an item played ("legs shift during item use", builds 21-27).
BASE = "/Game/_STALKER2/Animations/Player/AnimSequences/ar/common/stand/fp_ar_idle_stand"
DIR = "/ImmersiveCampfires/Runtime"
YAW_HALF, STEP = 75, 5
YAWS = list(range(-YAW_HALF, YAW_HALF + 1, STEP))          # 31 keys
N = len(YAWS)
REST_YAWS = list(range(-YAW_HALF, YAW_HALF + 1))           # 151 rows
PITCHES = list(range(-60, 51, 5))                          # 23 keys per row
REST_KEYS = [(y, p) for y in REST_YAWS for p in PITCHES]
LEGS = {"jnt_b_hips_bag", "jnt_f_hips_bag", "jnt_l_hips_bag", "jnt_l_hips_bag2",
        "jnt_l_up_leg", "jnt_l_leg", "jnt_l_foot", "jnt_l_knee", "jnt_l_up_leg_roll", "jnt_l_leg_bag", "jnt_l_toe_base",
        "jnt_r_up_leg", "jnt_r_leg", "jnt_r_foot", "jnt_r_toe_base", "jnt_r_knee", "jnt_r_up_leg_roll", "jnt_r_leg_bag",
        "jnt_ik_foot_root", "jnt_l_ik_foot", "jnt_r_ik_foot"}


def q(t):
    r = t.rotation
    return (r.x, r.y, r.z, r.w)


def v(t):
    return (t.translation.x, t.translation.y, t.translation.z)


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qinv(a):
    return (-a[0], -a[1], -a[2], a[3])


def qrot(a, p):
    r = qmul(qmul(a, (p[0], p[1], p[2], 0.0)), qinv(a))
    return (r[0], r[1], r[2])


def rz(deg):
    h = math.radians(deg) / 2
    return (0.0, 0.0, math.sin(h), math.cos(h))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def Q(t):
    return unreal.Quat(*t)


def V(t):
    return unreal.Vector(*t)


log = []
src = unreal.load_asset(SRC)
base = unreal.load_asset(BASE)
tracks = sorted(set(str(t) for t in AL.get_animation_track_names(src)) | set(str(t) for t in AL.get_animation_track_names(base)))
parent = {}
for b in tracks:
    p = [str(x) for x in AL.find_bone_path_to_root(src, b)]
    parent[b] = p[1] if len(p) > 1 else None
log.append("hips parent %s, camera parent %s, l_up_leg parent %s" % (parent.get("jnt_hips"), parent.get("jnt_camera"), parent.get("jnt_l_up_leg")))
assert parent["jnt_hips"] == "jnt_root" and parent["jnt_camera"] == "jnt_root"
sit = {b: AL.get_bone_pose_for_frame(src, b, 0, False) for b in tracks}
bas = {b: AL.get_bone_pose_for_frame(base, b, 0, False) for b in tracks}


def pitch_q(p):          # FRotator(p, 0, 0).Quaternion()
    h = math.radians(p) / 2
    return (0.0, -math.sin(h), 0.0, math.cos(h))


def prepare(name, additive, n=N):
    path = DIR + "/" + name
    if not EAL.does_asset_exist(path):
        unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, DIR, src)
    seq = unreal.load_asset(path)
    ctrl = seq.get_editor_property("controller")
    ctrl.open_bracket("ImmCamp yaw table", True)
    ctrl.set_frame_rate(unreal.FrameRate(30, 1), True)
    ctrl.set_number_of_frames(unreal.FrameNumber(n - 1), True)
    # build 24: lossless keys. The camera pitch lives in jnt_camera here and the game feeds the camera
    # back into the view pitch, so ACL's tiny error made the view creep and shake (build 22-23).
    seq.set_editor_property("bone_compression_settings", unreal.load_asset("/Engine/Animation/DefaultRecorderBoneCompression"))
    if additive:
        seq.set_editor_property("additive_anim_type", unreal.AdditiveAnimationType.AAT_LOCAL_SPACE_BASE)
        seq.set_editor_property("ref_pose_type", unreal.AdditiveBasePoseType.ABPT_ANIM_FRAME)
        seq.set_editor_property("ref_pose_seq", base)
        seq.set_editor_property("ref_frame_index", 0)
    else:
        seq.set_editor_property("additive_anim_type", unreal.AdditiveAnimationType.AAT_NONE)
    return seq, ctrl


def write(seq, ctrl, keys):
    for b in tracks:
        pos, rot, scl = keys[b]
        ctrl.set_bone_track_keys(b, [V(p) for p in pos], [Q(r) for r in rot], [s for s in scl], True)
    ctrl.close_bracket(True)
    log.append("%s keys=%d len=%.3f saved=%s" % (seq.get_name(), AL.get_num_keys(seq), seq.get_play_length(),
                                                EAL.save_loaded_asset(seq, only_if_is_dirty=False)))


# ---- resting: whole sit pose turned about the root ----
NR = len(REST_KEYS)
seq, ctrl = prepare("AS_ImmCamp_SitRest", False, NR)
keys = {}
for b in tracks:
    t = sit[b]
    if parent[b] == "jnt_root":
        pos, rot = [], []
        for y, p in REST_KEYS:
            r = rz(-y)
            pos.append(qrot(r, v(t)))
            rot.append(pitch_q(p) if b == "jnt_camera" else qmul(r, q(t)))
        keys[b] = (pos, rot, [t.scale3d] * NR)
    else:
        keys[b] = ([v(t)] * NR, [q(t)] * NR, [t.scale3d] * NR)
write(seq, ctrl, keys)

# ---- free arms: standing upper body, hips moved (not turned), sit legs turned about the root ----
seq, ctrl = prepare("AS_ImmCamp_SitAdditive", True)
Qh_s, Ph_s = q(sit["jnt_hips"]), v(sit["jnt_hips"])
Qh_b, Ph_b = q(bas["jnt_hips"]), v(bas["jnt_hips"])
keys = {}
for b in tracks:
    tb = bas[b]
    keys[b] = ([v(tb)] * N, [q(tb)] * N, [tb.scale3d] * N)       # zero delta by default
hp, cp = [], []
for y in YAWS:
    r = rz(-y)
    ph = qrot(r, Ph_s)
    hp.append(ph)
    cp.append(add(v(bas["jnt_camera"]), sub(ph, Ph_b)))
keys["jnt_hips"] = (hp, [Qh_b] * N, [bas["jnt_hips"].scale3d] * N)
keys["jnt_camera"] = (cp, [q(bas["jnt_camera"])] * N, [bas["jnt_camera"].scale3d] * N)
for b in tracks:                           # item / weapon / IK-hand roots follow the hips offset
    if parent[b] == "jnt_root" and b not in ("jnt_hips", "jnt_camera") and b not in LEGS:
        tb = bas[b]
        keys[b] = ([add(v(tb), sub(hp[k], Ph_b)) for k in range(N)], [q(tb)] * N, [tb.scale3d] * N)
for b in LEGS:
    if b not in sit:
        continue
    t = sit[b]
    if parent[b] == "jnt_hips":           # root-space sit transform, turned, re-expressed under the standing hips
        pos, rot = [], []
        for k, y in enumerate(YAWS):
            r = rz(-y)
            rs_rot = qmul(r, qmul(Qh_s, q(t)))
            rs_pos = qrot(r, add(Ph_s, qrot(Qh_s, v(t))))
            rot.append(qmul(qinv(Qh_b), rs_rot))
            pos.append(qrot(qinv(Qh_b), sub(rs_pos, hp[k])))
        keys[b] = (pos, rot, [t.scale3d] * N)
    elif parent[b] == "jnt_root":
        keys[b] = ([qrot(rz(-y), v(t)) for y in YAWS], [qmul(rz(-y), q(t)) for y in YAWS], [t.scale3d] * N)
    else:
        keys[b] = ([v(t)] * N, [q(t)] * N, [t.scale3d] * N)
log.append("hips sit %s base %s; camera drop at yaw 0 %s" % (tuple(round(x, 1) for x in Ph_s), tuple(round(x, 1) for x in Ph_b),
                                                            tuple(round(x, 1) for x in sub(Ph_s, Ph_b))))
write(seq, ctrl, keys)
unreal.log("SITYAW\n" + "\n".join(log))
