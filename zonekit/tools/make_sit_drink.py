"""Seated-drink free-arms tables (build 67), run in the open editor (harness/tools/ue_exec.py) after make_sit_yaw.py.

The one-handed drinks (energy drink, water, vodka, beer) lift the free left hand ~20 cm in their second half (toward
where a weapon grip would be): probe, builds 60-66, also bare-handed. The only slot after the game's arm layers is
FullBody, where our free-arms additive (AS_ImmCamp_SitAdditive: seated legs, one key per 5 deg of view yaw) plays.
So per drink this writes AS_ImmCamp_SitDrink_<drink>: the same additive, one ROW per drink frame (31 yaw keys each, so
the yaw still interpolates), plus a left-arm part that turns the drink's left arm into the campfire sit's lap pose,
faded in between 40% and 52% of the drink (the drink may use the left hand early: water opens its cap).
BP_ImmCampActor plays it instead of AS_ImmCamp_SitAdditive for these drinks; position = row * 31/30 + yaw key / 30,
row = drink montage position * 30.
"""
import unreal, math
AL = unreal.AnimationLibrary
EAL = unreal.EditorAssetLibrary
SRC = "/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/AS_fp_ca_gd_bonfire_sit_idle"
BASE = "/Game/_STALKER2/Animations/Player/AnimSequences/ar/common/stand/fp_ar_idle_stand"
ITEMS = "/Game/_STALKER2/Animations/Player/AnimSequences/Items/"
DRINKS = {"EnergyDrink": "EnergyDrink/AS_fp_energy_drink_use", "Water": "Water/AS_fp_water_use",
          "Vodka": "Vodka/AS_fp_vodka_use", "Beer": "Beer/AS_fp_beer_use"}
DIR = "/ImmersiveCampfires/Runtime"
TEMPLATE = DIR + "/AS_ImmCamp_SitAdditive"
ARM_ROOT = "jnt_l_shoulder"
FADE_A, FADE_B = 0.40, 0.52
YAWS = list(range(-75, 76, 5))
N = len(YAWS)
LEGS = {"jnt_b_hips_bag", "jnt_f_hips_bag", "jnt_l_hips_bag", "jnt_l_hips_bag2",
        "jnt_l_up_leg", "jnt_l_leg", "jnt_l_foot", "jnt_l_knee", "jnt_l_up_leg_roll", "jnt_l_leg_bag", "jnt_l_toe_base",
        "jnt_r_up_leg", "jnt_r_leg", "jnt_r_foot", "jnt_r_toe_base", "jnt_r_knee", "jnt_r_up_leg_roll", "jnt_r_leg_bag",
        "jnt_ik_foot_root", "jnt_l_ik_foot", "jnt_r_ik_foot"}


def q(t): r = t.rotation; return (r.x, r.y, r.z, r.w)
def v(t): return (t.translation.x, t.translation.y, t.translation.z)


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qinv(a): return (-a[0], -a[1], -a[2], a[3])
def qrot(a, p): r = qmul(qmul(a, (p[0], p[1], p[2], 0.0)), qinv(a)); return (r[0], r[1], r[2])
def rz(deg): h = math.radians(deg) / 2; return (0.0, 0.0, math.sin(h), math.cos(h))
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def scl(a, s): return (a[0] * s, a[1] * s, a[2] * s)


def slerp_id(qq, w):
    """identity -> qq by w (nlerp, short way)"""
    x, y, z, ww = qq
    if ww < 0: x, y, z, ww = -x, -y, -z, -ww
    r = (x * w, y * w, z * w, 1 - w + ww * w)
    n = math.sqrt(sum(c * c for c in r))
    return tuple(c / n for c in r)


log = []
src = unreal.load_asset(SRC)
base = unreal.load_asset(BASE)
for short, rel in DRINKS.items():
    d = unreal.load_asset(ITEMS + rel)
    if d is None:
        log.append("%s missing" % short); continue
    tracks = sorted(set(str(t) for t in AL.get_animation_track_names(src)) | set(str(t) for t in AL.get_animation_track_names(base))
                    | set(str(t) for t in AL.get_animation_track_names(d)))
    parent, arm = {}, set()
    for b in tracks:
        p = [str(x) for x in AL.find_bone_path_to_root(d, b)]
        parent[b] = p[1] if len(p) > 1 else None
        if ARM_ROOT in p:
            arm.add(b)
    sit = {b: AL.get_bone_pose_for_frame(src, b, 0, False) for b in tracks}
    bas = {b: AL.get_bone_pose_for_frame(base, b, 0, False) for b in tracks}
    nfr = AL.get_num_frames(d)
    rows = nfr + 1
    drk = {b: [AL.get_bone_pose_for_frame(d, b, f, False) for f in range(rows)] for b in arm}
    # the yaw part, as in make_sit_yaw.build_additive (AR stance)
    Qh_s, Ph_s = q(sit["jnt_hips"]), v(sit["jnt_hips"])
    Qh_b, Ph_b = q(bas["jnt_hips"]), v(bas["jnt_hips"])
    yaw = {}
    for b in tracks:
        tb = bas[b]
        yaw[b] = ([v(tb)] * N, [q(tb)] * N)
    hp = [qrot(rz(-y), Ph_s) for y in YAWS]
    yaw["jnt_hips"] = (hp, [Qh_b] * N)
    yaw["jnt_camera"] = ([add(v(bas["jnt_camera"]), sub(h, Ph_b)) for h in hp], [q(bas["jnt_camera"])] * N)
    for b in tracks:
        if parent[b] == "jnt_root" and b not in ("jnt_hips", "jnt_camera") and b not in LEGS:
            yaw[b] = ([add(v(bas[b]), sub(hp[k], Ph_b)) for k in range(N)], [q(bas[b])] * N)
    for b in LEGS:
        if b not in sit: continue
        t = sit[b]
        if parent[b] == "jnt_hips":
            pos, rot = [], []
            for k, y in enumerate(YAWS):
                r = rz(-y)
                rot.append(qmul(qinv(Qh_b), qmul(r, qmul(Qh_s, q(t)))))
                pos.append(qrot(qinv(Qh_b), sub(qrot(r, add(Ph_s, qrot(Qh_s, v(t)))), hp[k])))
            yaw[b] = (pos, rot)
        elif parent[b] == "jnt_root":
            yaw[b] = ([qrot(rz(-y), v(t)) for y in YAWS], [qmul(rz(-y), q(t)) for y in YAWS])
        else:
            yaw[b] = ([v(t)] * N, [q(t)] * N)
    # rows: one per drink frame; left arm: base (+) w * (lap (-) drink)
    keys = {}
    for b in tracks:
        ypos, yrot = yaw[b]
        pos, rot = [], []
        for f in range(rows):
            if b in arm:
                frac = f / float(nfr)
                w = min(1.0, max(0.0, (frac - FADE_A) / (FADE_B - FADE_A)))
                w = w * w * (3 - 2 * w)
                dq = slerp_id(qmul(q(sit[b]), qinv(q(drk[b][f]))), w)
                dp = scl(sub(v(sit[b]), v(drk[b][f])), w)
                for k in range(N):
                    rot.append(qmul(dq, q(bas[b])))
                    pos.append(add(v(bas[b]), dp))
            else:
                pos += ypos
                rot += yrot
        keys[b] = (pos, rot)
    total = rows * N
    name = "AS_ImmCamp_SitDrink_" + short
    path = DIR + "/" + name
    if not EAL.does_asset_exist(path):
        unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, DIR, unreal.load_asset(TEMPLATE))
    seq = unreal.load_asset(path)
    ctrl = seq.get_editor_property("controller")
    ctrl.open_bracket("ImmCamp seated drink", True)
    existing = set(str(t) for t in AL.get_animation_track_names(seq))
    for b in set(tracks) - existing:
        try:
            ctrl.add_bone_curve(b, True)
        except Exception:
            ctrl.add_bone_track(b, True)
    ctrl.set_frame_rate(unreal.FrameRate(30, 1), True)
    ctrl.set_number_of_frames(unreal.FrameNumber(total - 1), True)
    seq.set_editor_property("bone_compression_settings", unreal.load_asset("/Engine/Animation/DefaultRecorderBoneCompression"))
    seq.set_editor_property("additive_anim_type", unreal.AdditiveAnimationType.AAT_LOCAL_SPACE_BASE)
    seq.set_editor_property("ref_pose_type", unreal.AdditiveBasePoseType.ABPT_ANIM_FRAME)
    seq.set_editor_property("ref_pose_seq", base)
    seq.set_editor_property("ref_frame_index", 0)
    for b in tracks:
        pos, rot = keys[b]
        sc = bas[b].scale3d
        ctrl.set_bone_track_keys(b, [unreal.Vector(*p) for p in pos], [unreal.Quat(*r) for r in rot], [sc] * total, True)
    ctrl.close_bracket(True)
    log.append("%s rows=%d (drink frames %d, %.3f s) keys=%d len=%.3f arm=%d saved=%s" % (
        name, rows, nfr, d.get_play_length(), AL.get_num_keys(seq), seq.get_play_length(), len(arm), EAL.save_loaded_asset(seq, only_if_is_dirty=False)))
open("C:/Users/noahs/AppData/Local/Temp/make_sit_drink.log", "w").write("\n".join(log))
