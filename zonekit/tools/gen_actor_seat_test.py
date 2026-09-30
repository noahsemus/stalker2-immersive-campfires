"""Generates the BP_ImmCampActor event graph for the own-seated-mode proof (replace the graph with it).

Home key toggles:
  not seated -> Cast To PC(Get Player Pawn) -> Play Anim Montage(MG_fp_ca_gd_bonfire, 1.0, "In") -> SeatedMode = true
  seated     -> Cast To PC(Get Player Pawn) -> Stop Anim Montage(MG_fp_ca_gd_bonfire)      -> SeatedMode = false
The vanilla sit plays this same FullBody montage (In -> Idle loop -> Out) inside an interaction, and
the interaction is what blocks PDA / backpack (builds 1-5). Played by us, the game is not in an
interaction, so the question this build answers is whether P / I / quick slots work natively
while the seated pose plays, and how it looks.
Usage: python gen_actor_seat_test.py <out.txt>
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from bp_t3d import cls, TGT, write
from bp_graph import Graph, Node

PC = cls("/Script/Stalker2.PC")
CHAR = cls("/Script/Engine.Character")
PAWN = cls("/Script/Engine.Pawn")
OBJ = cls("/Script/CoreUObject.Object")
GS = cls("/Script/Engine.GameplayStatics")
MONT = cls("/Script/Engine.AnimMontage")
KEY = "\"/Script/CoreUObject.ScriptStruct'/Script/InputCore.Key'\""
SELF = "\"/Script/Engine.BlueprintGeneratedClass'/ImmersiveCampfires/Runtime/BP_ImmCampActor.BP_ImmCampActor_C'\""
SIT = "/Game/_STALKER2/Animations/Player/AnimSequences/contextual_action/sit_ground_bonfire/MG_fp_ca_gd_bonfire.MG_fp_ca_gd_bonfire"
BG = "/Script/BlueprintGraph."
GET_TIP = 'PinToolTip="Retrieves the value of the variable, can use instead of a separate Get node",'

g = Graph()
seq = [0]


def nm(kind):
    seq[0] += 1
    return f"{kind}_{900 + seq[0]}"


def exec_pins(n):
    n.pin("execute", "exec")
    n.pin("then", "exec", out=True)
    return n


def player_cast(x, y, label):
    gp = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x - 280, y + 200, "",
              ["bIsPureFunc=True", f"FunctionReference=(MemberParent={GS},MemberName=\"GetPlayerPawn\")"])
    gp.pin("self", "object", sub=GS, hidden=True, extra='DefaultObject="/Script/Engine.Default__GameplayStatics",')
    gp.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
    gp.pin("PlayerIndex", "int", extra='DefaultValue="0",')
    gp.pin("ReturnValue", "object", sub=PAWN, out=True)
    c = exec_pins(Node(g, BG + "K2Node_DynamicCast", nm("K2Node_DynamicCast"), x, y, f"player ({label})",
                       [f"TargetType=\"/Script/CoreUObject.Class'/Script/Stalker2.PC'\""]))
    c.pin("CastFailed", "exec", out=True)
    c.pin("Object", "object", sub=OBJ)
    c.pin("AsPC", "object", sub=PC, out=True)
    c.pin("bSuccess", "bool", out=True)
    g.link(gp["ReturnValue"], c["Object"])
    return c


def set_seated(x, y, value, comment):
    n = exec_pins(Node(g, BG + "K2Node_VariableSet", nm("K2Node_VariableSet"), x, y, comment,
                       ['VariableReference=(MemberName="SeatedMode",bSelfContext=True)']))
    n.pin("SeatedMode", "bool", extra=f'DefaultValue="{value}",')
    n.pin("Output_Get", "bool", out=True, extra=GET_TIP)
    n.pin("self", "object", sub=SELF, hidden=True, extra=TGT)
    return n


g.box("EdGraphNode_Comment_900", -60, -120, 2000, 900, "Seated mode test (Home key)")

key = Node(g, BG + "K2Node_InputKey", nm("K2Node_InputKey"), 0, 0, "",
           ['InputKey=Home'])
key.pin("Pressed", "exec", out=True)
key.pin("Released", "exec", out=True)
key.pin("Key", "struct", sub=KEY, out=True)

get = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), 60, 180, "",
           ['VariableReference=(MemberName="SeatedMode",bSelfContext=True)'])
get.pin("SeatedMode", "bool", out=True)
get.pin("self", "object", sub=SELF, hidden=True, extra=TGT)

br = Node(g, BG + "K2Node_IfThenElse", nm("K2Node_IfThenElse"), 300, 0, "already seated?")
br.pin("execute", "exec")
br.pin("Condition", "bool", extra='DefaultValue="true",')
br.pin("then", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "true", "true"),')
br.pin("else", "exec", out=True, extra='PinFriendlyName=NSLOCTEXT("K2Node", "false", "false"),')
g.link(key["Pressed"], br["execute"])
g.link(get["SeatedMode"], br["Condition"])

# not seated -> sit
c1 = player_cast(820, 360, "sit")
g.link(br["else"], c1["execute"])
play = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), 1100, 360, "sit: play bonfire montage",
                      [f"FunctionReference=(MemberParent={CHAR},MemberName=\"PlayAnimMontage\")"]))
play.pin("self", "object", sub=CHAR, extra=TGT)
play.pin("AnimMontage", "object", sub=MONT, extra=f'DefaultObject="{SIT}",')
play.pin("InPlayRate", "real", subcat="float", extra='DefaultValue="1.000000",')
play.pin("StartSectionName", "name", extra='DefaultValue="In",')
play.pin("ReturnValue", "real", subcat="float", out=True)
g.link(c1["AsPC"], play["self"])
g.link(c1["then"], play["execute"])
s1 = set_seated(1500, 360, "true", "seated: on")
g.link(play["then"], s1["execute"])

# seated -> stand
c2 = player_cast(820, 0, "stand")
g.link(br["then"], c2["execute"])
stop = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), 1100, 0, "stand: stop bonfire montage",
                      [f"FunctionReference=(MemberParent={CHAR},MemberName=\"StopAnimMontage\")"]))
stop.pin("self", "object", sub=CHAR, extra=TGT)
stop.pin("AnimMontage", "object", sub=MONT, extra=f'DefaultObject="{SIT}",')
g.link(c2["AsPC"], stop["self"])
g.link(c2["then"], stop["execute"])
s2 = set_seated(1500, 0, "false", "seated: off")
g.link(stop["then"], s2["execute"])

write(sys.argv[1], g.text())
print("ok", len(g.nodes), "nodes")
