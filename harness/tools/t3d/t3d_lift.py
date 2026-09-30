"""Lift graph nodes out of an exported Blueprint / AnimBlueprint T3D (AssetExportTask) into paste text.

An export writes every object twice: a declaration pass (`Begin Object Class=... Name=...`) and a
definition pass (`Begin Object Name=...` with properties and pins). Paste text wants one block per
node with the class on it, and nested sub-objects (e.g. AnimGraphNodeBinding_Base) declared and
defined inside. lift() builds that block, renames the node, gives every pin a fresh PinId, drops
the old links and lets the caller set new ones.
"""
import re
from bp_t3d import G


def _blocks(lines, export_path):
    """Return (class, definition lines) for the object whose ExportPath ends with export_path."""
    cls, body = None, None
    for i, l in enumerate(lines):
        m = re.match(r'(\s*)Begin Object (Class=(\S+) )?Name="([^"]+)" ExportPath="([^"]+)"', l)
        if not m or not m.group(5).rstrip("'").endswith(export_path):
            continue
        ind = m.group(1)
        j = i + 1
        blk = []
        while not (lines[j].startswith(ind + "End Object") and len(lines[j]) - len(lines[j].lstrip()) == len(ind)):
            blk.append(lines[j])
            j += 1
        if m.group(3):
            cls = m.group(3)
        else:
            body = blk
    return cls, body


class Lifted:
    def __init__(self, export_file, export_path, new_name, x, y, replace=None):
        lines = open(export_file, encoding="utf-8", errors="replace").read().splitlines()
        self.cls, body = _blocks(lines, export_path)
        assert self.cls and body, export_path
        self.name, self.links, self.pin_ids = new_name, {}, {}
        base_ind = len(body[0]) - len(body[0].lstrip())
        out, sub_decl = [], []
        k = 0
        while k < len(body):
            l = body[k]
            s = l.strip()
            m = re.match(r'Begin Object Name="([^"]+)" ExportPath="([^"]+)"', s)
            if m and len(l) - len(l.lstrip()) == base_ind:
                # nested sub-object definition: find its class from the declaration pass
                sub_path = m.group(2).split("'")[1] if "'" in m.group(2) else m.group(2)
                sub_cls, _ = _blocks(lines, sub_path.split(":")[-1])
                sub_decl.append(f'   Begin Object Class={sub_cls} Name="{m.group(1)}"')
                sub_decl.append("   End Object")
                blk = [f'   Begin Object Name="{m.group(1)}"']
                k += 1
                while not (body[k].strip() == "End Object" and len(body[k]) - len(body[k].lstrip()) == base_ind):
                    blk.append("   " + body[k].strip())
                    k += 1
                blk.append("   End Object")
                out += blk
            elif s.startswith("NodePosX="):
                out.append(f"   NodePosX={x}")
            elif s.startswith("NodePosY="):
                out.append(f"   NodePosY={y}")
            elif s.startswith("NodeGuid="):
                out.append(f"   NodeGuid={G()}")
            elif s.startswith("CustomProperties Pin"):
                pn = re.search(r'PinName="([^"]+)"', s).group(1)
                pid = G()
                self.pin_ids[pn] = pid
                s = re.sub(r"PinId=[0-9A-F]+", f"PinId={pid}", s)
                s = re.sub(r"LinkedTo=\([^)]*\),", "", s)
                out.append("   " + s)
            elif s.startswith("ErrorType=") or s.startswith("ErrorMsg="):
                pass
            else:
                out.append("   " + s)
            k += 1
        if replace:
            out = [replace(l) for l in out]
        self.lines = sub_decl + out

    def pin(self, name):
        return (self, name)

    def text(self):
        res = [f'Begin Object Class={self.cls} Name="{self.name}"']
        for l in self.lines:
            m = re.search(r'PinName="([^"]+)"', l) if "CustomProperties Pin" in l else None
            if m and m.group(1) in self.links:
                lk = "LinkedTo=(" + "".join(f"{n.name} {n.pin_ids[p]}," for n, p in self.links[m.group(1)]) + "),"
                l = l.replace("PersistentGuid=", lk + "PersistentGuid=", 1)
            res.append(l)
        res.append("End Object")
        return res


def link(a, a_pin, b, b_pin):
    a.links.setdefault(a_pin, []).append((b, b_pin))
    b.links.setdefault(b_pin, []).append((a, a_pin))
