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
  - the IAI AOI parameter lists, for backing-tag member references
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
    "SCON_Status", "SCON_Operations", "SCON_Moves",
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
    aoi_required = {}
    for aoi in root.iter("AddOnInstructionDefinition"):
        aoi_params[aoi.get("Name")] = {
            p.get("Name") for p in aoi.iter("Parameter")}
        aoi_params[aoi.get("Name")] |= {
            l.get("Name") for l in aoi.iter("LocalTag")}
        # A ladder call passes the backing tag plus one argument per
        # Required parameter, in declaration order.
        aoi_required[aoi.get("Name")] = [
            p.get("Name") for p in aoi.findall("Parameters/Parameter")
            if p.get("Required") == "true"]

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

    # Structural checks on the raw rung text, and duplicate-output
    # detection: two OTEs driving the same bit is a Logix verify error and
    # the classic way a step sequencer written in ladder goes wrong.
    ote_owner = {}

    n_rungs = 0
    for routine in program.iter("Routine"):
        rname = routine.get("Name")
        for rung in routine.iter("Rung"):
            n_rungs += 1
            text = (rung.findtext("Text") or "").strip()
            where = "%s rung %s" % (rname, rung.get("Number"))

            if not text.endswith(";"):
                problems.append("%s: %s does not end with ';'" % (
                    os.path.basename(path), where))
            if text.count("[") != text.count("]"):
                problems.append("%s: %s has unbalanced branch brackets" % (
                    os.path.basename(path), where))
            if text.count("(") != text.count(")"):
                problems.append("%s: %s has unbalanced parentheses" % (
                    os.path.basename(path), where))

            for bit in re.findall(r"OTE\(([^()]+)\)", text):
                if bit in ote_owner:
                    problems.append(
                        "%s: %s is driven by OTE in both %s and %s "
                        "(duplicate destructive bit)" % (
                            os.path.basename(path), bit, ote_owner[bit], where))
                else:
                    ote_owner[bit] = where
            for instr, args in re.findall(r"([A-Za-z_]\w*)\(([^()]*(?:\([^()]*\)[^()]*)*)\)", text):
                if instr in aoi_required:
                    want = len(aoi_required[instr]) + 1     # + the backing tag
                    got = len([a for a in args.split(",") if a.strip()])
                    if got != want:
                        problems.append(
                            "%s: %s call has %d operands, the definition needs "
                            "%d (backing tag + %d required parameters) in %s" % (
                                os.path.basename(path), instr, got, want,
                                want - 1, where))
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


def main():
    problems = []
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
