"""Builds /ImmersiveCampfires/Runtime/AS_ImmCamp_SitAdditive in the open editor (ue_exec.py).

v2 (build 17). The vanilla bonfire sit idle, duplicated and edited per frame, then made additive
(local space) against fp_bh_idle_stand frame 0:
  - hips and legs keep the sit animation (seated legs, pelvis down);
  - spine_01 gets a counter-rotation so the chest keeps its standing orientation (in root space);
  - every bone above spine_01 is set to the standing frame (zero additive delta: the game's arm,
    PDA and item animations stay untouched);
  - jnt_camera (a child of jnt_root, not of the head) is moved by exactly the chest's drop, so the
    camera keeps its standing relation to the arms (v1 used the sit camera: PDA / bottles off-centre).
Rotations use UE's convention: parent-space rotation composes as Q_world = Q_parent * Q_local.
"""
import unreal, math
AL = unreal.AnimationLibrary
EAL = unreal.EditorAssetLibrary
SRC = "/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/AS_fp_ca_gd_bonfire_sit_idle"
BASE = "/Game/_STALKER2/Animations/Player/AnimSequences/bh/stand/fp_bh_idle_stand"
DST_DIR, DST_NAME = "/ImmersiveCampfires/Runtime", "AS_ImmCamp_SitAdditive"
DST = DST_DIR + "/" + DST_NAME
KEEP_SIT = {"jnt_hips", "jnt_b_hips_bag", "jnt_f_hips_bag", "jnt_l_hips_bag", "jnt_l_hips_bag2",
            "jnt_l_up_leg", "jnt_l_leg", "jnt_l_foot", "jnt_l_knee", "jnt_l_up_leg_roll", "jnt_l_leg_bag", "jnt_l_toe_base",
            "jnt_r_up_leg", "jnt_r_leg", "jnt_r_foot", "jnt_r_toe_base", "jnt_r_knee", "jnt_r_up_leg_roll", "jnt_r_leg_bag",
            "jnt_ik_foot_root", "jnt_l_ik_foot", "jnt_r_ik_foot"}


def q(t):
    r = t.rotation
    return (r.x, r.y, r.z, r.w)


def qmul(a, b):  # Hamilton product a*b
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qinv(a):
    x, y, z, w = a
    return (-x, -y, -z, w)


def qrot(a, v):  # rotate vector v by quaternion a
    p = qmul(qmul(a, (v[0], v[1], v[2], 0.0)), qinv(a))
    return (p[0], p[1], p[2])


def vec(t):
    return (t.translation.x, t.translation.y, t.translation.z)


log = []
base = unreal.load_asset(BASE)
src = unreal.load_asset(SRC)
if not EAL.does_asset_exist(DST):   # edit in place when it exists (the actor BP references it)
    unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(DST_NAME, DST_DIR, src)
seq = unreal.load_asset(DST)
n = AL.get_num_keys(seq)
tracks = set(str(t) for t in AL.get_animation_track_names(seq)) | set(str(t) for t in AL.get_animation_track_names(base))
log.append("keys %d tracks %d" % (n, len(tracks)))
path = [str(b) for b in AL.find_bone_path_to_root(seq, "jnt_spine_01")]
log.append("spine_01 path to root: %s" % path)
root = unreal.AnimationLibrary.get_bone_pose_for_frame(src, "jnt_root", 0, False)
log.append("sit root t=%s r=%s" % (vec(root), q(root)))


def world_rot_pos(anim, bone_chain, frame):
    """Root-space rotation / position of the last bone in bone_chain (root first)."""
    Q = (0.0, 0.0, 0.0, 1.0)
    P = (0.0, 0.0, 0.0)
    for b in bone_chain:
        t = AL.get_bone_pose_for_frame(anim, b, frame, False)
        off = qrot(Q, vec(t))
        P = (P[0] + off[0], P[1] + off[1], P[2] + off[2])
        Q = qmul(Q, q(t))
    return Q, P


chain_to_hips = list(reversed(path))[:-1]          # root ... hips (path is spine_01 -> root)
if chain_to_hips and chain_to_hips[0] == "jnt_root":
    chain_to_hips = chain_to_hips[1:]              # root-space = relative to jnt_root
log.append("chain to hips (root space): %s" % chain_to_hips)
sp_base = AL.get_bone_pose_for_frame(base, "jnt_spine_01", 0, False)
cam_base = AL.get_bone_pose_for_frame(base, "jnt_camera", 0, False)
Qh_b, Ph_b = world_rot_pos(base, chain_to_hips, 0)
Qs_b = qmul(Qh_b, q(sp_base))                      # spine_01 root-space rotation, standing
off_b = qrot(Qh_b, vec(sp_base))
Ps_b = (Ph_b[0] + off_b[0], Ph_b[1] + off_b[1], Ph_b[2] + off_b[2])

sp_pos, sp_rot, sp_scl, cam_pos, cam_rot, cam_scl = [], [], [], [], [], []
for f in range(n):
    Qh_s, Ph_s = world_rot_pos(src, chain_to_hips, f)
    ql = qmul(qinv(Qh_s), Qs_b)                    # local rotation that keeps the chest upright
    sp_pos.append(sp_base.translation)
    sp_rot.append(unreal.Quat(*ql))
    sp_scl.append(sp_base.scale3d)
    off_s = qrot(Qh_s, vec(sp_base))
    Ps_s = (Ph_s[0] + off_s[0], Ph_s[1] + off_s[1], Ph_s[2] + off_s[2])
    d = (Ps_s[0] - Ps_b[0], Ps_s[1] - Ps_b[1], Ps_s[2] - Ps_b[2])
    cam_pos.append(unreal.Vector(cam_base.translation.x + d[0], cam_base.translation.y + d[1], cam_base.translation.z + d[2]))
    cam_rot.append(cam_base.rotation)
    cam_scl.append(cam_base.scale3d)
    if f == 0:
        log.append("frame0 chest drop %s" % (d,))

ctrl = seq.get_editor_property("controller")
ctrl.open_bracket("ImmCamp additive v2", True)
done = 0
for b in sorted(tracks):
    if b in KEEP_SIT:
        continue
    if b == "jnt_spine_01":
        ctrl.set_bone_track_keys(b, sp_pos, sp_rot, sp_scl, True)
    elif b == "jnt_camera":
        ctrl.set_bone_track_keys(b, cam_pos, cam_rot, cam_scl, True)
    else:
        t = AL.get_bone_pose_for_frame(base, b, 0, False)
        ctrl.set_bone_track_keys(b, [t.translation] * n, [t.rotation] * n, [t.scale3d] * n, True)
    done += 1
ctrl.close_bracket(True)
log.append("tracks rewritten %d" % done)
seq.set_editor_property("additive_anim_type", unreal.AdditiveAnimationType.AAT_LOCAL_SPACE_BASE)
seq.set_editor_property("ref_pose_type", unreal.AdditiveBasePoseType.ABPT_ANIM_FRAME)
seq.set_editor_property("ref_pose_seq", base)
seq.set_editor_property("ref_frame_index", 0)
log.append("saved %s" % EAL.save_loaded_asset(seq, only_if_is_dirty=False))
unreal.log("\n".join(log))
