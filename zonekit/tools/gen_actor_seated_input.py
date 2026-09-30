"""Generates the whole BP_ImmCampActor event graph (PLAN.md Layer 2) as paste text.

Per action (PDA, backpack):
  EnhancedInputAction <IA> (Started) -> Presses += 1 -> Cast To PC (Get Player Pawn)
  -> Branch PC.bInContextualAction -> Calls += 1
  -> CanInvBefore = PC.CanUseInventory() -> InteractBefore = PC.IsInteractionInProgress()
  -> TargetSaved = PC.GetInteractionTarget() -> HadTarget = IsValid(TargetSaved)
  -> PC.ResetInteractionTarget() -> InteractMid = PC.IsInteractionInProgress()
  -> PC.bInContextualAction = false -> PC.<StartUsePDA | StartUseBackpack>
  -> PC.bInContextualAction = true -> UsingAfter = PC.<IsUsingPDA | IsUsingBackpack>()
  -> PC.SetInteractionTarget(TargetSaved)
Build 3 showed Presses == Calls == 4 with nothing opening: the native call refuses while seated.
Build 4 cleared the seated flag around the call: no change; InteractBefore=1, CanInvBefore=1.
Build 5 also clears the interaction target around the call. Variables (added from Python): Presses, Calls (int); CanInvBefore,
InteractBefore, UsingAfter (bool).
Usage: python gen_actor_seated_input.py <out.txt>
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from bp_t3d import cls, TGT, write
from bp_graph import Graph, Node

PC = cls("/Script/Stalker2.PC")
PAWN = cls("/Script/Engine.Pawn")
OBJ = cls("/Script/CoreUObject.Object")
GS = cls("/Script/Engine.GameplayStatics")
KML = cls("/Script/Engine.KismetMathLibrary")
KSL = cls("/Script/Engine.KismetSystemLibrary")
ICOMP = cls("/Script/Stalker2.InteractionComponent")
SELF = "\"/Script/Engine.BlueprintGeneratedClass'/ImmersiveCampfires/Runtime/BP_ImmCampActor.BP_ImmCampActor_C'\""
IA_CLS = cls("/Script/EnhancedInput.InputAction")
IA_DIR = "/Game/_Stalker_2/data/input/InputActions/"
BG = "/Script/BlueprintGraph."
GET_TIP = 'PinToolTip="Retrieves the value of the variable, can use instead of a separate Get node",'

ACTIONS = [  # (box, IA, start fn, is-using fn, label, has page pin)
    ("Seated: PDA", "IA_OpenPDA", "StartUsePDA", "IsUsingPDA", "PDA", True),
    ("Seated: backpack", "IA_Inventory", "StartUseBackpack", "IsUsingBackpack", "backpack", False),
]

g = Graph()
seq = [0]


def nm(kind):
    seq[0] += 1
    return f"{kind}_{900 + seq[0]}"


def exec_pins(n):
    n.pin("execute", "exec")
    n.pin("then", "exec", out=True)
    return n


def self_var_set(var, cat, x, y, comment, member_parent=None, default=None):
    ref = (f'VariableReference=(MemberParent={member_parent},MemberName="{var}")' if member_parent
           else f'VariableReference=(MemberName="{var}",bSelfContext=True)')
    n = exec_pins(Node(g, BG + "K2Node_VariableSet", nm("K2Node_VariableSet"), x, y, comment, [ref]))
    n.pin(var, cat, extra=f'DefaultValue="{default}",' if default is not None else "")
    n.pin("Output_Get", cat, out=True, extra=GET_TIP)
    if member_parent:
        n.pin("self", "object", sub=PC, extra=TGT)
    else:
        n.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    return n


def counter(var, x, y, comment):
    gv = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x - 60, y + 180, "",
              [f'VariableReference=(MemberName="{var}",bSelfContext=True)'])
    gv.pin(var, "int", out=True)
    gv.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    add = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x + 100, y + 180, "",
               ["bIsPureFunc=True", f"FunctionReference=(MemberParent={KML},MemberName=\"Add_IntInt\")"])
    add.pin("self", "object", sub=KML, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetMathLibrary",')
    add.pin("A", "int", extra='DefaultValue="0",')
    add.pin("B", "int", extra='DefaultValue="1",')
    add.pin("ReturnValue", "int", out=True)
    s = self_var_set(var, "int", x, y, comment)
    g.link(gv[var], add["A"])
    g.link(add["ReturnValue"], s[var])
    return s


def pc_query(fn, x, y, as_pc):
    q = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, "",
             ["bIsPureFunc=True", f"FunctionReference=(MemberParent={PC},MemberName=\"{fn}\")"])
    q.pin("self", "object", sub=PC, extra=TGT)
    q.pin("ReturnValue", "bool", out=True)
    g.link(as_pc, q["self"])
    return q


for i, (box, ia, start_fn, using_fn, label, has_page) in enumerate(ACTIONS):
    y = i * 700
    g.box(f"EdGraphNode_Comment_{900 + i}", -60, y - 80, 5900, 560, box)

    ev = Node(g, "/Script/InputBlueprintNodes.K2Node_EnhancedInputAction", nm("K2Node_EnhancedInputAction"), 0, y, "",
              [f"InputAction=\"/Script/EnhancedInput.InputAction'{IA_DIR}{ia}.{ia}'\""])
    for e in ("Triggered", "Started", "Ongoing", "Canceled", "Completed"):
        ev.pin(e, "exec", out=True)
    ev.pin("ActionValue", "bool", out=True)
    ev.pin("ElapsedSeconds", "real", subcat="double", out=True, adv=True)
    ev.pin("TriggeredSeconds", "real", subcat="double", out=True, adv=True)
    ev.pin("InputAction", "object", sub=IA_CLS, out=True)

    presses = counter("Presses", 300, y, f"count press ({label})")
    g.link(ev["Started"], presses["execute"])

    gp = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), 420, y + 320, "",
              ["bIsPureFunc=True", f"FunctionReference=(MemberParent={GS},MemberName=\"GetPlayerPawn\")"])
    gp.pin("self", "object", sub=GS, hidden=True, extra='DefaultObject="/Script/Engine.Default__GameplayStatics",')
    gp.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
    gp.pin("PlayerIndex", "int", extra='DefaultValue="0",')
    gp.pin("ReturnValue", "object", sub=PAWN, out=True)

    cast = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), 700, y, f"player ({label})",
                          [f"TargetType=\"/Script/CoreUObject.Class'/Script/Stalker2.PC'\""]))
    cast.pin("CastFailed", "exec", out=True)
    cast.pin("Object", "object", sub=OBJ)
    cast.pin("AsPC", "object", sub=PC, out=True)
    cast.pin("bSuccess", "bool", out=True)
    as_pc = cast["AsPC"]
    g.link(presses["then"], cast["execute"])
    g.link(gp["ReturnValue"], cast["Object"])

    seated = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), 980, y + 220, "",
                  [f"VariableReference=(MemberParent={PC},MemberName=\"bInContextualAction\")"])
    seated.pin("bInContextualAction", "bool", out=True,
               extra='PinFriendlyName=NSLOCTEXT("UObjectDisplayNames", "PC:bInContextualAction", "In Contextual Action"),')
    seated.pin("self", "object", sub=PC, extra=TGT)
    g.link(as_pc, seated["self"])

    br = exec_pins(Node(g, BG + "K2Node_IfThenElse", nm("K2Node_IfThenElse"), 1220, y, f"seated? ({label})"))
    br.pins.pop("then")
    br.pin("Condition", "bool", extra='DefaultValue="true",')
    br.pin("then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "true", "true"),')
    br.pin("else", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "false", "false"),')
    g.link(cast["then"], br["execute"])
    g.link(seated["bInContextualAction"], br["Condition"])

    calls = counter("Calls", 1460, y, f"count call ({label})")
    g.link(br["then"], calls["execute"])

    x = 1780
    rec1 = self_var_set("CanInvBefore", "bool", x, y, f"record can use inventory ({label})")
    g.link(pc_query("CanUseInventory", x - 40, y + 220, as_pc)["ReturnValue"], rec1["CanInvBefore"])
    g.link(calls["then"], rec1["execute"])

    x += 320
    rec2 = self_var_set("InteractBefore", "bool", x, y, f"record interaction in progress ({label})")
    g.link(pc_query("IsInteractionInProgress", x - 40, y + 220, as_pc)["ReturnValue"], rec2["InteractBefore"])
    g.link(rec1["then"], rec2["execute"])

    # Build 5: the sit is an interaction in progress (build 4: InteractBefore=1, CanInvBefore=1).
    # Save the interaction target, clear it around the call, put it back afterwards.
    x += 320
    save = self_var_set("TargetSaved", "object", x, y, f"save interaction target ({label})")
    save.pins["TargetSaved"].sub = ICOMP
    save.pins["Output_Get"].sub = ICOMP
    gt = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x - 40, y + 220, "",
              ["bIsPureFunc=True", f"FunctionReference=(MemberParent={PC},MemberName=\"GetInteractionTarget\")"])
    gt.pin("self", "object", sub=PC, extra=TGT)
    gt.pin("ReturnValue", "object", sub=ICOMP, out=True)
    g.link(as_pc, gt["self"])
    g.link(gt["ReturnValue"], save["TargetSaved"])
    g.link(rec2["then"], save["execute"])

    x += 320
    had = self_var_set("HadTarget", "bool", x, y, f"record had target ({label})")
    iv = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x - 40, y + 220, "",
              ["bIsPureFunc=True", f"FunctionReference=(MemberParent={KSL},MemberName=\"IsValid\")"])
    iv.pin("self", "object", sub=KSL, hidden=True, extra='DefaultObject="/Script/Engine.Default__KismetSystemLibrary",')
    iv.pin("Object", "object", sub=OBJ)
    iv.pin("ReturnValue", "bool", out=True)
    g.link(save["Output_Get"], iv["Object"])
    g.link(iv["ReturnValue"], had["HadTarget"])
    g.link(save["then"], had["execute"])

    x += 320
    rst = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, f"clear interaction target ({label})",
                         [f"FunctionReference=(MemberParent={PC},MemberName=\"ResetInteractionTarget\")"]))
    rst.pin("self", "object", sub=PC, extra=TGT)
    g.link(as_pc, rst["self"])
    g.link(had["then"], rst["execute"])

    x += 320
    mid = self_var_set("InteractMid", "bool", x, y, f"record interaction after clear ({label})")
    g.link(pc_query("IsInteractionInProgress", x - 40, y + 220, as_pc)["ReturnValue"], mid["InteractMid"])
    g.link(rst["then"], mid["execute"])

    x += 320
    off = self_var_set("bInContextualAction", "bool", x, y, f"seated flag off ({label})", member_parent=PC, default="false")
    g.link(as_pc, off["self"])
    g.link(mid["then"], off["execute"])

    x += 320
    call = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, f"open {label} while seated",
                          [f"FunctionReference=(MemberParent={PC},MemberName=\"{start_fn}\")"]))
    call.pin("self", "object", sub=PC, extra=TGT)
    if has_page:
        call.pin("InitialPageType", "byte", sub="\"/Script/CoreUObject.Enum'/Script/Stalker2.EPDAPageType'\"",
                 extra='DefaultValue="None",')
    g.link(as_pc, call["self"])
    g.link(off["then"], call["execute"])

    x += 320
    on = self_var_set("bInContextualAction", "bool", x, y, f"seated flag on ({label})", member_parent=PC, default="true")
    g.link(as_pc, on["self"])
    g.link(call["then"], on["execute"])

    x += 320
    rec3 = self_var_set("UsingAfter", "bool", x, y, f"record opened ({label})")
    g.link(pc_query(using_fn, x - 40, y + 220, as_pc)["ReturnValue"], rec3["UsingAfter"])
    g.link(on["then"], rec3["execute"])

    x += 320
    put = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, f"restore interaction target ({label})",
                         [f"FunctionReference=(MemberParent={PC},MemberName=\"SetInteractionTarget\")"]))
    put.pin("self", "object", sub=PC, extra=TGT)
    put.pin("Target", "object", sub=ICOMP)
    ts = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x - 40, y + 220, "",
              ['VariableReference=(MemberName="TargetSaved",bSelfContext=True)'])
    ts.pin("TargetSaved", "object", sub=ICOMP, out=True)
    ts.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    g.link(as_pc, put["self"])
    g.link(ts["TargetSaved"], put["Target"])
    g.link(rec3["then"], put["execute"])

write(sys.argv[1], g.text())
print("ok", len(g.nodes), "nodes")
