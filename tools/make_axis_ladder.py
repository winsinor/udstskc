#!/usr/bin/env python3
"""
Generate the barebones axis program for both stations.

    python3 tools/make_axis_ladder.py

Writes src/Station*.rungs and src/Station*.tags.csv from scratch.

Each program is two routines and six rungs: read the drive, turn the servo
on, hand the move to IAI's instructions, write the drive. Nothing else.

To move the actuator:
    set   <prefix>_Target        the position you want, 0.01mm
    pulse <prefix>_Cmd_StartMove SCON_Moves takes the rising edge

The AOI call operand lists are generated from IAI's own definitions, since
Logix expects every Required parameter in declaration order.
"""

import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
VENDOR_FILE = os.path.join(ROOT, "source", "iai", "SCON_Moves_AOI.L5X")


def required_parameters(aoi_name):
    root = ET.parse(VENDOR_FILE).getroot()
    for aoi in root.iter("AddOnInstructionDefinition"):
        if aoi.get("Name") == aoi_name:
            return [p.get("Name") for p in aoi.findall("Parameters/Parameter")
                    if p.get("Required") == "true"]
    raise SystemExit("AOI %s not found" % aoi_name)


def call(aoi_name, backing, mapping):
    params = required_parameters(aoi_name)
    missing = [p for p in params if p not in mapping]
    if missing:
        raise SystemExit("%s: no tag mapped for %s" % (aoi_name, missing))
    return "%s(%s,%s);" % (aoi_name, backing, ",".join(mapping[p] for p in params))


# SCON_Status output parameter -> tag suffix.
STATUS_MAP = [
    ("Actual_Position", "Position", "DINT", "Actual position, 0.01mm"),
    ("Actual_Speed", "Speed", "DINT", "Actual speed, 0.01mm/s"),
    ("Alarm_Active", "AlarmActive", "BOOL", "Drive alarm active (ALM)"),
    ("Alarm_Code", "AlarmCode", "INT", "Drive alarm code"),
    ("Battery_Alarm", "BatteryAlarm", "BOOL", "Battery alarm (BALM)"),
    ("Command_Current", "CommandCurrent", "DINT", "Command current"),
    ("Home_Complete", "HomeComplete", "BOOL", "Home complete (HEND)"),
    ("Homing", "Homing", "BOOL", "Homing in progress (GHMS)"),
    ("E_Stop_Active", "EStop", "BOOL", "Drive E-stop (EMGS)"),
    ("In_Push_Zone", "InPushZone", "BOOL", "In push zone (PUSHS)"),
    ("In_PZone", "InPZone", "BOOL", "In PZONE"),
    ("In_Zone_1", "InZone1", "BOOL", "In zone 1 (ZONE1)"),
    ("In_Zone_2", "InZone2", "BOOL", "In zone 2 (ZONE2)"),
    ("Load_Output_Reached", "LoadReached", "BOOL", "Load output reached"),
    ("Manual_Mode", "DriveManualMode", "BOOL", "Drive in manual mode (RMDS)"),
    ("Moving", "Moving", "BOOL", "Moving (MOVE)"),
    ("Position_Complete", "PositionComplete", "BOOL",
     "Position complete (PEND). This is the arrival confirmation"),
    ("Push_Failed", "PushFailed", "BOOL", "Push failed (PSFL)"),
    ("Ready", "DriveReady", "BOOL", "Drive ready (RDY)"),
    ("Servo_On", "ServoOn", "BOOL", "Servo is on (SV)"),
    ("Torque_Reached", "TorqueReached", "BOOL", "Torque level reached (TRQS)"),
    ("Total_Moving_Count", "TotalMoveCount", "DINT", "Total moving count"),
    ("Total_Moving_Distance", "TotalMoveDistance", "DINT", "Total moving distance"),
]

OPS_MAP = [
    ("Servo_On", "Cmd_ServoOn", "Servo enable"),
    ("Pause", "Cmd_Pause", "Pause the drive (STP)"),
    ("Inch_Select", "Cmd_Inch", "Inch select (JISL). Leave off for continuous jog"),
    ("Jog_Forward", "Cmd_JogFwd", "Jog forward (JOG+), runs while held"),
    ("Jog_Reverse", "Cmd_JogRev", "Jog reverse (JOG-), runs while held"),
    ("Reset", "Cmd_Reset", "Alarm reset (RES)"),
    ("Release_Brake", "Cmd_BrakeRelease", "Brake release (BKRL)"),
]

# SCON_Moves inputs that get their own tag. Speed/accel/decel reuse the
# controller tags that are already there.
MOVES_MAP = [
    ("Home", "Cmd_Home", "BOOL", "0", "Rising edge homes the axis"),
    ("Start_Move", "Cmd_StartMove", "BOOL", "0",
     "Rising edge runs a move to Target. This is the go command"),
    ("Target_Position", "Target", "DINT", "0",
     "Where to go, 0.01mm. Set this before pulsing Cmd_StartMove"),
    ("Position_Band", "Band", "DINT", "50", "In-position band, 0.01mm"),
    ("Increment_Select", "Increment_Select", "BOOL", "0",
     "Relative move (INC). Off = absolute moves"),
    ("Push_Select", "Push_Select", "BOOL", "0", "Push mode. Off = positioning only"),
    ("Push_Direction", "Push_Direction", "BOOL", "0", "Push direction. Unused"),
    ("Push_Percent", "Push_Percent", "INT", "0", "Push force percent. Unused"),
    ("Load_Threshold_Percent", "Load_Threshold", "INT", "0",
     "Load threshold percent. Unused"),
    ("PZone_Upper_Limit", "PZone_Upper", "DINT", "0", "PZONE upper limit. Unused"),
    ("PZone_Lower_Limit", "PZone_Lower", "DINT", "0", "PZONE lower limit. Unused"),
]


RUNGS = """# =====================================================================
# {PROGRAM}
#
# Barebones. Two routines, six rungs: read the drive, turn the servo on,
# hand the move to IAI's instructions, write the drive.
#
# TO MOVE THE ACTUATOR
#     set    {P}_Target         where to go, in 0.01mm (12500 = 125.00mm)
#     pulse  {P}_Cmd_StartMove  SCON_Moves takes the rising edge
#
#     watch  {P}_Position          where it actually is, 0.01mm
#            {P}_Moving            running
#            {P}_PositionComplete  arrived  <-- the confirmation
#            {P}_AlarmActive       faulted, code in {P}_AlarmCode
#
# The three SCON_* instructions are IAI's own, imported unmodified.
# SCON_Moves owns the START handshake: it latches START with the move
# data on the rising edge and drops it when the drive acknowledges.
#
# Speed, accel and decel come from the existing controller tags
# {SPEED}, {ACCEL} and {DECEL}.
# =====================================================================


@ROUTINE R000_Main | Main.
JSR(R100_Axis,0);


@ROUTINE R100_Axis | The whole axis. Six rungs.
# ---------------------------------------------------------------------
# 1. Read the drive, and unpack it into the {P}_ status tags.
# ---------------------------------------------------------------------
CPS({MOD}:I,{IN},1);

{STATUS_CALL}

# ---------------------------------------------------------------------
# 2. Servo permissive and the motor power contactor ({CR}).
#    Unlocking the doors drops the servo, so nothing can move with the
#    doors open. This is the existing machine interlock, kept as it was.
# ---------------------------------------------------------------------
XIC(POWER_OK_24VB)XIO(Unlock_Doors)
[OTE({P}_Cmd_ServoOn) ,OTE({CR}) ];

# ---------------------------------------------------------------------
# 3. Hand the commands to IAI's instructions.
#
#    Pulse {P}_Cmd_StartMove to run a move to {P}_Target.
#    {P}_Cmd_JogFwd / {P}_Cmd_JogRev jog while held.
#    {P}_Cmd_Home homes on a rising edge.
# ---------------------------------------------------------------------
{OPS_CALL}

{MOVES_CALL}

# ---------------------------------------------------------------------
# 4. Write the drive.
# ---------------------------------------------------------------------
CPS({OUT},{MOD}:O,1);
"""


STATIONS = [
    dict(FILE="Station200_UpStacker", P="UpAxis",
         PROGRAM="Program050000_Station200_UpStacker  --  up stacker axis",
         MOD="IAI_UpStacker", CR="CR614",
         IN="UpStack_Inputs", OUT="UpStack_Outputs",
         SPEED="UpStack_Target_Speed",
         ACCEL="UpStack_Output_Acceleration",
         DECEL="UpStack_Output_Deceleration"),
    dict(FILE="Station600_DownStacker", P="DnAxis",
         PROGRAM="Program090000_Station600_DownStacker  --  down stacker axis",
         MOD="IAI_DwnStacker", CR="CR615",
         IN="DwnStack_Inputs", OUT="DwnStack_Outputs",
         SPEED="DwnStack_Target_Speed",
         ACCEL="DwnStack_Output_Acceleration",
         DECEL="DwnStack_Output_Deceleration"),
]


def build(station):
    P = station["P"]
    status = call("SCON_Status", "%s_Sts" % P,
                  dict([(param, "%s_%s" % (P, suffix))
                        for param, suffix, _, _ in STATUS_MAP]
                       + [("Map_Axis_Inputs", station["IN"])]))
    ops = call("SCON_Operations", "%s_Ops" % P,
               dict([(param, "%s_%s" % (P, suffix))
                     for param, suffix, _ in OPS_MAP]
                    + [("Map_Axis_Outputs", station["OUT"])]))
    moves = call("SCON_Moves", "%s_Mov" % P,
                 dict([(param, "%s_%s" % (P, suffix))
                       for param, suffix, _, _, _ in MOVES_MAP]
                      + [("Target_Speed", station["SPEED"]),
                         ("Accel", station["ACCEL"]),
                         ("Decel", station["DECEL"]),
                         ("Map_Axis_Inputs", station["IN"]),
                         ("Map_Axis_Outputs", station["OUT"])]))

    rungs = RUNGS.format(STATUS_CALL=status, OPS_CALL=ops, MOVES_CALL=moves,
                         **station)
    with open(os.path.join(SRC, station["FILE"] + ".rungs"), "w") as fh:
        fh.write(rungs)

    tags = ["# Program-scoped tags for %s" % station["PROGRAM"].split("  --")[0],
            "#",
            "# name , datatype , dimensions , default , description",
            "#",
            "# Nearly all of these exist because IAI's instructions require an",
            "# argument for every parameter. The only ones you touch to move the",
            "# axis are %s_Target and %s_Cmd_StartMove." % (P, P),
            "",
            "# ---- IAI instruction backing tags ---------------------------------",
            "%s_Sts , SCON_Status     , , , SCON_Status backing tag" % P,
            "%s_Ops , SCON_Operations , , , SCON_Operations backing tag" % P,
            "%s_Mov , SCON_Moves      , , , SCON_Moves backing tag" % P,
            "",
            "# ---- status, filled in by SCON_Status -----------------------------"]
    for _, suffix, dtype, desc in STATUS_MAP:
        tags.append("%-26s , %-4s , , 0 , %s" % ("%s_%s" % (P, suffix), dtype, desc))
    tags += ["", "# ---- commands into SCON_Operations --------------------------------"]
    for _, suffix, desc in OPS_MAP:
        tags.append("%-26s , BOOL , , 0 , %s" % ("%s_%s" % (P, suffix), desc))
    tags += ["", "# ---- commands into SCON_Moves -------------------------------------"]
    for _, suffix, dtype, default, desc in MOVES_MAP:
        tags.append("%-26s , %-4s , , %-2s , %s"
                    % ("%s_%s" % (P, suffix), dtype, default, desc))
    with open(os.path.join(SRC, station["FILE"] + ".tags.csv"), "w") as fh:
        fh.write("\n".join(tags) + "\n")

    return len(STATUS_MAP) + len(OPS_MAP) + len(MOVES_MAP) + 3


def main():
    for station in STATIONS:
        n = build(station)
        print("  %-30s 2 routines, 6 rungs, %d tags" % (station["FILE"], n))


if __name__ == "__main__":
    main()
