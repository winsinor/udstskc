#!/usr/bin/env python3
"""
Assemble importable Studio 5000 L5X files from the readable sources in src/.

    python3 tools/build_l5x.py

Produces, in export/:
    SCON_*_AOI.L5X                          the three IAI Add-On Instructions,
                                            copied through byte for byte
    Program050000_Station200_UpStacker.L5X  the up stacker program
    Program090000_Station600_DownStacker.L5X the down stacker program

There is no custom Add-On Instruction. The only AOIs involved are IAI's own,
and this script does not modify them.

The two program files are built by taking the ORIGINAL export from source/
and replacing only its <Program Use="Target"> element.  Everything else --
the controller context, the data types, the module and tag dependencies --
is carried across byte for byte, so the generated file declares exactly the
dependencies the original did and nothing is silently dropped.
"""

import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SOURCE = os.path.join(ROOT, "source")
EXPORT = os.path.join(ROOT, "export")
IAI_DIR = os.path.join(ROOT, "source", "iai")

SOFTWARE_REVISION = "35.04"

STAMP = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def xml_escape(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def cdata(text):
    """Wrap in CDATA, splitting any accidental ']]>' sequence."""
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def description(text, indent=""):
    if not text:
        return ""
    return "%s<Description>\n%s%s\n%s</Description>\n" % (
        indent, indent, cdata(text), indent)


def read_csv_rows(path, columns):
    """Yield rows of exactly `columns` fields, skipping blanks and # comments.

    The last field is the description and may itself contain commas, so
    everything past the last separator is rejoined into it.
    """
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cells = [c.strip() for c in line.split(",")]
            if len(cells) < columns:
                cells += [""] * (columns - len(cells))
            elif len(cells) > columns:
                cells = cells[:columns - 1] + [", ".join(cells[columns - 1:])]
            yield cells


# ---------------------------------------------------------------------------
# the IAI vendor Add-On Instructions
# ---------------------------------------------------------------------------

VENDOR_AOI_FILE = os.path.join(ROOT, "source", "iai", "SCON_Moves_AOI.L5X")
VENDOR_AOIS = ("SCON_Status", "SCON_Operations", "SCON_Moves")


def vendor_aoi_context():
    """The three IAI AOI definitions, verbatim, marked as context.

    They are not modified in any way -- the only edit is Use="Target"
    to Use="Context", which is what tells Studio 5000 these are
    dependencies of the program rather than things to import.
    """
    text = open(VENDOR_AOI_FILE, encoding="utf-8-sig").read()
    blocks = []
    for name in VENDOR_AOIS:
        m = re.search(
            r'(<AddOnInstructionDefinition Use="[^"]*" Name="%s".*?'
            r'</AddOnInstructionDefinition>)' % name, text, re.S)
        if not m:
            sys.exit("vendor AOI %s not found in %s" % (name, VENDOR_AOI_FILE))
        blocks.append(m.group(1).replace('Use="Target"', 'Use="Context"', 1))
    return chr(10).join(blocks)


# ---------------------------------------------------------------------------
# program tags
# ---------------------------------------------------------------------------

def build_tags(tags_csv, cognex_defaults=None):
    out = ["<Tags>"]
    for row in read_csv_rows(tags_csv, 5):
        name, dtype, dims, default, desc = row

        # Attribute set and order copied from Studio 5000's own output --
        # see the controller tags in the original export.
        attrs = ['Name="%s"' % name, 'Class="Standard"', 'TagType="Base"',
                 'DataType="%s"' % dtype]
        if dims:
            attrs.append('Dimensions="%s"' % " ".join(dims.split()))
        if dtype in ("BOOL", "SINT", "INT", "DINT"):
            attrs.append('Radix="Decimal"')
        attrs.append('Constant="false"')
        attrs.append('ExternalAccess="Read/Write"')

        out.append("<Tag %s>" % " ".join(attrs))
        out.append(description(desc).rstrip("\n"))

        if dims and name == "Cfg_Cognex_Offset":
            rows_n, cols_n = (int(x) for x in dims.split())
            values = cognex_defaults or {}
            flat, elements = [], []
            for r in range(rows_n):
                for c in range(cols_n):
                    v = values.get((r, c), 0)
                    flat.append(str(v))
                    elements.append('<Element Index="[%d,%d]" Value="%d"/>' % (r, c, v))
            out.append('<Data Format="L5K">\n%s\n</Data>'
                       % cdata("[" + ",".join(flat) + "]"))
            out.append('<Data Format="Decorated">')
            out.append('<Array DataType="DINT" Dimensions="%d,%d" Radix="Decimal">'
                       % (rows_n, cols_n))
            out.extend(elements)
            out.append("</Array>")
            out.append("</Data>")
        elif not dims and dtype in ("BOOL", "SINT", "INT", "DINT") and default != "":
            out.append('<Data Format="L5K">\n%s\n</Data>' % cdata(default))
            out.append('<Data Format="Decorated">')
            out.append('<DataValue DataType="%s" Radix="Decimal" Value="%s"/>'
                       % (dtype, default))
            out.append("</Data>")

        out.append("</Tag>")
    out.append("</Tags>")
    return "\n".join(l for l in out if l)


# ---------------------------------------------------------------------------
# program routines
# ---------------------------------------------------------------------------

def parse_rungs(path):
    """Parse the .rungs source into [(routine, description, [(comment, text)])]."""
    routines = []
    comment, buf = [], []

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("@ROUTINE"):
                head = stripped[len("@ROUTINE"):].strip()
                name, _, desc = head.partition("|")
                routines.append((name.strip(), desc.strip(), []))
                comment, buf = [], []
                continue

            if not routines:
                continue                      # file header, before any routine

            if not buf and stripped.startswith("#"):
                comment.append(stripped.lstrip("#").rstrip())
                continue

            if not stripped:
                if not buf:
                    comment = []              # blank line ends a comment block
                continue

            buf.append(stripped)
            if stripped.endswith(";"):
                text = " ".join(buf)
                routines[-1][2].append(("\n".join(comment).strip(), text))
                comment, buf = [], []

    if buf:
        sys.exit("unterminated rung in %s: %s" % (path, " ".join(buf)[:80]))
    return routines


def build_routines(rungs_path):
    out = ["<Routines>"]
    for name, desc, rungs in parse_rungs(rungs_path):
        out.append('<Routine Name="%s" Type="RLL">' % name)
        out.append(description(desc).rstrip("\n"))
        out.append("<RLLContent>")
        for i, (comment, text) in enumerate(rungs):
            out.append('<Rung Number="%d" Type="N">' % i)
            if comment:
                out.append("<Comment>\n%s\n</Comment>" % cdata(comment))
            out.append("<Text>\n%s\n</Text>" % cdata(text))
            out.append("</Rung>")
        out.append("</RLLContent>")
        out.append("</Routine>")
    out.append("</Routines>")
    return "\n".join(l for l in out if l)


# ---------------------------------------------------------------------------
# whole program files
# ---------------------------------------------------------------------------

# The Cognex InspectionResults index of the X value for each tray hole,
# as [row, column].  These are the eight offsets the original program had
# hard-coded in its rung 6; a 2 row x 4 column tray.
COGNEX_OFFSETS = {
    (1, 1): 0,  (1, 2): 6,  (1, 3): 24, (1, 4): 30,
    (2, 1): 48, (2, 2): 54, (2, 3): 72, (2, 4): 78,
}


def build_program_file(original_name, program_name, tags_csv, rungs_file,
                       extra_context_tags=(), cognex_defaults=None):
    original = open(os.path.join(SOURCE, original_name), encoding="utf-8-sig").read()

    program = "\n".join([
        '<Program Use="Target" Name="%s" TestEdits="false" '
        'MainRoutineName="R000_Main" Disabled="false" Class="Standard" '
        'UseAsFolder="false">' % program_name,
        build_tags(tags_csv, cognex_defaults),
        build_routines(rungs_file),
        '</Program>',
    ])

    # Swap the target program for ours, leaving the whole context intact.
    new, n = re.subn(r'<Program Use="Target".*?</Program>', lambda _: program,
                     original, count=1, flags=re.S)
    if n != 1:
        sys.exit("could not find the target <Program> in %s" % original_name)

    # Declare the AOIs so the program's dependency on them is explicit.
    #
    # Placement is not free choice: the L5X schema fixes the order of the
    # children of <Controller> as
    #     DataTypes, Modules, AddOnInstructionDefinitions, Tags, Programs
    # so this block goes after </Modules>, not after </DataTypes>. Putting it
    # in the wrong slot makes Studio 5000 reject the file with
    # "Element <Modules> is in the wrong order."
    if "<AddOnInstructionDefinitions" not in new:
        aoi_block = ('<AddOnInstructionDefinitions Use="Context">\n%s\n'
                     '</AddOnInstructionDefinitions>\n' % vendor_aoi_context())
        new, n = re.subn(r'(</Modules>\n)', lambda m: m.group(1) + aoi_block,
                         new, count=1)
        if n != 1:
            sys.exit("could not place the AOI context block in %s" % original_name)

    # Some referenced controller tags are absent from an export's context
    # because the original program never touched them.  Carry them over.
    for tag_name in extra_context_tags:
        if re.search(r'<Tag Name="%s"' % re.escape(tag_name), new):
            continue
        src = open(os.path.join(
            SOURCE, "Program050000_Station200_UpStacker_Program.L5X"),
            encoding="utf-8-sig").read()
        m = re.search(r'(<Tag Name="%s"[ >].*?</Tag>)' % re.escape(tag_name), src, re.S)
        if not m:
            sys.exit("could not find controller tag %s to carry over" % tag_name)
        new, n = re.subn(r'(<Tags Use="Context">\n)',
                         lambda mm: mm.group(1) + m.group(1) + "\n", new, count=1)
        if n != 1:
            sys.exit("could not place carried-over tag %s" % tag_name)

    new = new.replace('TargetName="Program050000_Station200_UpStacker"',
                      'TargetName="%s"' % program_name)
    new = new.replace('TargetName="Program090000_Station600_DownStacker"',
                      'TargetName="%s"' % program_name)
    return new


# ---------------------------------------------------------------------------

def main():
    os.makedirs(EXPORT, exist_ok=True)
    written = []

    def write(filename, text):
        path = os.path.join(EXPORT, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            sys.exit("%s is not well-formed XML: %s" % (filename, exc))
        written.append((filename, os.path.getsize(path)))

    # The vendor AOI files are copied through byte for byte. They are IAI's,
    # not ours, and nothing here modifies them.
    for name in sorted(os.listdir(IAI_DIR)):
        if name.endswith(".L5X"):
            src = os.path.join(IAI_DIR, name)
            with open(src, "rb") as fh:
                blob = fh.read()
            with open(os.path.join(EXPORT, name), "wb") as fh:
                fh.write(blob)
            written.append((name + "  (IAI, unmodified)", len(blob)))

    write("Program050000_Station200_UpStacker.L5X", build_program_file(
        "Program050000_Station200_UpStacker_Program.L5X",
        "Program050000_Station200_UpStacker",
        os.path.join(SRC, "Station200_UpStacker.tags.csv"),
        os.path.join(SRC, "Station200_UpStacker.rungs"),
        cognex_defaults=COGNEX_OFFSETS))

    write("Program090000_Station600_DownStacker.L5X", build_program_file(
        "Program090000_Station600_DownStacker_Program.L5X",
        "Program090000_Station600_DownStacker",
        os.path.join(SRC, "Station600_DownStacker.tags.csv"),
        os.path.join(SRC, "Station600_DownStacker.rungs"),
        extra_context_tags=("Cfg_Layer_Max",)))

    for filename, size in written:
        print("  %-46s %8d bytes" % (filename, size))


if __name__ == "__main__":
    main()
