#!/usr/bin/env python3
"""
Cross-check every tag the refactored ladder references against what the
export actually declares.  This is the check that catches the typo that
would otherwise only show up as a failed import in Studio 5000.

    python3 tools/check_refs.py

For each generated program it resolves every operand in every rung against:
  - the program's own tags
  - the controller context tags carried in the export
  - module I/O tags  (Name:I..., Name:O...)
  - the IAI_SCON_Axis parameter list, for Axis.<member> references
  - the SCON_Inputs / SCON_Outputs members, for <image>.<member> references
  - routine names, for JSR targets

Exits non-zero and lists anything that does not resolve.
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, "export")

# Instruction mnemonics that appear where an operand would otherwise be.
INSTRUCTIONS = {
    "XIC", "XIO", "OTE", "OTL", "OTU", "ONS", "OSR", "OSF", "AFI", "NOP",
    "MOV", "CPT", "ADD", "SUB", "MUL", "DIV", "CLR", "COP", "CPS", "FLL",
    "EQU", "NEQ", "GRT", "GEQ", "LES", "LEQ", "LIM", "MEQ",
    "TON", "TOF", "RTO", "RES", "JSR", "SBR", "RET", "GSV", "SSV",
    "IAI_SCON_Axis",
}

# Bare words that are GSV/SSV class and attribute names, not tags.
GSV_WORDS = {"Module", "FaultCode", "Program", "Task", "Controller"}

ATOMIC_MEMBERS = {
    "DN", "EN", "TT", "ACC", "PRE", "TimerEnable", "Reset",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
}


def load(path):
    return ET.parse(path).getroot()


def scon_members(root):
    out = {}
    for dt in root.iter("DataType"):
        name = dt.get("Name")
        if name in ("SCON_Inputs", "SCON_Outputs"):
            out[name] = {m.get("Name") for m in dt.findall("Members/Member")}
    return out


def udt_members(root):
    out = {}
    for dt in root.iter("DataType"):
        out[dt.get("Name")] = {m.get("Name") for m in dt.findall("Members/Member")}
    return out


def check(path):
    root = load(path)
    problems = []

    program = None
    for p in root.iter("Program"):
        if p.get("Use") != "Context":
            program = p
    if program is None:
        return ["%s: no target program" % os.path.basename(path)]

    prog_tags = {}
    for t in program.findall("Tags/Tag"):
        prog_tags[t.get("Name")] = t.get("DataType")

    # Alias tags carry no DataType of their own -- they resolve through
    # AliasFor, usually to a module I/O bit. Record them as present.
    ctrl_tags = {}
    for c in root.iter("Controller"):
        for t in c.findall("Tags/Tag"):
            ctrl_tags[t.get("Name")] = t.get("DataType") or "@alias"

    # Module names appear as the instance operand of GSV/SSV.
    modules = {m.get("Name") for m in root.iter("Module")}

    routines = {r.get("Name") for r in program.iter("Routine")}
    scon = scon_members(root)
    udts = udt_members(root)

    aoi_params = {}
    for aoi in root.iter("AddOnInstructionDefinition"):
        aoi_params[aoi.get("Name")] = {
            p.get("Name") for p in aoi.iter("Parameter")}
        aoi_params[aoi.get("Name")] |= {
            l.get("Name") for l in aoi.iter("LocalTag")}

    def resolve(operand, where):
        raw = operand.strip()
        if not raw or raw in INSTRUCTIONS or raw in GSV_WORDS:
            return
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", raw) or raw == "?":
            return
        # arithmetic expression inside CPT -- pull the identifiers out
        if re.search(r"[-+*/()]", raw) and not re.match(r"^[A-Za-z_]\w*\[", raw):
            for ident in re.findall(r"[A-Za-z_]\w*(?:[.\[][^\s,]*)?", raw):
                resolve(ident, where)
            return

        base = re.split(r"[.\[]", raw, 1)[0]
        rest = raw[len(base):]

        # module tag, e.g. IAI_UpStacker:I or IS3800:I.InspectionResults[96]
        if ":" in base:
            return
        if base.endswith(":I") or base.endswith(":O"):
            return

        dtype = prog_tags.get(base) or ctrl_tags.get(base)
        if dtype is None:
            if base in routines or base in modules:
                return
            problems.append("%s: unknown tag %r (in %s)" % (
                os.path.basename(path), base, where))
            return

        # member check, one level deep, where we can
        m = re.match(r"^\.([A-Za-z_]\w*)", rest)
        if not m:
            return
        member = m.group(1)
        if member in ATOMIC_MEMBERS or dtype == "@alias":
            return
        if dtype in aoi_params:
            if member not in aoi_params[dtype]:
                problems.append("%s: %s has no parameter %r (in %s)" % (
                    os.path.basename(path), dtype, member, where))
            return
        if dtype in scon:
            if member not in scon[dtype]:
                problems.append("%s: %s has no member %r (in %s)" % (
                    os.path.basename(path), dtype, member, where))
            return
        if dtype in udts and udts[dtype] and member not in udts[dtype]:
            problems.append("%s: %s has no member %r (in %s)" % (
                os.path.basename(path), dtype, member, where))

    n_rungs = 0
    for routine in program.iter("Routine"):
        rname = routine.get("Name")
        for rung in routine.iter("Rung"):
            n_rungs += 1
            text = (rung.findtext("Text") or "").strip()
            where = "%s rung %s" % (rname, rung.get("Number"))
            for instr, args in re.findall(r"([A-Za-z_]\w*)\(([^()]*(?:\([^()]*\)[^()]*)*)\)", text):
                if instr not in INSTRUCTIONS:
                    problems.append("%s: unknown instruction %r (in %s)" % (
                        os.path.basename(path), instr, where))
                depth, cur, args_list = 0, "", []
                for ch in args:
                    if ch == "," and depth == 0:
                        args_list.append(cur); cur = ""
                        continue
                    if ch in "([":
                        depth += 1
                    elif ch in ")]":
                        depth -= 1
                    cur += ch
                args_list.append(cur)
                for a in args_list:
                    resolve(a, where)

    print("%-46s %2d routines %3d rungs %3d program tags" % (
        os.path.basename(path), len(routines), n_rungs, len(prog_tags)))
    return problems


ST_KEYWORDS = {
    "IF", "THEN", "ELSE", "ELSIF", "END_IF", "CASE", "OF", "END_CASE",
    "FOR", "TO", "DO", "END_FOR", "WHILE", "END_WHILE", "REPEAT", "UNTIL",
    "AND", "OR", "NOT", "XOR", "MOD", "TRUE", "FALSE",
    "TONR", "TON", "TOF", "RTO", "CTU", "CTD",
}

TIMER_MEMBERS = {"PRE", "ACC", "DN", "EN", "TT", "TimerEnable", "Reset"}


def strip_st_comments(text):
    """Remove (* *) comments, tracking depth, and report any nesting.

    Logix does not handle nested (* *) reliably, so a nested open is
    reported as a problem rather than quietly accepted.
    """
    out, nested = [], []
    depth, i, line = 0, 0, 1
    while i < len(text):
        if text.startswith("(*", i):
            depth += 1
            if depth > 1:
                nested.append((line, text[i:i + 50].split("\n")[0]))
            i += 2
            continue
        if text.startswith("*)", i):
            depth = max(0, depth - 1)
            i += 2
            continue
        if text[i] == "\n":
            line += 1
            out.append("\n")
        elif depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out), nested, depth


def check_aoi_st(path):
    """Every identifier in the AOI's ST must be a parameter, a local, or a
    keyword; every .member must exist on its type."""
    root = load(path)
    problems = []

    aoi = next(iter(root.iter("AddOnInstructionDefinition")), None)
    if aoi is None:
        return ["%s: no AOI definition" % os.path.basename(path)]

    names = {p.get("Name"): p.get("DataType") for p in aoi.iter("Parameter")}
    names.update({l.get("Name"): l.get("DataType") for l in aoi.iter("LocalTag")})
    scon = scon_members(root)

    n_lines = 0
    for routine in aoi.iter("Routine"):
        rname = routine.get("Name")
        text = "\n".join(l.text or "" for l in routine.iter("Line"))
        n_lines += len(list(routine.iter("Line")))

        code, nested, depth = strip_st_comments(text)
        for line_no, snippet in nested:
            problems.append("%s: %s line %d has a nested (* *) comment: %s"
                            % (os.path.basename(path), rname, line_no, snippet))
        if depth != 0:
            problems.append("%s: %s has an unterminated (* comment"
                            % (os.path.basename(path), rname))

        seen = set()
        for m in re.finditer(r"\b([A-Za-z_]\w*)(?:\.([A-Za-z_]\w*))?", code):
            base, member = m.group(1), m.group(2)
            if base in ST_KEYWORDS or (base, member) in seen:
                continue
            seen.add((base, member))
            if base not in names:
                problems.append("%s: %s uses unknown identifier %r"
                                % (os.path.basename(path), rname, base))
                continue
            if not member:
                continue
            dtype = names[base]
            if dtype in scon and member not in scon[dtype]:
                problems.append("%s: %s -- %s has no member %r"
                                % (os.path.basename(path), rname, dtype, member))
            elif dtype == "TIMER" and member not in TIMER_MEMBERS:
                problems.append("%s: %s -- TIMER has no member %r"
                                % (os.path.basename(path), rname, member))

    print("%-46s %2d ST routines %3d lines %3d params/locals" % (
        os.path.basename(path),
        len(list(aoi.iter("Routine"))), n_lines, len(names)))
    return problems


def main():
    problems = []
    aoi_path = os.path.join(EXPORT, "IAI_SCON_Axis.L5X")
    if os.path.exists(aoi_path):
        problems += check_aoi_st(aoi_path)
    for name in sorted(os.listdir(EXPORT)):
        if name.endswith(".L5X") and name.startswith("Program"):
            problems += check(os.path.join(EXPORT, name))

    if problems:
        print("\n%d unresolved reference(s):" % len(problems))
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("\nall references resolve")


if __name__ == "__main__":
    main()
