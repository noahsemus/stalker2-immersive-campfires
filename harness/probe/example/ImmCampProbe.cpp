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
        swprintf_s(b, 640, L"hand=%d hasMain=%d leftBusy=%d equippedNone=%d pda=%d bag=%d",
            CallByte(pawn, STR("GetMainHandEquipType")), CallBool(pawn, STR("HasItemInMainHand")), CallBool(pawn, STR("IsLeftHandBusy")),
            CallBool(pawn, STR("IsPlayerEquipedWithNone")), CallBool(pawn, STR("IsUsingPDA")), CallBool(pawn, STR("IsUsingBackpack")));
        Output::send<LogLevel::Verbose>(STR("[CampProbe] hands {}\n"), StringType(b));
    }

    // per-frame burst (40 frames every 10 s while seated): view pitch jitter at rest (builds 22-24)
    UObject* m_bPawn = nullptr; UObject* m_bAct = nullptr; int m_bSeated = 0; uint64_t m_lastBurst = 0; int m_burst = 0; uint64_t m_frame = 0;
    void Burst(uint64_t now) {
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
        wchar_t b[256];
        swprintf_s(b, 256, L"f=%llu ctlP=%.3f ctlY=%.3f camP=%.3f camY=%.3f pos=%.4f", m_frame, cr.P, cr.Y, vr.P, vr.Y, pos);
        Output::send<LogLevel::Verbose>(STR("[CampProbe] burst {}\n"), StringType(b));
    }

    auto on_update() -> void override {
        uint64_t now = GetTickCount64();
        Burst(now);
        if (now - m_lastLive < 500) return;   // twice a second (FindFirstOf scans the object array)
        m_lastLive = now;
        UObject* pawn = UObjectGlobals::FindFirstOf(STR("PC"));
        if (pawn && pawn->IsUnreachable()) pawn = nullptr;
        int seated = pawn ? SeatedFlag(pawn) : -1;
        StringType state = StringType(STR("pawn=")) + (pawn ? STR("1") : STR("0")) + STR(" seated=") + std::to_wstring(seated);
        if (state != m_lastState || now - m_lastHb > 30000) {
            m_lastState = state; m_lastHb = now;
            Output::send<LogLevel::Verbose>(STR("[CampProbe] {}\n"), state);
        }
        // Post-process layer class, logged on change (install at a seat / restore elsewhere).
        if (pawn) {
            UObject* mesh = nullptr;
            if (FProperty* p = pawn->GetPropertyByNameInChain(STR("Mesh"))) { UObject** v = p->ContainerPtrToValuePtr<UObject*>(pawn); if (v) mesh = *v; }
            StringType pp = STR("null");
            if (mesh) if (FProperty* p = mesh->GetPropertyByNameInChain(STR("PostProcessAnimInstance"))) { UObject** v = p->ContainerPtrToValuePtr<UObject*>(mesh); if (v && *v) pp = (*v)->GetClassPrivate()->GetName(); }
            if (pp != m_lastPP) { m_lastPP = pp; Output::send<LogLevel::Verbose>(STR("[CampProbe] layer now {} (seated={})\n"), pp, seated); }
        }
        // Our own seated mode (the takeover clears the vanilla flag): read SeatedMode off the actor.
        if (seated != 1) {
            if (UObject* act = UObjectGlobals::FindFirstOf(STR("BP_ImmCampActor_C"))) {
                if (FProperty* p = act->GetPropertyByNameInChain(STR("SeatedMode")))
                    if (FBoolProperty* bp = CastField<FBoolProperty>(p)) { uint8_t* raw = p->ContainerPtrToValuePtr<uint8_t>(act); if (raw && bp->GetPropertyValue(raw)) seated = 1; }
            }
        }
        m_bPawn = pawn; m_bSeated = seated; m_bAct = UObjectGlobals::FindFirstOf(STR("BP_ImmCampActor_C"));
        if (pawn) Body(pawn, seated, now);
        if (seated != 1) { if (m_sitStart != 0) ScanContexts(STR("stand")); m_sitStart = 0; m_scans = 0; return; }
        if (m_sitStart == 0) m_sitStart = now;
        if (m_scans == 0 && now - m_sitStart >= 500) { m_scans = 1; ScanContexts(STR("sit+0.5s")); }
        else if (m_scans == 1 && now - m_sitStart >= 3000) { m_scans = 2; ScanContexts(STR("sit+3s")); }
        UObject* pi = UObjectGlobals::FindFirstOf(STR("EnhancedPlayerInput"));
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
