#!/usr/bin/env python3
"""
Generate the R100_AxisControl ladder for both stations and splice it into
their .rungs sources.

    python3 tools/make_axis_ladder.py

The three IAI Add-On Instructions (SCON_Status, SCON_Operations, SCON_Moves)
are the vendor's own, imported unmodified. Everything else -- the step
sequencer, manual control, arbitration, the watchdog -- is plain ladder in
the program.

The AOI call operand lists are generated from the vendor definitions rather
than typed by hand: Logix expects every Required parameter, in declaration
order, and getting that wrong is the easiest way to fail an import.
"""

import os
import re
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
IAI = os.path.join(ROOT, "source", "iai")
VENDOR_FILE = os.path.join(IAI, "SCON_Moves_AOI.L5X")


def required_parameters(aoi_name):
    """Required parameters of a vendor AOI, in declaration order.

    A Logix ladder call passes the backing tag then every Required
    parameter in this order. EnableIn/EnableOut/EN are Required=false and
    are not in the operand list.
    """
    root = ET.parse(VENDOR_FILE).getroot()
    for aoi in root.iter("AddOnInstructionDefinition"):
        if aoi.get("Name") != aoi_name:
            continue
        return [p.get("Name") for p in aoi.findall("Parameters/Parameter")
                if p.get("Required") == "true"]
    raise SystemExit("AOI %s not found in %s" % (aoi_name, VENDOR_FILE))


def call(aoi_name, backing, mapping):
    """Render an AOI call, checking the mapping covers every parameter."""
    params = required_parameters(aoi_name)
    missing = [p for p in params if p not in mapping]
    if missing:
        raise SystemExit("%s: no tag mapped for %s" % (aoi_name, missing))
    extra = [k for k in mapping if k not in params]
    if extra:
        raise SystemExit("%s: mapped tags that are not parameters: %s"
                         % (aoi_name, extra))
    return "%s(%s,%s);" % (aoi_name, backing, ",".join(mapping[p] for p in params))


# --------------------------------------------------------------------------

HEADER = """@ROUTINE R100_AxisControl | The only routine that talks to the actuator. Read it top to bottom.
# =====================================================================
# {TITLE} AXIS
#
# The three SCON_* instructions are IAI's own Add-On Instructions,
# imported unmodified from the vendor files. They do exactly three
# things and nothing else:
#
#   SCON_Status      unpacks the drive input image into readable tags
#   SCON_Operations  writes servo on, pause, jog, reset, brake release
#   SCON_Moves       writes home and the positioning move, and owns the
#                    START (DSTR) handshake -- it latches START, loads
#                    the move data, and drops START once the drive
#                    acknowledges by clearing POSITION COMPLETE
#
# Everything else below is plain ladder in this program. No custom AOI.
#
# THE STEP SEQUENCER  --  {P}_Step is the tag to watch
#
#    0  initialising
#   10  not ready: no servo, not homed, drive alarm, or E-stop
#   20  idle, ready and holding position
#   30  move: range-check the target and load it
#   35  move: hand the move to SCON_Moves (one scan)
#   40  move: waiting for the drive to accept it
#   50  move: running, waiting for POSITION COMPLETE
#   60  move: arrival confirmed (one scan)
#   70  home: hand the home request to SCON_Moves
#   80  home: waiting for HOME COMPLETE
#   90  jogging
#
# Two rules make this safe, and both matter if you edit it:
#
#   1. Every command tag is written by exactly ONE rung, and that rung
#      names the step that owns it. No duplicate destructive bits.
#   2. The transition rungs are in DESCENDING step order. That is what
#      limits the sequencer to one step per scan -- in ascending order a
#      move would run 30-35-40 in a single scan and the start pulse
#      would never reach the instruction.
# =====================================================================
# ---------------------------------------------------------------------
# 1. Read the drive, then unpack it with the vendor status instruction.
#    Everything below reads the {P}_ status tags, never the module tag.
# ---------------------------------------------------------------------
CPS({MOD}:I,{IN},1);

{STATUS_CALL}

# ---------------------------------------------------------------------
# 2. Servo permissive and the motor power contactor ({CR}).
#    Unlocking the doors drops the servo, so with the doors unlocked
#    nothing moves no matter what is pressed on the faceplate.
# ---------------------------------------------------------------------
XIC(POWER_OK_24VB)XIO(Unlock_Doors)
[OTE({P}_Cmd_ServoOn) ,OTE({CR}) ];

# ---------------------------------------------------------------------
# 3. Motion parameters and timer presets, refreshed every scan so an HMI
#    edit takes effect on the next move without a download.
#    SCON_Moves latches these into the drive on the start pulse.
# ---------------------------------------------------------------------
[MOV(Cfg_MoveTimeout,{P}_Move_TMR.PRE)
,MOV(200,{P}_Reset_TMR.PRE) ];

# Jog speed select (JVEL). SCON_Operations does not expose this bit, so
# it is written straight to the output image -- the vendor instruction
# does not touch it, so there is no conflict. Jog speeds themselves come
# from the drive's own parameters.
XIC(Cfg_JogFast)OTE({OUT}.Jog_Parameter_Select);

# ---------------------------------------------------------------------
# 4. Pause, and the alarm reset pulse. RES is pulsed for 200ms and only
#    while the drive is actually alarmed, so holding the HMI reset
#    button cannot sit on the bit.
# ---------------------------------------------------------------------
XIC(Man_Stop_PB)OTE({P}_Cmd_Pause);

[XIC(FaultReset) ,XIC(Man_Reset_PB) ]OTE({P}_Reset_Req);

XIC({P}_Reset_Req)XIC({P}_AlarmActive)
TON({P}_Reset_TMR,?,?)XIO({P}_Reset_TMR.DN)OTE({P}_Cmd_Reset);

XIC({P}_Reset_Req)[OTU({P}_Fault_Timeout) ,OTU({P}_Fault_Range) ];

# ---------------------------------------------------------------------
# 5. Who owns the axis: manual or the auto sequence. One or the other,
#    never both. This is the single arbitration point in the program.
# ---------------------------------------------------------------------
XIC(Man_Mode)MOV(Man_Target_Position,{P}_Set_Position);

XIO(Man_Mode)MOV(Auto_Target_Position,{P}_Set_Position);

# Both sources are one-scan pulses produced by R200/R300 on the previous
# scan, so no edge detection is needed here.
[XIC(Man_Mode) XIC(Man_Move_Cmd)
,XIO(Man_Mode) XIC(Auto_Move_Cmd) ]OTE({P}_Move_Req);

XIC(Man_Mode)XIC(Man_Home_PB)ONS({P}_ONS.0)OTE({P}_Home_Req);

# ---------------------------------------------------------------------
# 6. Derived status. The rest of the program reads these.
# ---------------------------------------------------------------------
[XIC({P}_AlarmActive) ,XIC({P}_Fault_Timeout) ]OTE({P}_Fault);

XIC({P}_DriveReady)XIC({P}_ServoOn)XIC({P}_HomeComplete)
XIO({P}_EStop)XIO({P}_Fault)OTE({P}_Ready);

# Motion is allowed. Every command rung is gated on this, so a fault
# drops the command bits in the same scan it appears.
XIC({P}_ServoOn)XIO({P}_AlarmActive)XIO({P}_EStop)
XIO({P}_Fault_Timeout)OTE({P}_Motion_OK);

GEQ({P}_Step,30)LEQ({P}_Step,90)OTE({P}_Busy);

# In position: the drive's own POSITION COMPLETE while idle, or the
# confirmed arrival at step 60. This is the move confirmation.
[EQU({P}_Step,20) XIC({P}_PositionComplete) XIO({P}_Moving)
,EQU({P}_Step,60) ]OTE({P}_InPosition);

# Step 60 lasts exactly one scan, so this is a one-scan done pulse.
EQU({P}_Step,60)OTE({P}_MoveDone);

EQU({P}_Step,90)OTE({P}_Jogging);

# ---------------------------------------------------------------------
# 7. Commands into the vendor instructions. ONE rung each -- do not add
#    a second writer.
# ---------------------------------------------------------------------
XIC({P}_Motion_OK)EQU({P}_Step,35)OTE({P}_Cmd_StartMove);

XIC({P}_Motion_OK)EQU({P}_Step,70)OTE({P}_Cmd_Home);

# JOG DIRECTION -- CHECK ON COMMISSIONING. This assumes extend (JOG+)
# raises the stacker, i.e. increasing position is up, which matches the
# layer arithmetic. If it is reversed, swap these two rungs.
XIC({P}_Motion_OK)EQU({P}_Step,90)XIC(Man_JogUp)XIO(Man_JogDn)
OTE({P}_Cmd_JogFwd);

XIC({P}_Motion_OK)EQU({P}_Step,90)XIC(Man_JogDn)XIO(Man_JogUp)
OTE({P}_Cmd_JogRev);

# ---------------------------------------------------------------------
# 8. Step transitions, in DESCENDING order -- see the note at the top.
# ---------------------------------------------------------------------
# 90 -> 20  both buttons released, both pressed, or stop
EQU({P}_Step,90)
[XIO(Man_JogUp) XIO(Man_JogDn)
,XIC(Man_JogUp) XIC(Man_JogDn)
,XIC(Man_Stop_PB) ]MOV(20,{P}_Step);

# 80 -> 20  homing finished
EQU({P}_Step,80)XIC({P}_HomeComplete)XIO({P}_Homing)MOV(20,{P}_Step);

# 70 -> 80  drive has started homing
EQU({P}_Step,70)XIC({P}_Homing)MOV(80,{P}_Step);

# 60 -> 20  arrival already reported, go back to idle
EQU({P}_Step,60)MOV(20,{P}_Step);

# 50 -> 60  POSITION COMPLETE: the move is confirmed
EQU({P}_Step,50)XIC({P}_PositionComplete)XIO({P}_Moving)MOV(60,{P}_Step);

# 40 -> 50  the drive has accepted the move
EQU({P}_Step,40)
[XIC({P}_Moving) ,XIO({P}_PositionComplete) ]MOV(50,{P}_Step);

# 35 -> 40  the start pulse has been handed to SCON_Moves
EQU({P}_Step,35)MOV(40,{P}_Step);

# 30 -> 35  target in range: load it and go
# 30 -> 20  target refused: flag it and stay put. The old program simply
#           dropped an out-of-range target with no indication.
EQU({P}_Step,30)
[GEQ({P}_Set_Position,{LOMAX}) LEQ({P}_Set_Position,{HIMAX})
 [MOV({P}_Set_Position,{P}_Target) ,OTU({P}_Fault_Range) ,MOV(35,{P}_Step) ]
,[LES({P}_Set_Position,{LOMAX}) ,GRT({P}_Set_Position,{HIMAX}) ]
 [OTL({P}_Fault_Range) ,MOV(20,{P}_Step) ] ];

# 20 -> 30 move, 20 -> 70 home, 20 -> 90 jog
EQU({P}_Step,20)XIO(Man_Stop_PB)
[XIC({P}_Move_Req) MOV(30,{P}_Step)
,XIC({P}_Home_Req) MOV(70,{P}_Step)
,[XIC(Man_JogUp) XIO(Man_JogDn) ,XIC(Man_JogDn) XIO(Man_JogUp) ]
 MOV(90,{P}_Step) ];

# 10 -> 20 ready, or 10 -> 70 if homing was asked for
EQU({P}_Step,10)XIC({P}_ServoOn)XIO({P}_AlarmActive)XIO({P}_EStop)
[XIC({P}_HomeComplete) MOV(20,{P}_Step)
,XIO({P}_HomeComplete) XIC({P}_Home_Req) MOV(70,{P}_Step) ];

# 0 -> 10  first scan
EQU({P}_Step,0)MOV(10,{P}_Step);

# Anything outside the defined steps restarts the sequencer.
[LES({P}_Step,0) ,GRT({P}_Step,90) ]MOV(0,{P}_Step);

# ---------------------------------------------------------------------
# 9. Abort. Runs after the transitions so it always wins: an alarm, an
#    E-stop or the servo dropping mid-move sends the sequencer back to
#    NOT READY. The command bits are already off via {P}_Motion_OK.
# ---------------------------------------------------------------------
GEQ({P}_Step,30)XIO({P}_Motion_OK)MOV(10,{P}_Step);

# ---------------------------------------------------------------------
# 10. Move and home watchdog. If the drive never confirms, this faults
#     instead of hanging. The old program had no such check.
# ---------------------------------------------------------------------
[GEQ({P}_Step,35) LEQ({P}_Step,50)
,GEQ({P}_Step,70) LEQ({P}_Step,80) ]TON({P}_Move_TMR,?,?);

XIC({P}_Move_TMR.DN)OTL({P}_Fault_Timeout);

# ---------------------------------------------------------------------
# 11. Hand the commands to the vendor instructions, then write the drive.
# ---------------------------------------------------------------------
{OPS_CALL}

{MOVES_CALL}

CPS({OUT},{MOD}:O,1);

# ---------------------------------------------------------------------
# 12. Keep the existing controller-scoped target tag in step, so HMI
#     screens already pointing at it keep reading correctly.
# ---------------------------------------------------------------------
MOV({P}_Target,{TARGETTAG});
{EXTRA}"""


UPSTACK_EXTRA = """
# ---------------------------------------------------------------------
# 13. Drive and camera communications faults. Broken out of the original
#     rung 0, which mixed the I/O copy, the servo permissive, two GSVs
#     and the reset logic into a single rung.
# ---------------------------------------------------------------------
GSV(Module,IS3800,FaultCode,HARDWARE_FAULTS[0])NEQ(HARDWARE_FAULTS[0],0)
[XIO(Cognex_Bypass) OTL(Cognex_Com_Fault)
,XIC(Cognex_Bypass) OTU(Cognex_Com_Fault) ];

GSV(Module,IAI_UpStacker,FaultCode,HARDWARE_FAULTS[1])NEQ(HARDWARE_FAULTS[1],0)
OTL(Upstack_Com_Fault);

XIC(Reset_Hold_TMR.DN)
[OTU(Cognex_Com_Fault) ,OTU(Upstack_Com_Fault) ,OTU(Upstack_Jam) ];
"""

DOWNSTACK_EXTRA = """
# ---------------------------------------------------------------------
# 13. Drive communications fault.
# ---------------------------------------------------------------------
GSV(Module,IAI_DwnStacker,FaultCode,HARDWARE_FAULTS[2])NEQ(HARDWARE_FAULTS[2],0)
OTL(DwnStack_Com_Fault);

XIC(Reset_Hold_TMR.DN)[OTU(DwnStack_Com_Fault) ,OTU(DwnStack_Jam) ];
"""


def build_calls(P, IN, OUT, SPEED, ACCEL, DECEL):
    status = call("SCON_Status", "%s_Sts" % P, {
        "Actual_Position": "%s_Position" % P,
        "Actual_Speed": "%s_Speed" % P,
        "Alarm_Active": "%s_AlarmActive" % P,
        "Alarm_Code": "%s_AlarmCode" % P,
        "Battery_Alarm": "%s_BatteryAlarm" % P,
        "Command_Current": "%s_CommandCurrent" % P,
        "Home_Complete": "%s_HomeComplete" % P,
        "Homing": "%s_Homing" % P,
        "E_Stop_Active": "%s_EStop" % P,
        "In_Push_Zone": "%s_InPushZone" % P,
        "In_PZone": "%s_InPZone" % P,
        "In_Zone_1": "%s_InZone1" % P,
        "In_Zone_2": "%s_InZone2" % P,
        "Load_Output_Reached": "%s_LoadReached" % P,
        "Manual_Mode": "%s_DriveManualMode" % P,
        "Moving": "%s_Moving" % P,
        "Position_Complete": "%s_PositionComplete" % P,
        "Push_Failed": "%s_PushFailed" % P,
        "Ready": "%s_DriveReady" % P,
        "Servo_On": "%s_ServoOn" % P,
        "Torque_Reached": "%s_TorqueReached" % P,
        "Total_Moving_Count": "%s_TotalMoveCount" % P,
        "Total_Moving_Distance": "%s_TotalMoveDistance" % P,
        "Map_Axis_Inputs": IN,
    })
    ops = call("SCON_Operations", "%s_Ops" % P, {
        "Servo_On": "%s_Cmd_ServoOn" % P,
        "Pause": "%s_Cmd_Pause" % P,
        "Inch_Select": "%s_Cmd_Inch" % P,
        "Jog_Forward": "%s_Cmd_JogFwd" % P,
        "Jog_Reverse": "%s_Cmd_JogRev" % P,
        "Reset": "%s_Cmd_Reset" % P,
        "Release_Brake": "%s_Cmd_BrakeRelease" % P,
        "Map_Axis_Outputs": OUT,
    })
    moves = call("SCON_Moves", "%s_Mov" % P, {
        "Home": "%s_Cmd_Home" % P,
        "Start_Move": "%s_Cmd_StartMove" % P,
        "Target_Position": "%s_Target" % P,
        "Target_Speed": SPEED,
        "Accel": ACCEL,
        "Decel": DECEL,
        "Position_Band": "Cfg_PosBand",
        "Increment_Select": "%s_Increment_Select" % P,
        "Push_Select": "%s_Push_Select" % P,
        "Push_Direction": "%s_Push_Direction" % P,
        "Push_Percent": "%s_Push_Percent" % P,
        "Load_Threshold_Percent": "%s_Load_Threshold" % P,
        "PZone_Upper_Limit": "%s_PZone_Upper" % P,
        "PZone_Lower_Limit": "%s_PZone_Lower" % P,
        "Map_Axis_Inputs": IN,
        "Map_Axis_Outputs": OUT,
    })
    return status, ops, moves


STATIONS = {
    "Station200_UpStacker.rungs": dict(
        TITLE="UP STACKER", P="UpAxis", MOD="IAI_UpStacker", CR="CR614",
        IN="UpStack_Inputs", OUT="UpStack_Outputs",
        SPEED="UpStack_Target_Speed",
        ACCEL="UpStack_Output_Acceleration",
        DECEL="UpStack_Output_Deceleration",
        LOMAX="Cfg_UpStack_LowMax_POS", HIMAX="Cfg_UpStack_HighMax_POS",
        TARGETTAG="UpStack_Target_Position", EXTRA=UPSTACK_EXTRA),
    "Station600_DownStacker.rungs": dict(
        TITLE="DOWN STACKER", P="DnAxis", MOD="IAI_DwnStacker", CR="CR615",
        IN="DwnStack_Inputs", OUT="DwnStack_Outputs",
        SPEED="DwnStack_Target_Speed",
        ACCEL="DwnStack_Output_Acceleration",
        DECEL="DwnStack_Output_Deceleration",
        LOMAX="Cfg_DwnStack_LowMax_POS", HIMAX="Cfg_DwnStack_HighMax_POS",
        TARGETTAG="DwnStack_Target_Position", EXTRA=DOWNSTACK_EXTRA),
}

# The old custom-AOI references, rewritten onto the new plain tags.
RENAMES = [
    ("Axis.Sts_Fault_Timeout", "{P}_Fault_Timeout"),
    ("Axis.Sts_Fault_Range", "{P}_Fault_Range"),
    ("Axis.Sts_Fault_Drive", "{P}_AlarmActive"),
    ("Axis.Sts_Fault", "{P}_Fault"),
    ("Axis.Sts_InPosition", "{P}_InPosition"),
    ("Axis.Sts_MoveDone", "{P}_MoveDone"),
    ("Axis.Sts_Position", "{P}_Position"),
    ("Axis.Sts_Target", "{P}_Target"),
    ("Axis.Sts_ServoOn", "{P}_ServoOn"),
    ("Axis.Sts_Homed", "{P}_HomeComplete"),
    ("Axis.Sts_EStop", "{P}_EStop"),
    ("Axis.Sts_Ready", "{P}_Ready"),
    ("Axis.Sts_Busy", "{P}_Busy"),
]


def main():
    for filename, subs in STATIONS.items():
        path = os.path.join(SRC, filename)
        text = open(path, encoding="utf-8").read()

        status, ops, moves = build_calls(
            subs["P"], subs["IN"], subs["OUT"],
            subs["SPEED"], subs["ACCEL"], subs["DECEL"])

        block = HEADER.format(STATUS_CALL=status, OPS_CALL=ops,
                              MOVES_CALL=moves, **subs).rstrip() + "\n"

        text, n = re.subn(r"@ROUTINE R100_AxisControl.*?(?=\n@ROUTINE )",
                          lambda _: block + "\n", text, flags=re.S)
        if n != 1:
            raise SystemExit("could not splice R100 into %s (matched %d)"
                             % (filename, n))

        for old, new in RENAMES:
            text = text.replace(old, new.format(P=subs["P"]))

        open(path, "w", encoding="utf-8").write(text)
        print("  %-34s R100 spliced, %d call(s) generated"
              % (filename, 3))


if __name__ == "__main__":
    main()
