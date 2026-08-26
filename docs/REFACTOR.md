# The refactored program

## One instruction owns the actuator

`IAI_SCON_Axis` is an Add-On Instruction wrapping one SCON drive. Both
stations use the same one, so the up stacker and the down stacker behave
identically and there is a single place to fix a motion bug.

```
CPS( IAI_UpStacker:I , UpStack_Inputs , 1 )
IAI_SCON_Axis( Axis , UpStack_Inputs , UpStack_Outputs )
CPS( UpStack_Outputs , IAI_UpStacker:O , 1 )
```

Only those three operands are on the instruction face. Everything else is on
the backing tag: `Axis.Cmd_MoveAbs`, `Axis.Sts_InPosition`, `Axis.Sts_Step`.

The body is Structured Text. A ten-step sequencer reads as ten steps in ST;
as ladder it would be another forty rungs of latches, which is roughly how
the program got into the state it was in.

### The one move command

```
Axis.Set_Position := 12500        (* 125.00 mm, units are 0.01 mm *)
Axis.Cmd_MoveAbs  := rising edge  (* go *)

Axis.Sts_Busy                     (* running *)
Axis.Sts_InPosition               (* arrived -- from the drive's PEND bit *)
Axis.Sts_MoveDone                 (* one-scan pulse on arrival *)
```

Nothing else starts a positioning move. The instruction range-checks the
target against `Cfg_Pos_Min`/`Cfg_Pos_Max`, loads the drive, pulses DSTR,
waits for the drive to accept it, then waits for PEND.

### Sequencer steps

`Axis.Sts_Step` says exactly where the axis is, which is the tag to watch
when troubleshooting:

| Step | Meaning |
|---:|---|
| 0 | initialising |
| 10 | not ready — no servo, not homed, or drive alarm |
| 20 | idle, ready and holding position |
| 30 | move: range check and load the target |
| 40 | move: DSTR asserted, waiting for the drive to accept |
| 50 | move: running, waiting for PEND |
| 60 | move: arrival confirmed |
| 70 | home: HOME asserted |
| 80 | home: waiting for HEND |
| 90 | jogging |

### Faults

| Output | Raised when |
|---|---|
| `Sts_Fault_Drive` | drive alarm (ALM). Code in `Sts_AlarmCode` |
| `Sts_Fault_Timeout` | move or home did not confirm inside `Cfg_Move_Timeout` |
| `Sts_Fault_Range` | commanded target was outside the travel limits, and was refused |
| `Sts_EStop` | drive E-stop (EMGS) |

`Sts_Fault` is the drive alarm or the timeout. `Sts_Fault_Range` is
deliberately excluded — a mistyped height is a bad command, not a broken
machine, and must not lock the operator out of simply retyping it. It clears
on the next accepted move or on reset.

`EnableInFalse` drops every command bit to the drive, so the actuator cannot
be left jogging if the calling rung is ever conditioned off.

## Program layout

Both programs, same five routines:

| Routine | Job |
|---|---|
| `R000_Main` | JSRs, in scan order |
| `R100_AxisControl` | the only routine that touches the drive: I/O copy, servo permissive, config, manual/auto arbitration, the AOI call, comms faults |
| `R200_Manual` | manual height control and jog |
| `R300_AutoSequence` | layer number to height, auto move requests, tray walk |
| `R400_TrayData` | Cognex results into the tray array, robot handshake |
| `R900_Alarms` | real alarms |

Scan order note: `R100` runs first, so it consumes the move requests `R200`
and `R300` produced on the previous scan and their status reads are always
fresh. One scan of command latency, which at a normal scan time is nothing
for a stacker.

## Manual operation

The headline change. Two steps, so a mistyped height cannot launch a move.

1. Type a height into `Man_Position_Entry` (0.01 mm — 12500 is 125.00 mm).
   Or type a layer into `Man_Layer_Entry` and press **GO TO LAYER**, which
   fills in the height using the same arithmetic the auto sequence uses.
2. Press **SET**. The height is range-checked against the travel limits and
   armed. Out of range sets `Man_Rejected` and arms nothing.
3. Press **GO**. The move runs.
4. `Man_Move_Confirmed` comes on when the drive confirms arrival — not when
   the move was merely started.

**JOG UP** / **JOG DN** run while held and stop at the software travel
limits.

Manual mode releases the axis from the auto sequence: `R300` will not request
a move while `Man_Mode` is on.

Safety carried over from the original: unlocking the doors drops the servo
permissive, so with the doors unlocked nothing moves regardless of what is
pressed on the faceplate.

### HMI faceplate tags

Program-scoped, so the path is
`Program:Program050000_Station200_UpStacker.<tag>` (and
`Program:Program090000_Station600_DownStacker.<tag>` for the down stacker).

| Tag | Type | Use |
|---|---|---|
| `Man_Mode` | BOOL | manual mode selector |
| `Man_Position_Entry` | DINT | height entry, 0.01 mm |
| `Man_Layer_Entry` | DINT | layer number for the helper |
| `Man_Set_PB` | BOOL | momentary — range-check and arm |
| `Man_Go_PB` | BOOL | momentary — confirm and run |
| `Man_GoToLayer_PB` | BOOL | momentary — fill the height from the layer |
| `Man_JogUp_PB` / `Man_JogDn_PB` | BOOL | held to run |
| `Man_Home_PB` | BOOL | momentary — home |
| `Man_Stop_PB` | BOOL | maintained — pause and block commands |
| `Man_Reset_PB` | BOOL | momentary — reset |
| `Man_Move_Armed` | BOOL | lamp: a height is armed, waiting for GO |
| `Man_Move_Active` | BOOL | lamp: move running |
| `Man_Move_Confirmed` | BOOL | lamp: arrived |
| `Man_Rejected` | BOOL | lamp: entry out of range |
| `Axis.Sts_Position` | DINT | actual height, 0.01 mm |
| `Axis.Sts_Target` | DINT | commanded height |
| `Axis.Sts_Step` | DINT | sequencer step, per the table above |
| `Axis.Sts_AlarmCode` | INT | drive alarm code |

`UpStack_Target_Position` / `DwnStack_Target_Position` are still written
every scan from `Axis.Sts_Target`, so existing HMI screens pointing at them
keep working.

## What changed in behaviour, deliberately

These are the changes that alter how the machine runs. Everything else is
structural.

1. **Interlocks now require confirmed in-position.**
   `Upstack_Count_Permission`, `DwnStack_Count_Permission` and the Cognex
   trigger were gated on "not moving"; they are gated on
   `Axis.Sts_InPosition` now. This closes the window where a permission
   could release against an axis that had not started moving yet.

2. **Stack completion is no longer blocked.** The `XIC(WinTest.0)` gate is
   gone, so `Upstack_Complete` can actually latch.

3. **The down stacker jam interlock now works.** The original
   `[XIO(DwnStack_Jam) ,]` branch had an empty leg, which is always true and
   shorted the interlock out. It is in series now.

4. **Alarms exist.** Six faults and three warnings per station, on the same
   `_Fault` / `_Warning` words the HMI already reads. See below.

5. **Out-of-range targets are refused and flagged** instead of silently
   dropped.

6. **Moves and homing are watchdogged.**

## Alarm map

Same `Station200Upstacker._Fault[n]` / `._Warning[n]` words as before.

| Bit | Up stacker | Down stacker |
|---:|---|---|
| Fault 0 | drive alarm | drive alarm |
| Fault 1 | move timeout | move timeout |
| Fault 2 | drive comms | drive comms |
| Fault 3 | camera comms | — |
| Fault 4 | tray missing (jam) | tray missing (jam) |
| Fault 5 | drive E-stop | drive E-stop |
| Warning 0 | height refused, out of range | height refused, out of range |
| Warning 1 | axis not homed | axis not homed |
| Warning 2 | manual mode selected | manual mode selected |

## Tray layout is data now

The eight hard-coded Cognex offsets became a lookup:

```
MOV( Cfg_Cognex_Offset[UpStack_Row_Fill, UpStack_Column_Fill], Cognex_Control_X1 )
```

`Cfg_Cognex_Offset` is `DINT[5,7]`, indexed `[row, column]`, pre-loaded with
the current 2 x 4 values (0, 6, 24, 30 / 48, 54, 72, 78). Y is X+1, angle is
X+2, and the second inspection is +12.

To move to a 12-hole tray: set `Cfg_Row_Max` and `Cfg_Column_Max`, extend the
Cognex job to report the extra positions, and fill in their offsets here. No
logic changes. See the note at the end of `ANALYSIS.md` — the camera job and
the intended layout are yours to decide.

## Before you run it

Things this refactor cannot verify from an offline export:

- **Jog direction.** The logic assumes extend (JOG+) raises the stacker, i.e.
  increasing position is up, which is consistent with the layer arithmetic
  (layer 0 is the top of travel). Confirm on first power-up. If it is
  reversed, swap the two `OTE`s at the end of `R200_Manual`.
- **Jog speed.** `Cmd_JogUp`/`Cmd_JogDn` use the drive's JOG bits, and the
  jog speeds come from the SCON's own parameters, not from the PLC.
  `Cfg_JogFast` picks between jog speed 1 and 2 via JVEL. Check what those
  parameters are set to on your drives before jogging with the guard open.
  `Manual_Select` (RMOD) is deliberately left at 0 — the drive stays in auto
  mode, where both positioning and jog work.
- **`Cfg_PosBand`** defaults to 50 (0.50 mm) and **`Cfg_MoveTimeout`** to
  15000 ms. Both are guesses at sane values; tune them to the machine.
- **Accel/decel are 1** (0.01 G) in the existing config, carried over
  unchanged. That is very gentle. If moves feel slow, that is why — but it
  was the original setting, so it is left alone.
- The Cognex, robot handshake and tray-array logic is carried over with the
  same behaviour, only split into readable rungs. It has not been redesigned,
  and it has not been tested.

## Import order

1. `export/IAI_SCON_Axis.L5X` — the Add-On Instruction, first.
2. `export/Program050000_Station200_UpStacker.L5X`
3. `export/Program090000_Station600_DownStacker.L5X`

Import the programs as a replacement for the existing ones. New tags are
program-scoped so they are created by the import; the controller tags, the
robot handshake and the module configuration are referenced, not modified.

Then delete the now-unused controller tags if you want them gone:
`Upstack_Layer_Temp`, `DwnStack_Layer_Temp`, `Upstack_Start_HLD_TMR`,
`DwnStack_Start_HLD_TMR`, `WinTest`, `PlaceHolderBit`. Check nothing else in
the project references them first.

## Rebuilding

The `.L5X` files in `export/` are generated. Edit the readable sources in
`src/` and rebuild:

```
python3 tools/build_l5x.py     # regenerate export/
python3 tools/check_refs.py    # resolve every tag and ST identifier
```

`check_refs.py` cross-checks every operand in every rung against the program
tags, controller tags, module names, AOI parameters and UDT members, and
every identifier in the AOI's Structured Text against its parameters and
locals. It also rejects nested `(* *)` comments, which Logix will not
compile. It caught two real defects while this was being written.

It is not a Studio 5000 compiler. It will not catch a semantic error, and it
cannot tell you the machine is safe.
