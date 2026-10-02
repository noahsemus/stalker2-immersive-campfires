// ImmCampProbeCpp - read-only dev-box diagnostic for ImmersiveCampfires. Never shipped.
// While the player is seated (PC's contextual-action flag set) it logs:
//   - every InputMappingContext named IMC_PlayerCA in memory: full path, row count, keys;
//   - the live key list the Enhanced Input system is using (EnhancedPlayerInput.EnhancedActionMappings)
//     for the actions this mod cares about.
// Scans run on the sit edge (+0.5 s, +3 s); the live list is read once a second and logged on change.
#include <Mod/CppUserModBase.hpp>
#include <DynamicOutput/DynamicOutput.hpp>
#include <Unreal/UObjectGlobals.hpp>
#include <Unreal/UObject.hpp>
#include <Unreal/UClass.hpp>
#include <Unreal/NameTypes.hpp>
#include <Unreal/CoreUObject/UObject/UnrealType.hpp>
#include <Windows.h>
#include <cmath>
#include <string>
#include <vector>
#include <set>

using namespace RC;
using namespace RC::Unreal;

class ImmCampProbe : public CppUserModBase {
public:
    ImmCampProbe() {
        ModName = STR("ImmCampProbeCpp"); ModVersion = STR("0.1"); ModAuthors = STR("Noah");
        ModDescription = STR("Read-only seated-input probe for ImmersiveCampfires.");
    }
    uint64_t m_lastHb = 0, m_lastLive = 0, m_sitStart = 0; int m_scans = 0; bool m_loggedProps = false;
    StringType m_lastLiveStr, m_lastState, m_lastPP;

    static bool Wanted(const StringType& a) {
        return a == STR("IA_PlayerCAExit") || a == STR("IA_OpenPDA") || a == STR("IA_Inventory") || a == STR("IA_ItemSelector")
            || a.rfind(STR("IA_QuickSlot"), 0) == 0 || a == STR("IA_GuitarContextualAction");
    }
    // Reads a TArray<FEnhancedActionKeyMapping> property; returns "Action:Key ..." for the wanted actions (all when wantedOnly=false).
    struct Row { UObject* act; uint8_t key[sizeof(FName)]; };
    static const int32_t kMaxRows = 4000;
    // SEH-only copy of (action, key name) pairs; no objects with destructors in here.
    static bool GuardedCopyRows(uint8_t* hdr, int32_t es, int32_t actOff, int32_t keyOff, Row* rows, int32_t* num) {
        __try {
            uint8_t* data = *reinterpret_cast<uint8_t**>(hdr); int32_t n = *reinterpret_cast<int32_t*>(hdr + 8);
            if (n < 0 || n > kMaxRows || (n > 0 && !data)) return false;
            for (int32_t i = 0; i < n; ++i) {
                uint8_t* e = data + (int64_t)i * es;
                rows[i].act = *reinterpret_cast<UObject**>(e + actOff);
                memcpy(rows[i].key, e + keyOff, sizeof(FName));
            }
            *num = n; return true;
        } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
    }
    static bool GuardedRows(uint8_t* hdr, int32_t es, int32_t actOff, int32_t keyOff, bool wantedOnly, StringType* out, int* total) {
        std::vector<Row> rows(kMaxRows); int32_t num = 0;
        if (!GuardedCopyRows(hdr, es, actOff, keyOff, rows.data(), &num)) return false;
        *total = num;
        for (int32_t i = 0; i < num; ++i) {
            StringType an = rows[i].act ? rows[i].act->GetName() : StringType(STR("null"));
            if (wantedOnly && !Wanted(an)) continue;
            *out += an + STR(":") + reinterpret_cast<FName*>(rows[i].key)->ToString() + STR(" ");
        }
        return true;
    }
    static bool ReadMappings(UObject* o, const wchar_t* prop, bool wantedOnly, StringType* out, int* total) {
        FProperty* mp = o->GetPropertyByNameInChain(prop); FArrayProperty* ap = mp ? CastField<FArrayProperty>(mp) : nullptr;
        FStructProperty* ip = ap ? CastField<FStructProperty>(ap->GetInner()) : nullptr;
        if (!ip) return false;
        int32_t keyOff = -1, actOff = -1;
        for (UStruct* w = ip->GetStruct(); w; w = w->GetSuperStruct())
            for (FProperty* p : TFieldRange<FProperty>(w, EFieldIterationFlags::None)) {
                if (p->GetName() == STR("Key")) keyOff = p->GetOffset_ForInternal();
                if (p->GetName() == STR("Action")) actOff = p->GetOffset_ForInternal();
            }
        if (keyOff < 0 || actOff < 0) return false;
        return GuardedRows(mp->ContainerPtrToValuePtr<uint8_t>(o), ap->GetInner()->GetElementSize(), actOff, keyOff, wantedOnly, out, total);
    }
    static bool IsA(UObject* o, const wchar_t* cls) {
        for (UStruct* w = o->GetClassPrivate(); w; w = w->GetSuperStruct()) if (w->GetName() == cls) return true;
        return false;
    }
    void ScanContexts(const wchar_t* when) {
        std::vector<UObject*> found;
        UObjectGlobals::ForEachUObject([&](UObject* obj, int32_t, int32_t) -> LoopAction {
            if (obj && obj->GetName() == STR("IMC_PlayerCA") && IsA(obj, STR("InputMappingContext"))) found.push_back(obj);
            return LoopAction::Continue;
        });
        for (UObject* imc : found) {
            StringType rows; int total = -1;
            bool ok = ReadMappings(imc, STR("Mappings"), false, &rows, &total);
            Output::send<LogLevel::Verbose>(STR("[CampProbe] imc {} obj={} ok={} rows={} [{}]\n"), when, imc->GetFullName(), ok ? 1 : 0, total, rows);
        }
        if (found.empty()) Output::send<LogLevel::Verbose>(STR("[CampProbe] imc {} none in memory\n"), when);
        // Layer 2 host: are the mod's subsystem and seated-input actor alive?
        StringType hosts;
        UObjectGlobals::ForEachUObject([&](UObject* obj, int32_t, int32_t) -> LoopAction {
            if (!obj) return LoopAction::Continue;
            StringType cn = obj->GetClassPrivate() ? obj->GetClassPrivate()->GetName() : StringType();
            if ((cn == STR("BP_ImmCampActor_C") || cn == STR("BP_ImmCampSubsystem_C")) && obj->GetName().rfind(STR("Default__"), 0) != 0) {
                hosts += obj->GetFullName();
                if (FProperty* p = obj->GetPropertyByNameInChain(STR("SpawnAttempts")))
                    if (int32_t* v = p->ContainerPtrToValuePtr<int32_t>(obj)) hosts += STR(" spawnAttempts=") + std::to_wstring(*v);
                for (const wchar_t* iv : { STR("Presses"), STR("Calls") })
                    if (FProperty* p = obj->GetPropertyByNameInChain(iv))
                        if (int32_t* v = p->ContainerPtrToValuePtr<int32_t>(obj)) hosts += StringType(STR(" ")) + iv + STR("=") + std::to_wstring(*v);
                for (const wchar_t* bv : { STR("SeatedMode"), STR("Standing"), STR("VanillaHold"), STR("LimitsSaved") })
                    if (FProperty* p = obj->GetPropertyByNameInChain(bv))
                        if (FBoolProperty* bp = CastField<FBoolProperty>(p)) {
                            uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(obj);
                            if (raw) hosts += StringType(STR(" ")) + bv + STR("=") + (bp->GetPropertyValue(raw) ? STR("1") : STR("0"));
                        }
                if (FProperty* p = obj->GetPropertyByNameInChain(STR("InputComponent")))
                    if (UObject** v = p->ContainerPtrToValuePtr<UObject*>(obj)) hosts += StringType(STR(" inputComp=")) + (*v ? (*v)->GetClassPrivate()->GetName() : StringType(STR("null")));
                if (FProperty* p = obj->GetPropertyByNameInChain(STR("SeatedActor")))
                    if (UObject** v = p->ContainerPtrToValuePtr<UObject*>(obj)) hosts += StringType(STR(" seatedActor=")) + (*v ? (*v)->GetName() : StringType(STR("null")));
                hosts += STR(" | ");
            }
            return LoopAction::Continue;
        });
        Output::send<LogLevel::Verbose>(STR("[CampProbe] hosts {} [{}]\n"), when, hosts);
        // Post-process layer on the player mesh (ours while seated, ImmersiveDialogue's or none otherwise)
        if (UObject* pawn = UObjectGlobals::FindFirstOf(STR("PC"))) {
            UObject* mesh = nullptr;
            if (FProperty* p = pawn->GetPropertyByNameInChain(STR("Mesh"))) { UObject** v = p->ContainerPtrToValuePtr<UObject*>(pawn); if (v) mesh = *v; }
            if (mesh) {
                StringType pp = STR("null"); int dis = -1;
                if (FProperty* p = mesh->GetPropertyByNameInChain(STR("PostProcessAnimInstance"))) { UObject** v = p->ContainerPtrToValuePtr<UObject*>(mesh); if (v && *v) pp = (*v)->GetClassPrivate()->GetName(); }
                if (FProperty* p = mesh->GetPropertyByNameInChain(STR("bDisablePostProcessBlueprint"))) if (FBoolProperty* bp = CastField<FBoolProperty>(p)) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(mesh); if (raw) dis = bp->GetPropertyValue(raw) ? 1 : 0; }
                Output::send<LogLevel::Verbose>(STR("[CampProbe] pp {} class={} disabled={}\n"), when, pp, dis);
            }
        }
    }
    int SeatedFlag(UObject* pawn) {
        int v = -1;
        for (UStruct* w = pawn->GetClassPrivate(); w; w = w->GetSuperStruct())
            for (FProperty* p : TFieldRange<FProperty>(w, EFieldIterationFlags::None)) {
                StringType n = p->GetName();
                if (n.find(STR("ContextualAction")) == StringType::npos) continue;
                FBoolProperty* bp = CastField<FBoolProperty>(p);
                if (!m_loggedProps) Output::send<LogLevel::Verbose>(STR("[CampProbe] PC prop {} ({})\n"), n, p->GetClass().GetName());
                if (bp && v < 0) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(pawn); if (raw) v = bp->GetPropertyValue(raw) ? 1 : 0; }
            }
        m_loggedProps = true;
        return v;
    }

    // ---- body / hands measurements (ProcessEvent getters, SEH-guarded) ----
    static bool GuardedPE(UObject* o, UFunction* fn, void* parms) {
        __try { o->ProcessEvent(fn, parms); return true; } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
    }
    static UObject* ObjProp(UObject* o, const wchar_t* n) {
        if (!o) return nullptr; FProperty* p = o->GetPropertyByNameInChain(n); if (!p) return nullptr;
        UObject** v = p->ContainerPtrToValuePtr<UObject*>(o); return v ? *v : nullptr;
    }
    struct FV { double X, Y, Z; };
    static bool CompLoc(UObject* c, FV* out) {
        if (!c) return false; UFunction* f = c->GetFunctionByNameInChain(FName(STR("K2_GetComponentLocation"))); if (!f) return false;
        struct { FV R; } p{}; if (!GuardedPE(c, f, &p)) return false; *out = p.R; return true;
    }
    static bool Sock(UObject* mesh, const wchar_t* s, FV* out) {
        if (!mesh) return false; UFunction* f = mesh->GetFunctionByNameInChain(FName(STR("GetSocketLocation"))); if (!f) return false;
        struct { FName N; FV R; } p{}; p.N = FName(s); if (!GuardedPE(mesh, f, &p)) return false; *out = p.R; return true;
    }
    static int CallBool(UObject* o, const wchar_t* fn) {
        UFunction* f = o->GetFunctionByNameInChain(FName(fn)); if (!f) return -1;
        struct { bool R = false; } p; return GuardedPE(o, f, &p) ? (p.R ? 1 : 0) : -2;
    }
    static int CallByte(UObject* o, const wchar_t* fn) {
        UFunction* f = o->GetFunctionByNameInChain(FName(fn)); if (!f) return -1;
        struct { uint8_t R = 0; } p; return GuardedPE(o, f, &p) ? (int)p.R : -2;
    }
    uint64_t m_lastBody = 0;
    struct FR { double P, Y, R; };
    // offset of a mesh socket from the camera, in camera space (forward, right, up), UE FRotationMatrix axes
    static FV CamSpace(const FV& c, const FR& r, const FV& w) {
        const double d2r = 3.14159265358979 / 180.0;
        double SP = sin(r.P * d2r), CP = cos(r.P * d2r), SY = sin(r.Y * d2r), CY = cos(r.Y * d2r), SR = sin(r.R * d2r), CR = cos(r.R * d2r);
        FV X{CP * CY, CP * SY, SP}, Y{SR * SP * CY - CR * SY, SR * SP * SY + CR * CY, -SR * CP}, Z{-(CR * SP * CY + SR * SY), CY * SR - CR * SP * SY, CR * CP};
        FV d{w.X - c.X, w.Y - c.Y, w.Z - c.Z};
        return FV{d.X * X.X + d.Y * X.Y + d.Z * X.Z, d.X * Y.X + d.Y * Y.Y + d.Z * Y.Z, d.X * Z.X + d.Y * Z.Y + d.Z * Z.Z};
    }
    void Body(UObject* pawn, int seated, uint64_t now) {
        UObject* mesh = ObjProp(pawn, STR("Mesh")); UObject* cam = ObjProp(pawn, STR("Camera"));
        UObject* anim = nullptr; int act = -1; StringType mont = STR("none");
        if (mesh) if (UFunction* f = mesh->GetFunctionByNameInChain(FName(STR("GetAnimInstance")))) { struct { UObject* R = nullptr; } p; if (GuardedPE(mesh, f, &p)) anim = p.R; }
        if (anim) {
            if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("IsSlotActive")))) { struct { FName N; bool R = false; } p{}; p.N = FName(STR("MainActionSlot")); if (GuardedPE(anim, f, &p)) act = p.R ? 1 : 0;
                struct { FName N; bool R = false; } q{}; q.N = FName(STR("DefaultSlot")); if (GuardedPE(anim, f, &q) && q.R) act += 10;
                struct { FName N; bool R = false; } u{}; u.N = FName(STR("UpperBody")); if (GuardedPE(anim, f, &u) && u.R) act += 100; }
            if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("GetCurrentActiveMontage")))) { struct { UObject* R = nullptr; } p; if (GuardedPE(anim, f, &p) && p.R) {
                mont = p.R->GetName();
                StringType sec = STR("?"); float rate = -1;
                if (UFunction* g = anim->GetFunctionByNameInChain(FName(STR("Montage_GetCurrentSection")))) { struct { UObject* M; FName R; } q{}; q.M = p.R; if (GuardedPE(anim, g, &q)) sec = q.R.ToString(); }
                if (UFunction* g = anim->GetFunctionByNameInChain(FName(STR("Montage_GetPlayRate")))) { struct { UObject* M; float R = -1; } q{}; q.M = p.R; if (GuardedPE(anim, g, &q)) rate = q.R; }
                mont += STR("/") + sec + STR("@") + std::to_wstring(rate).substr(0, 4);
            } }
        }
        uint64_t every = (seated == 1 || act == 1) ? 500u : 5000u;
        if (now - m_lastBody < every) return;
        m_lastBody = now;
        FV c{}, jc{}, hd{}, rh{}, lh{}, hp{}; FR r{}; CompLoc(cam, &c); Sock(mesh, STR("jnt_camera"), &jc); Sock(mesh, STR("jnt_head"), &hd);
        Sock(mesh, STR("jnt_r_hand"), &rh); Sock(mesh, STR("jnt_l_hand"), &lh); Sock(mesh, STR("jnt_hips"), &hp);
        if (cam) if (UFunction* f = cam->GetFunctionByNameInChain(FName(STR("K2_GetComponentRotation")))) { struct { FR R; } p{}; if (GuardedPE(cam, f, &p)) r = p.R; }
        FV R = CamSpace(c, r, rh), L = CamSpace(c, r, lh), H = CamSpace(c, r, hp), J = CamSpace(c, r, jc);
        wchar_t b[640];
        swprintf_s(b, 640, L"seated=%d act=%d mont=%s pitch=%.2f yaw=%.2f | camspace fwd/right/up: rhand=(%.0f,%.0f,%.0f) lhand=(%.0f,%.0f,%.0f) hips=(%.1f,%.1f,%.1f) jntcam=(%.0f,%.0f,%.0f) head-cam=(%.0f,%.0f,%.0f) camParent=%s",
            seated, act, mont.c_str(), r.P, r.Y, R.X, R.Y, R.Z, L.X, L.Y, L.Z, H.X, H.Y, H.Z, J.X, J.Y, J.Z, hd.X - c.X, hd.Y - c.Y, hd.Z - c.Z,
            cam ? (ObjProp(cam, STR("AttachParent")) ? ObjProp(cam, STR("AttachParent"))->GetName().c_str() : L"none") : L"nocam");
        Output::send<LogLevel::Verbose>(STR("[CampProbe] body {}\n"), StringType(b));
        int moveIgn = -1, mode = -1; UObject* ctl = ObjProp(pawn, STR("Controller")); UObject* cmc = ObjProp(pawn, STR("CharacterMovement"));
        if (ctl) moveIgn = CallBool(ctl, STR("IsMoveInputIgnored"));
        if (cmc) if (FProperty* mp = cmc->GetPropertyByNameInChain(STR("MovementMode"))) { uint8_t* v = mp->ContainerPtrToValuePtr<uint8_t>(cmc); if (v) mode = *v; }
        FV aloc{}; if (UFunction* f = pawn->GetFunctionByNameInChain(FName(STR("K2_GetActorLocation")))) { struct { FV R; } q{}; if (GuardedPE(pawn, f, &q)) aloc = q.R; }
        int camAbs = -1; FR camRel{};
        if (cam) { if (FProperty* p = cam->GetPropertyByNameInChain(STR("bAbsoluteRotation"))) if (FBoolProperty* bp = CastField<FBoolProperty>(p)) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(cam); if (raw) camAbs = bp->GetPropertyValue(raw) ? 1 : 0; }
                   if (FProperty* p = cam->GetPropertyByNameInChain(STR("RelativeRotation"))) { FR* v = p->ContainerPtrToValuePtr<FR>(cam); if (v) camRel = *v; } }
        swprintf_s(b, 640, L"moveIgnored=%d moveMode=%d camAbs=%d camRel=(%.1f,%.1f,%.1f) lookIgnored=%d actor=(%.1f,%.1f,%.1f)", moveIgn, mode, camAbs, camRel.P, camRel.Y, camRel.R, ctl ? CallBool(ctl, STR("IsLookInputIgnored")) : -1, aloc.X, aloc.Y, aloc.Z);
        Output::send<LogLevel::Verbose>(STR("[CampProbe] move {}\n"), StringType(b));
        swprintf_s(b, 640, L"hand=%d hasMain=%d leftBusy=%d equippedNone=%d pda=%d bag=%d",
            CallByte(pawn, STR("GetMainHandEquipType")), CallBool(pawn, STR("HasItemInMainHand")), CallBool(pawn, STR("IsLeftHandBusy")),
            CallBool(pawn, STR("IsPlayerEquipedWithNone")), CallBool(pawn, STR("IsUsingPDA")), CallBool(pawn, STR("IsUsingBackpack")));
        Output::send<LogLevel::Verbose>(STR("[CampProbe] hands {}\n"), StringType(b));
    }

    // per-frame burst (40 frames every 10 s while seated): view pitch jitter at rest (builds 22-24)
    UObject* m_bPawn = nullptr; UObject* m_bAct = nullptr; int m_bSeated = 0; uint64_t m_lastBurst = 0; int m_burst = 0; uint64_t m_frame = 0;
    StringType m_lastMont; UObject* m_lastPose = nullptr;
    // every change of the active montage and of our PoseMontage while seated (input drop after items, build 32)
    void MontageEvents(uint64_t now) {
        if (!m_bPawn || m_bSeated != 1 || m_bPawn->IsUnreachable()) { m_lastMont.clear(); return; }
        UObject* mesh = ObjProp(m_bPawn, STR("Mesh")); UObject* anim = nullptr;
        if (mesh) if (UFunction* f = mesh->GetFunctionByNameInChain(FName(STR("GetAnimInstance")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(mesh, f, &q)) anim = q.R; }
        StringType mont = STR("none");
        if (anim) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("GetCurrentActiveMontage")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(anim, f, &q) && q.R) mont = q.R->GetName(); }
        UObject* pose = (m_bAct && !m_bAct->IsUnreachable()) ? ObjProp(m_bAct, STR("PoseMontage")) : nullptr;
        if (mont != m_lastMont || pose != m_lastPose) {
            Output::send<LogLevel::Verbose>(STR("[CampProbe] mont t={} active={} pose={}\n"), now % 100000, mont, pose ? pose->GetName() : StringType(STR("null")));
            m_lastMont = mont; m_lastPose = pose;
        }
    }
    // transition trace (build 40: "legs, arms and body snap when an item ends"): 2.5 s at ~30 Hz from every change of
    // MainActionSlot activity or of PoseAdditive; bone positions relative to the actor, our pose state
    uint64_t m_trEnd = 0, m_trLast = 0; int m_lastActSlot = -1, m_lastPA = -1; StringType m_lastTgt;
    static bool BoolVar(UObject* o, const wchar_t* n) {
        if (!o) return false; FProperty* p = o->GetPropertyByNameInChain(n); FBoolProperty* bp = p ? CastField<FBoolProperty>(p) : nullptr;
        uint8_t* raw = p ? p->ContainerPtrToValuePtr<uint8_t>(o) : nullptr; return bp && raw && bp->GetPropertyValue(raw);
    }
    static double DblVar(UObject* o, const wchar_t* n) {
        if (!o) return 0; FProperty* p = o->GetPropertyByNameInChain(n); double* v = p ? p->ContainerPtrToValuePtr<double>(o) : nullptr; return v ? *v : 0;
    }
    void Trace(uint64_t now) {
        if (!m_bPawn || m_bSeated != 1 || m_bPawn->IsUnreachable() || !m_bAct || m_bAct->IsUnreachable()) return;
        UObject* mesh = ObjProp(m_bPawn, STR("Mesh")); if (!mesh) return;
        UObject* anim = nullptr;
        if (UFunction* f = mesh->GetFunctionByNameInChain(FName(STR("GetAnimInstance")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(mesh, f, &q)) anim = q.R; }
        int act = -1;
        if (anim) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("IsSlotActive")))) { struct { FName N; bool R = false; } q{}; q.N = FName(STR("MainActionSlot")); if (GuardedPE(anim, f, &q)) act = q.R ? 1 : 0; }
        int pa = BoolVar(m_bAct, STR("PoseAdditive")) ? 1 : 0;
        if (act != m_lastActSlot || pa != m_lastPA) { m_trEnd = now + 2500; Output::send<LogLevel::Verbose>(STR("[CampProbe] trace start act={} poseAdditive={}\n"), act, pa); }
        m_lastActSlot = act; m_lastPA = pa;
        // guitar spot data: the saved interaction target's location, logged when it changes
        if (UObject* tgt = ObjProp(m_bAct, STR("TargetSaved"))) {
            FV tl{}; CompLoc(tgt, &tl); UObject* own = nullptr;
            if (UFunction* f = tgt->GetFunctionByNameInChain(FName(STR("GetOwner")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(tgt, f, &q)) own = q.R; }
            FV ol{}; if (own) if (UFunction* f = own->GetFunctionByNameInChain(FName(STR("K2_GetActorLocation")))) { struct { FV R; } q{}; if (GuardedPE(own, f, &q)) ol = q.R; }
            wchar_t tb[256]; swprintf_s(tb, 256, L"target comp=(%.1f,%.1f,%.1f) owner=%s (%.1f,%.1f,%.1f)", tl.X, tl.Y, tl.Z, own ? own->GetName().c_str() : L"none", ol.X, ol.Y, ol.Z);
            StringType ts(tb); if (ts != m_lastTgt) { m_lastTgt = ts; Output::send<LogLevel::Verbose>(STR("[CampProbe] {}\n"), ts); }
        }
        if (now > m_trEnd || now - m_trLast < 33) return;
        m_trLast = now;
        FV a{}; if (UFunction* f = m_bPawn->GetFunctionByNameInChain(FName(STR("K2_GetActorLocation")))) { struct { FV R; } q{}; if (GuardedPE(m_bPawn, f, &q)) a = q.R; }
        FV lf{}, rh{}, lh{}, sp{}, hp{}; Sock(mesh, STR("jnt_l_foot"), &lf); Sock(mesh, STR("jnt_r_hand"), &rh); Sock(mesh, STR("jnt_l_hand"), &lh); Sock(mesh, STR("jnt_spine_03"), &sp); Sock(mesh, STR("jnt_hips"), &hp);
        StringType mont = STR("none");
        if (anim) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("GetCurrentActiveMontage")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(anim, f, &q) && q.R) mont = q.R->GetName(); }
        wchar_t b[400];
        swprintf_s(b, 400, L"t=%llu act=%d PA=%d AR=%d unh=%d body=%.1f seat=%.1f lfoot=(%.0f,%.0f,%.0f) rhand=(%.0f,%.0f,%.0f) lhand=(%.0f,%.0f,%.0f) spine3=(%.0f,%.0f,%.0f) hips=(%.0f,%.0f,%.0f) mont=%s",
            now % 100000, act, pa, BoolVar(m_bAct, STR("PoseAR")) ? 1 : 0, BoolVar(m_bAct, STR("CamUnhooked")) ? 1 : 0, DblVar(m_bAct, STR("BodyYaw")), DblVar(m_bAct, STR("SeatYaw")),
            lf.X - a.X, lf.Y - a.Y, lf.Z - a.Z, rh.X - a.X, rh.Y - a.Y, rh.Z - a.Z, lh.X - a.X, lh.Y - a.Y, lh.Z - a.Z, sp.X - a.X, sp.Y - a.Y, sp.Z - a.Z, hp.X - a.X, hp.Y - a.Y, hp.Z - a.Z, mont.c_str());
        Output::send<LogLevel::Verbose>(STR("[CampProbe] tr {}\n"), StringType(b));
        // build 86: the item-tracking state behind "busy" (backpack items loop rest / free arms every ~0.1 s)
        auto nm = [](UObject* o) { return o ? o->GetName() : StringType(STR("-")); };
        UObject* im = ObjProp(m_bAct, STR("ItemMontage")); UObject* em = ObjProp(m_bAct, STR("EndedMontage")); UObject* fm = ObjProp(m_bAct, STR("FrozenMontage"));
        int slots = 0; const wchar_t* sn[5] = { L"MainActionSlot", L"DefaultSlot", L"UpperBody", L"LeftHand", L"RightHand" };
        if (anim) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("IsSlotActive"))))
            for (int i = 0; i < 5; ++i) { struct { FName N; bool R = false; } q{}; q.N = FName(sn[i]); if (GuardedPE(anim, f, &q) && q.R) slots |= 1 << i; }
        int imPlay = -1, emAct = -1; float imPos = -1.f, imLen = -1.f;
        if (anim && im) {
            if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("Montage_IsPlaying")))) { struct { UObject* M; bool R = false; } q{ im }; if (GuardedPE(anim, f, &q)) imPlay = q.R; }
            if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("Montage_GetPosition")))) { struct { UObject* M; float R = 0; } q{ im }; if (GuardedPE(anim, f, &q)) imPos = q.R; }
            if (UFunction* f = im->GetFunctionByNameInChain(FName(STR("GetPlayLength")))) { struct { float R = 0; } q{}; if (GuardedPE(im, f, &q)) imLen = q.R; }
        }
        if (anim && em) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("Montage_IsActive")))) { struct { UObject* M; bool R = false; } q{ em }; if (GuardedPE(anim, f, &q)) emAct = q.R; }
        int ft = 0; if (FProperty* p = m_bAct->GetPropertyByNameInChain(STR("FastTicks"))) { int32_t* v = p->ContainerPtrToValuePtr<int32_t>(m_bAct); if (v) ft = *v; }
        wchar_t s2[600];
        swprintf_s(s2, 600, L"t=%llu slots=%d hand=%d pda=%d bag=%d IM=%s play=%d pos=%.2f len=%.2f EM=%s act=%d FM=%s FT=%d LAT=%.2f FrT=%.2f pose=%s LS=%s",
            now % 100000, slots, CallByte(m_bPawn, STR("GetMainHandEquipType")), CallBool(m_bPawn, STR("IsUsingPDA")), CallBool(m_bPawn, STR("IsUsingBackpack")),
            nm(im).c_str(), imPlay, imPos, imLen, nm(em).c_str(), emAct, nm(fm).c_str(), ft, DblVar(m_bAct, STR("LastActionTime")), DblVar(m_bAct, STR("FrozenT")),
            nm(ObjProp(m_bAct, STR("PoseMontage"))).c_str(), nm(ObjProp(m_bAct, STR("LastStarted"))).c_str());
        Output::send<LogLevel::Verbose>(STR("[CampProbe] st {}\n"), StringType(s2));
    }
    // visible widgets while seated (build 49: which widget shows the "Play guitar" hint; does the Sleeping Bag Mod
    // popup exist): once a second, log the classes that appear / disappear
    std::set<StringType> m_wLast; uint64_t m_wT = 0;
    void Widgets(uint64_t now) {
        if (now - m_wT < 1000) return; m_wT = now;
        bool active = m_bSeated == 1 || (m_bAct && !m_bAct->IsUnreachable() && BoolVar(m_bAct, STR("VanillaHold")));
        if (!active) { m_wLast.clear(); return; }
        std::set<StringType> cur;
        UObjectGlobals::ForEachUObject([&](UObject* o, int32, int32) {
            if (!o || o->IsUnreachable()) return LoopAction::Continue;
            UClass* c = o->GetClassPrivate(); bool isUW = false;
            for (UStruct* w = c; w; w = w->GetSuperStruct()) if (w->GetName() == StringType(STR("UserWidget"))) { isUW = true; break; }
            if (!isUW) return LoopAction::Continue;
            StringType on = o->GetName(); if (on.rfind(STR("Default__"), 0) == 0) return LoopAction::Continue;
            if (CallBool(o, STR("IsVisible")) == 1) {
                int inVp = CallBool(o, STR("IsInViewport"));
                cur.insert(c->GetName() + (inVp == 1 ? STR("[vp]") : STR("")));
            }
            return LoopAction::Continue;
        });
        StringType add, rem;
        for (auto& n : cur) if (!m_wLast.count(n)) add += n + STR(" ");
        for (auto& n : m_wLast) if (!cur.count(n)) rem += n + STR(" ");
        if (!add.empty() || !rem.empty()) Output::send<LogLevel::Verbose>(STR("[CampProbe] widgets +[{}] -[{}]\n"), add, rem);
        m_wLast = cur;
    }
    void Burst(uint64_t now) {
        // Widgets(now);   // build 50: ProcessEvent on every widget crashed the game when a context menu opened
        MontageEvents(now);
        Trace(now);
        m_frame++;
        if (!m_bPawn || m_bSeated != 1) { m_burst = 0; return; }
        if (m_burst == 0) { if (now - m_lastBurst < 10000) return; m_lastBurst = now; m_burst = 40; }
        m_burst--;
        if (m_bPawn->IsUnreachable()) { m_bPawn = nullptr; return; }
        UObject* ctl = ObjProp(m_bPawn, STR("Controller")); UObject* cam = ObjProp(m_bPawn, STR("Camera")); UObject* mesh = ObjProp(m_bPawn, STR("Mesh"));
        FR cr{}, vr{}; double pos = -1;
        if (ctl) if (FProperty* p = ctl->GetPropertyByNameInChain(STR("ControlRotation"))) { FR* v = p->ContainerPtrToValuePtr<FR>(ctl); if (v) cr = *v; }
        if (cam) if (UFunction* f = cam->GetFunctionByNameInChain(FName(STR("K2_GetComponentRotation")))) { struct { FR R; } q{}; if (GuardedPE(cam, f, &q)) vr = q.R; }
        UObject* anim = nullptr;
        if (mesh) if (UFunction* f = mesh->GetFunctionByNameInChain(FName(STR("GetAnimInstance")))) { struct { UObject* R = nullptr; } q; if (GuardedPE(mesh, f, &q)) anim = q.R; }
        UObject* mont = (m_bAct && !m_bAct->IsUnreachable()) ? ObjProp(m_bAct, STR("PoseMontage")) : nullptr;
        if (anim && mont) if (UFunction* f = anim->GetFunctionByNameInChain(FName(STR("Montage_GetPosition")))) { struct { UObject* M; float R = -1; } q{}; q.M = mont; if (GuardedPE(anim, f, &q)) pos = q.R; }
        double ccp = -1;
        if (anim) if (FProperty* p = anim->GetPropertyByNameInChain(STR("CameraData"))) if (FStructProperty* sp = CastField<FStructProperty>(p)) {
            uint8_t* base = p->ContainerPtrToValuePtr<uint8_t>(anim);
            for (FProperty* q : TFieldRange<FProperty>(sp->GetStruct(), EFieldIterationFlags::None))
                if (q->GetName() == StringType(STR("ClampedControlPitch"))) { float* f = q->ContainerPtrToValuePtr<float>(base); if (f) ccp = *f; }
        }
        wchar_t b[256];
        swprintf_s(b, 256, L"f=%llu ctlP=%.3f ctlY=%.3f camP=%.3f camY=%.3f pos=%.4f ccp=%.4f", m_frame, cr.P, cr.Y, vr.P, vr.Y, pos, ccp);
        Output::send<LogLevel::Verbose>(STR("[CampProbe] burst {}\n"), StringType(b));
    }

    // look-input gaps: ControlRotation stops changing for > 60 ms in the middle of a mouse move (build 34: "drops"
    // after the guitar). Cheap: property reads on cached objects, no object-array scans.
    UObject* m_cPawn = nullptr; UObject* m_cAct = nullptr; uint64_t m_cRefresh = 0;
    FR m_gLast{}; uint64_t m_gChange = 0, m_gMoveStart = 0; bool m_gMoving = false; int m_gIgnLook = -2;
    void Gaps(uint64_t now) {
        if (!m_cPawn || m_cPawn->IsUnreachable()) return;
        UObject* ctl = ObjProp(m_cPawn, STR("Controller")); if (!ctl) return;
        FR cr{}; if (FProperty* p = ctl->GetPropertyByNameInChain(STR("ControlRotation"))) { FR* v = p->ContainerPtrToValuePtr<FR>(ctl); if (v) cr = *v; }
        bool changed = fabs(cr.Y - m_gLast.Y) > 1e-4 || fabs(cr.P - m_gLast.P) > 1e-4;
        if (changed) {
            if (m_gMoving && now - m_gChange > 60 && now - m_gChange < 400)
                Output::send<LogLevel::Verbose>(STR("[CampProbe] gap {}ms (moving {}ms) seated={}\n"), now - m_gChange, m_gChange - m_gMoveStart, m_bSeated);
            if (!m_gMoving) m_gMoveStart = now;
            m_gMoving = true; m_gChange = now; m_gLast = cr;
        } else if (m_gMoving && now - m_gChange >= 400) m_gMoving = false;
        // dropped input: the pawn says it had camera input last tick but ControlRotation did not move; hitches:
        // world delta seconds. Summarised once a second (counts), not per frame.
        {
            static uint64_t s_lastSum = 0; static int s_upd = 0, s_inputTicks = 0, s_dropTicks = 0, s_hitch = 0; static double s_maxDt = 0;
            static FR s_prev{}; static bool s_prevHad = false;
            bool had = false; FR lci{};
            FProperty* hp = m_cPawn->GetPropertyByNameInChain(STR("bHadCameraInputLastTick")); if (!hp) hp = m_cPawn->GetPropertyByNameInChain(STR("HadCameraInputLastTick"));
            if (FProperty* p = hp) if (FBoolProperty* bp = CastField<FBoolProperty>(p)) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(m_cPawn); if (raw) had = bp->GetPropertyValue(raw); }
            if (FProperty* p = m_cPawn->GetPropertyByNameInChain(STR("LastCameraInput"))) { FR* v = p->ContainerPtrToValuePtr<FR>(m_cPawn); if (v) lci = *v; }
            double dt = -1;
            static UFunction* s_wds = nullptr; static UObject* s_gs = nullptr;
            if (!s_gs) { s_gs = UObjectGlobals::StaticFindObject<UObject*>(nullptr, nullptr, STR("/Script/Engine.Default__GameplayStatics")); if (s_gs) s_wds = s_gs->GetFunctionByNameInChain(FName(STR("GetWorldDeltaSeconds"))); }
            if (s_gs && s_wds) { struct { UObject* W; double R; } q{}; q.W = m_cPawn; if (GuardedPE(s_gs, s_wds, &q)) dt = q.R; }
            s_upd++;
            bool moved = fabs(cr.Y - s_prev.Y) > 1e-5 || fabs(cr.P - s_prev.P) > 1e-5;
            bool inputNonZero = fabs(lci.Y) > 1e-4 || fabs(lci.P) > 1e-4;
            if (had && inputNonZero) { s_inputTicks++; if (!moved && s_prevHad) s_dropTicks++; }
            s_prevHad = had && inputNonZero; s_prev = cr;
            if (dt > s_maxDt) s_maxDt = dt;
            if (dt > 0.045) s_hitch++;
            if (now - s_lastSum >= 1000) {
                if (s_inputTicks > 0 || s_hitch > 0)
                    Output::send<LogLevel::Verbose>(STR("[CampProbe] look1s seated={} updates={} inputTicks={} stalledWithInput={} hitchUpdates={} maxDt={}ms lci=({},{})\n"),
                        m_bSeated, s_upd, s_inputTicks, s_dropTicks, s_hitch, (int)(s_maxDt * 1000), (int)(lci.P * 100), (int)(lci.Y * 100));
                s_lastSum = now; s_upd = s_inputTicks = s_dropTicks = s_hitch = 0; s_maxDt = 0;
            }
        }
        int ign = CallBool(ctl, STR("IsLookInputIgnored"));
        if (ign != m_gIgnLook) { Output::send<LogLevel::Verbose>(STR("[CampProbe] lookIgnored={} t={}\n"), ign, now % 100000); m_gIgnLook = ign; }
    }

    // ---- v1.0.0 "can't save after a sit": every property of the pawn, its controller and their components, before
    // the sit vs 3 s after standing up; differences logged once ("[CampProbe] diff ...") ----
    using Snap = std::vector<std::pair<StringType, StringType>>;
    Snap m_base; std::vector<Snap> m_ring; bool m_inSit = false; uint64_t m_idleSince = 0, m_baseT = 0;
    static StringType PropVal(UObject* o, FProperty* p) {
        uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(o); if (!raw) return STR("?");
        if (FBoolProperty* b = CastField<FBoolProperty>(p)) return b->GetPropertyValue(raw) ? STR("1") : STR("0");
        if (CastField<FObjectProperty>(p)) { UObject* v = *reinterpret_cast<UObject**>(raw); return v ? v->GetName() : StringType(STR("null")); }
        if (CastField<FArrayProperty>(p)) return StringType(STR("n=")) + std::to_wstring(*reinterpret_cast<int32_t*>(raw + 8));
        int32_t sz = p->GetSize(); if (sz > 64) sz = 64;
        wchar_t h[140]; int k = 0; for (int i = 0; i < sz && k < 130; ++i) k += swprintf_s(h + k, 140 - k, L"%02x", raw[i]);
        return StringType(h);
    }
    static void SnapObj(UObject* o, const StringType& tag, Snap& out) {
        if (!o || o->IsUnreachable()) return;
        for (FProperty* p : o->GetClassPrivate()->ForEachPropertyInChain()) out.emplace_back(tag + STR(".") + p->GetName(), PropVal(o, p));
    }
    static void SnapTree(UObject* o, const StringType& tag, Snap& out) {
        SnapObj(o, tag, out);
        if (!o) return;
        StringType path = o->GetPathName() + STR(".");
        for (FProperty* p : o->GetClassPrivate()->ForEachPropertyInChain()) {
            if (!CastField<FObjectProperty>(p)) continue;
            UObject* v = *reinterpret_cast<UObject**>(p->ContainerPtrToValuePtr<uint8_t>(o));
            if (v && !v->IsUnreachable() && v->GetPathName().rfind(path, 0) == 0) SnapObj(v, tag + STR(".") + p->GetName(), out);
        }
    }
    Snap TakeSnap(UObject* pawn) {
        Snap s; SnapTree(pawn, STR("PC"), s); SnapTree(ObjProp(pawn, STR("Controller")), STR("Ctl"), s);
        // the save lock may live outside the pawn: the save managers and the seat actors
        for (const wchar_t* cn : { L"SaveLoadManager", L"AutoSaveManager" }) SnapTree(UObjectGlobals::FindFirstOf(cn), cn, s);
        std::vector<UObject*> cas; UObjectGlobals::FindAllOf(STR("BP_PlayerContextualAction_C"), cas);
        for (UObject* c : cas) if (c && !c->IsUnreachable()) SnapTree(c, STR("CA:") + c->GetName(), s);
        return s;
    }
    uint64_t m_seatT = 0; bool m_seatDone = false;
    void LogDiff(UObject* pawn, const wchar_t* tag) {
        Snap after = TakeSnap(pawn); int n = 0;
        for (auto& a : after) {
            bool found = false;
            for (auto& b : m_base) if (a.first == b.first) { found = true; if (a.second != b.second) { Output::send<LogLevel::Verbose>(STR("[CampProbe] {} {} : {} -> {}\n"), tag, a.first, b.second, a.second); ++n; } break; }
            if (!found) { Output::send<LogLevel::Verbose>(STR("[CampProbe] {} NEW {} = {}\n"), tag, a.first, a.second); ++n; }
        }
        Output::send<LogLevel::Verbose>(STR("[CampProbe] {} done: {} changed of {} (base {})\n"), tag, n, after.size(), m_base.size());
    }
    void StateDiff(UObject* pawn, int seated, uint64_t now) {
        if (!pawn || pawn->IsUnreachable()) return;
        bool busy = seated == 1 || (m_cAct && !m_cAct->IsUnreachable() && (BoolVar(m_cAct, STR("VanillaHold")) || BoolVar(m_cAct, STR("Standing")) || BoolVar(m_cAct, STR("SeatedMode"))));
        // the vanilla sit-in runs ~4 s before any flag is set: the baseline is the snapshot from 6-8 s before
        if (busy) {
            if (!m_inSit && !m_ring.empty()) { m_inSit = true; m_seatT = 0; m_seatDone = false; m_base = m_ring.front(); Output::send<LogLevel::Verbose>(STR("[CampProbe] diff baseline frozen ({} props)\n"), m_base.size()); }
            bool sm = m_cAct && !m_cAct->IsUnreachable() && BoolVar(m_cAct, STR("SeatedMode"));
            if (m_inSit && sm && !m_seatDone) { if (m_seatT == 0) m_seatT = now; else if (now - m_seatT > 3000) { m_seatDone = true; LogDiff(pawn, L"diffSeated"); } }
            m_idleSince = 0; return;
        }
        if (m_idleSince == 0) m_idleSince = now;
        if (!m_inSit) { if (now - m_baseT > 2000) { m_ring.push_back(TakeSnap(pawn)); if (m_ring.size() > 4) m_ring.erase(m_ring.begin()); m_baseT = now; } return; }
        if (now - m_idleSince < 3000) return;
        LogDiff(pawn, L"diff");
        m_inSit = false; m_ring.clear(); m_baseT = 0;
    }

    auto on_update() -> void override {
        uint64_t now = GetTickCount64();
        Gaps(now);
        Burst(now);
        if (now - m_lastLive < 500) return;
        m_lastLive = now;
        // cached lookups: scan the object array only when a cached object is gone, or every 15 s
        if (!m_cPawn || m_cPawn->IsUnreachable() || now - m_cRefresh > 15000) {
            m_cRefresh = now;
            m_cPawn = UObjectGlobals::FindFirstOf(STR("PC")); if (m_cPawn && m_cPawn->IsUnreachable()) m_cPawn = nullptr;
            m_cAct = UObjectGlobals::FindFirstOf(STR("BP_ImmCampActor_C"));
        }
        UObject* pawn = m_cPawn;
        int seated = pawn ? SeatedFlag(pawn) : -1;
        StringType state = StringType(STR("pawn=")) + (pawn ? STR("1") : STR("0")) + STR(" seated=") + std::to_wstring(seated);
        if (state != m_lastState || now - m_lastHb > 30000) {
            m_lastState = state; m_lastHb = now;
            Output::send<LogLevel::Verbose>(STR("[CampProbe] {}\n"), state);
        }
        if (seated != 1 && m_cAct && !m_cAct->IsUnreachable()) {
            UObject* act = m_cAct;
            if (FProperty* p = act->GetPropertyByNameInChain(STR("SeatedMode")))
                if (FBoolProperty* bp = CastField<FBoolProperty>(p)) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(act); if (raw && bp->GetPropertyValue(raw)) seated = 1; }
        }
        m_bPawn = pawn; m_bSeated = seated; m_bAct = m_cAct;
        if (pawn) Body(pawn, seated, now);
        StateDiff(pawn, seated, now);
        if (seated != 1) { if (m_sitStart != 0) ScanContexts(STR("stand")); m_sitStart = 0; m_scans = 0; return; }
        if (m_sitStart == 0) m_sitStart = now;
        if (m_scans == 0 && now - m_sitStart >= 500) { m_scans = 1; ScanContexts(STR("sit+0.5s")); }
        else if (m_scans == 1 && now - m_sitStart >= 3000) { m_scans = 2; ScanContexts(STR("sit+3s")); }
        static UObject* s_pi = nullptr; static uint64_t s_piT = 0;
        if (!s_pi || s_pi->IsUnreachable() || now - s_piT > 15000) { s_piT = now; s_pi = UObjectGlobals::FindFirstOf(STR("EnhancedPlayerInput")); }
        UObject* pi = s_pi;
        StringType live; int total = -1;
        bool ok = pi && ReadMappings(pi, STR("EnhancedActionMappings"), true, &live, &total);
        StringType line = StringType(STR("ok=")) + (ok ? STR("1") : STR("0")) + STR(" total=") + std::to_wstring(total) + STR(" [") + live + STR("]");
        if (line != m_lastLiveStr) {
            m_lastLiveStr = line;
            Output::send<LogLevel::Verbose>(STR("[CampProbe] live {} input={}\n"), line, pi ? pi->GetFullName() : StringType(STR("null")));
        }
    }
};

#define MOD_API __declspec(dllexport)
extern "C" {
    MOD_API CppUserModBase* start_mod() { return new ImmCampProbe(); }
    MOD_API void uninstall_mod(CppUserModBase* mod) { delete mod; }
}
