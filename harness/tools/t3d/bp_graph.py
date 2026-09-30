"""Graph builder on top of bp_t3d: declare nodes and pins, link(a, b), emit paste text.

Links are written on both ends, so the pasted graph never depends on one-sided LinkedTo.
"""
from bp_t3d import G, head, comment_box, T, F, TGT


class Pin:
    def __init__(self, node, name, cat, sub="None", subcat="", out=False, hidden=False, adv=False, extra=""):
        self.node, self.name, self.cat, self.sub, self.subcat = node, name, cat, sub, subcat
        self.out, self.hidden, self.adv, self.extra, self.id, self.links = out, hidden, adv, extra, G(), []
        self.member_ref = ""   # e.g. MemberParent=...,MemberName="ReceiveTick" for an event's OutputDelegate
        self.container = "None"  # "Array" for array pins
        self.wrapper = False     # TSubclassOf function parameters
        self.ref = False         # by-reference parameter
        self.const = False

    def text(self):
        l = ("LinkedTo=(" + "".join(f"{p.node.name} {p.id}," for p in self.links) + "),") if self.links else ""
        d = 'Direction="EGPD_Output",' if self.out else ""
        return (f'   CustomProperties Pin (PinId={self.id},PinName="{self.name}",{self.extra}{d}'
                f'PinType.PinCategory="{self.cat}",PinType.PinSubCategory="{self.subcat}",'
                f'PinType.PinSubCategoryObject={self.sub},'
                + T.replace("PinType.PinSubCategoryMemberReference=()",
                            f"PinType.PinSubCategoryMemberReference=({self.member_ref})")
                   .replace("PinType.ContainerType=None", f"PinType.ContainerType={self.container}")
                   .replace("PinType.bIsUObjectWrapper=False", f"PinType.bIsUObjectWrapper={self.wrapper}")
                   .replace("PinType.bIsReference=False", f"PinType.bIsReference={self.ref}")
                   .replace("PinType.bIsConst=False", f"PinType.bIsConst={self.const}") + l
                + F % ("True" if self.hidden else "False", "True" if self.adv else "False"))


class Node:
    def __init__(self, graph, klass, name, x, y, comment="", body=()):
        self.klass, self.name, self.x, self.y, self.comment, self.body = klass, name, x, y, comment, list(body)
        self.pins = {}
        graph.nodes.append(self)

    def pin(self, name, cat, **kw):
        p = Pin(self, name, cat, **kw)
        self.pins[name] = p
        return p

    def __getitem__(self, name):
        return self.pins[name]

    def text(self):
        return head(self.klass, self.name, self.x, self.y, self.comment, self.body) + \
            [p.text() for p in self.pins.values()] + ["End Object"]


class Graph:
    def __init__(self):
        self.nodes, self.extra = [], []

    def link(self, a, b):
        a.links.append(b)
        b.links.append(a)

    def box(self, name, x, y, w, h, text):
        self.extra += comment_box(name, x, y, w, h, text)

    def text(self):
        out = list(self.extra)
        for n in self.nodes:
            out += n.text()
        return out
