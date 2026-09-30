"""Tiny T3D writer for Blueprint graph nodes (paste with Ctrl+V into a graph).

Format taken from nodes copied out of this kit's editor (ImmersiveDialogue sessions,
2026-09-22). Pins are written in full; links as LinkedTo=(NodeName PinId,).
"""
import uuid

G = lambda: uuid.uuid4().hex.upper()
T = ("PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),PinType.ContainerType=None,"
     "PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,"
     "PinType.bIsUObjectWrapper=False,PinType.bSerializeAsSinglePrecisionFloat=False,")
F = ("PersistentGuid=00000000000000000000000000000000,bHidden=%s,bNotConnectable=False,"
     "bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,bAdvancedView=%s,bOrphanedPin=False,)")
TGT = 'PinFriendlyName=NSLOCTEXT("K2Node", "Target", "Target"),'


def cls(path):
    """'/Script/Stalker2.PC' -> quoted class reference used in pin types."""
    return "\"/Script/CoreUObject.Class'%s'\"" % path


def pin(pid, name, cat, sub="None", subcat="", out=False, links=(), hidden=False, adv=False, extra=""):
    l = ("LinkedTo=(" + "".join(f"{n} {p}," for n, p in links) + "),") if links else ""
    d = 'Direction="EGPD_Output",' if out else ""
    return (f'   CustomProperties Pin (PinId={pid},PinName="{name}",{extra}{d}PinType.PinCategory="{cat}",'
            f'PinType.PinSubCategory="{subcat}",PinType.PinSubCategoryObject={sub},{T}{l}'
            + F % ("True" if hidden else "False", "True" if adv else "False"))


def head(klass, name, x, y, comment="", body=()):
    s = [f'Begin Object Class={klass} Name="{name}"'] + ["   " + b for b in body]
    s += [f"   NodePosX={x}", f"   NodePosY={y}"]
    if comment:
        s += ["   bCommentBubbleVisible=True", f'   NodeComment="{comment}"']
    s += [f"   NodeGuid={G()}"]
    return s


def comment_box(name, x, y, w, h, text):
    return [f'Begin Object Class=/Script/UnrealEd.EdGraphNode_Comment Name="{name}"',
            f"   NodePosX={x}", f"   NodePosY={y}", f"   NodeWidth={w}", f"   NodeHeight={h}",
            f'   NodeComment="{text}"', f"   NodeGuid={G()}", "End Object"]


def write(path, lines):
    open(path, "w", newline="\r\n", encoding="utf-8").write("\n".join(lines) + "\n")
