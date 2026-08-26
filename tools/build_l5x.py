#!/usr/bin/env python3
"""
Assemble importable Studio 5000 L5X files from the readable sources in src/.

    python3 tools/build_l5x.py

Produces, in export/:
    IAI_SCON_Axis.L5X                       the Add-On Instruction
    Program050000_Station200_UpStacker.L5X  the up stacker program
    Program090000_Station600_DownStacker.L5X the down stacker program

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

AOI_NAME = "IAI_SCON_Axis"
AOI_REVISION = "1.0"
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
# structured text
# ---------------------------------------------------------------------------

def st_routine(name, path, routine_description=None):
    """An <STContent> routine, one <Line> per source line."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    while lines and not lines[-1].strip():
        lines.pop()

    out = ['<Routine Name="%s" Type="ST">' % name]
    if routine_description:
        out.append(description(routine_description).rstrip("\n"))
    out.append("<STContent>")
    for i, line in enumerate(lines):
        out.append('<Line Number="%d">\n%s\n</Line>' % (i, cdata(line)))
    out.append("</STContent>")
    out.append("</Routine>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# the Add-On Instruction
# ---------------------------------------------------------------------------

def build_aoi_element(use):
    """Build the <AddOnInstructionDefinition> element as text."""
    params, locals_ = [], []
    for row in read_csv_rows(os.path.join(SRC, "%s.params.csv" % AOI_NAME), 6):
        if row[0].startswith("@local"):
            # "@local NAME , DATATYPE , description" -- only three fields
            locals_.append((row[0].split(None, 1)[1].strip(), row[1],
                            ", ".join(c for c in row[2:] if c)))
        else:
            params.append(row)

    out = []
    out.append(
        '<AddOnInstructionDefinition Use="%s" Name="%s" Revision="%s" '
        'ExecutePrescan="false" ExecutePostscan="false" '
        'ExecuteEnableInFalse="true" CreatedDate="%s" '
        'EditedDate="%s" SoftwareRevision="v%s">'
        % (use, AOI_NAME, AOI_REVISION, STAMP, STAMP, SOFTWARE_REVISION))

    out.append(description(
        "Driver for one IAI SCON actuator on EtherNet/IP in direct numerical "
        "specification mode.\n\n"
        "Call it as:  IAI_SCON_Axis( <backing tag>, <input image>, <output image> )\n"
        "with a CPS from the module input tag before the call and a CPS to the "
        "module output tag after it.\n\n"
        "To move: load Set_Position (0.01mm) and give Cmd_MoveAbs a rising edge. "
        "Sts_InPosition confirms arrival from the drive's PEND bit; Sts_MoveDone "
        "pulses for one scan. Targets outside Cfg_Pos_Min..Cfg_Pos_Max are refused "
        "and raise Sts_Fault_Range. A move that does not confirm inside "
        "Cfg_Move_Timeout raises Sts_Fault_Timeout.\n\n"
        "Cmd_JogUp / Cmd_JogDn jog while held.").rstrip("\n"))

    out.append("<Parameters>")
    for name, usage, dtype, required, visible, desc in params:
        if usage == "InOut":
            out.append(
                '<Parameter Name="%s" TagType="Base" DataType="%s" '
                'Usage="InOut" Required="%s" Visible="%s" Constant="false">'
                % (name, dtype, required, visible))
        else:
            radix = "Decimal" if dtype in ("BOOL", "SINT", "INT", "DINT") else "NullType"
            access = "Read/Write"
            if name in ("EnableIn", "EnableOut"):
                access = "Read Only"
            out.append(
                '<Parameter Name="%s" TagType="Base" DataType="%s" Usage="%s" '
                'Radix="%s" Required="%s" Visible="%s" ExternalAccess="%s">'
                % (name, dtype, usage, radix, required, visible, access))
        out.append(description(desc).rstrip("\n"))
        out.append("</Parameter>")
    out.append("</Parameters>")

    out.append("<LocalTags>")
    for name, dtype, desc in locals_:
        radix = ' Radix="Decimal"' if dtype in ("BOOL", "SINT", "INT", "DINT") else ""
        out.append('<LocalTag Name="%s" DataType="%s"%s ExternalAccess="Read/Write">'
                   % (name, dtype, radix))
        out.append(description(desc).rstrip("\n"))
        out.append("</LocalTag>")
    out.append("</LocalTags>")

    out.append("<Routines>")
    out.append(st_routine("Logic", os.path.join(SRC, "%s.st" % AOI_NAME)))
    out.append(st_routine("EnableInFalse",
                          os.path.join(SRC, "%s.EnableInFalse.st" % AOI_NAME)))
    out.append("</Routines>")
    out.append("</AddOnInstructionDefinition>")
    return "\n".join(l for l in out if l)


def build_aoi_file():
    """Standalone AOI export. Carries the two SCON data types as context."""
    original = open(os.path.join(
        SOURCE, "Program050000_Station200_UpStacker_Program.L5X"),
        encoding="utf-8-sig").read()

    types = []
    for name in ("SCON_Inputs", "SCON_Outputs"):
        m = re.search(r'(<DataType Name="%s".*?</DataType>)' % name, original, re.S)
        if not m:
            sys.exit("could not find data type %s in the original export" % name)
        types.append(m.group(1))

    controller = re.search(r'<Controller Use="Context" Name="([^"]+)"', original).group(1)

    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<RSLogix5000Content SchemaRevision="1.0" SoftwareRevision="%s" '
        'TargetName="%s" TargetType="AddOnInstructionDefinition" '
        'TargetRevision="%s" TargetLastEdited="%s" ContainsContext="true" '
        'ExportDate="%s" ExportOptions="References NoRawData L5KData '
        'DecoratedData Context Dependencies ForceProtectedEncoding '
        'AllProjDocTrans">'
        % (SOFTWARE_REVISION, AOI_NAME, AOI_REVISION, STAMP, STAMP),
        '<Controller Use="Context" Name="%s">' % controller,
        '<DataTypes Use="Context">',
        "\n".join(types),
        '</DataTypes>',
        '<AddOnInstructionDefinitions Use="Context">',
        build_aoi_element("Target"),
        '</AddOnInstructionDefinitions>',
        '</Controller>',
        '</RSLogix5000Content>',
        '',
    ])


# ---------------------------------------------------------------------------
# program tags
# ---------------------------------------------------------------------------

def build_tags(tags_csv, cognex_defaults=None):
    out = ["<Tags>"]
    for row in read_csv_rows(tags_csv, 5):
        name, dtype, dims, default, desc = row

        attrs = ['Name="%s"' % name, 'TagType="Base"', 'DataType="%s"' % dtype]
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
        '<Program Use="Target" Name="%s" TestEdits="false" MainRoutineName="R000_Main" '
        'Disabled="false" UseAsFolder="false">' % program_name,
        build_tags(tags_csv, cognex_defaults),
        build_routines(rungs_file),
        '</Program>',
    ])

    # Swap the target program for ours, leaving the whole context intact.
    new, n = re.subn(r'<Program Use="Target".*?</Program>', lambda _: program,
                     original, count=1, flags=re.S)
    if n != 1:
        sys.exit("could not find the target <Program> in %s" % original_name)

    # Declare the AOI so the program's dependency on it is explicit.
    if "<AddOnInstructionDefinitions" not in new:
        aoi_block = ('<AddOnInstructionDefinitions Use="Context">\n%s\n'
                     '</AddOnInstructionDefinitions>\n' % build_aoi_element("Context"))
        new, n = re.subn(r'(</DataTypes>\n)', lambda m: m.group(1) + aoi_block,
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

    write("%s.L5X" % AOI_NAME, build_aoi_file())

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
