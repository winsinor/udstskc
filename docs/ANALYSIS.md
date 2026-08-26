# What the original program did

Read from the two exports in `source/`, taken from a Logix v35.04 project
(`RS_Rev35011_691904_NPE`, KraussMaffei).

## Shape

Both programs had the same skeleton, and it was mostly empty:

| Routine | Rungs | What was actually in it |
|---|---:|---|
| `Routine0x0100_Main` | 5 | five JSRs |
| `Routine0x0300_InputStatus` | 1 | `NOP()` |
| `Routine0x0500_Operation` | 14 / 10 | **everything** |
| `Routine0x0600_AutoSequence1` | 1 | `NOP()` |
| `Routine0x0700_OutputActions` | 1 | `NOP()` |
| `Routine0x9999_Alarms` | 67 | 64 rungs of boilerplate, all dead |

Three of the six routines were empty shells. All the logic — I/O copy, servo
control, fault handling, motion, the Cognex vision interface, the tray data
model and the robot handshake — was in one routine, in rungs that ran up to
1,700 characters and eight branch levels deep.

## The actuators

Two IAI SCON drives on EtherNet/IP in direct numerical specification mode,
mapped through two UDTs (`SCON_Inputs`, `SCON_Outputs`) that are complete and
well documented — every SCON flag is there with its mnemonic.

Configured travel, from the tag values in the export:

| | Up stacker | Down stacker |
|---|---:|---:|
| `LowMax_POS` | 1200 (12.00 mm) | 1200 (12.00 mm) |
| `HighMax_POS` | 28525 (285.25 mm) | 28377 (283.77 mm) |
| `TrayHeight` | 2159 (21.59 mm) | 2250 (22.50 mm) |
| `Target_Speed` | 10000 (100.00 mm/s) | 10000 (100.00 mm/s) |
| `Accel` / `Decel` | 1 / 1 (0.01 G) | 1 / 1 (0.01 G) |

## How motion actually worked

Three rungs, spread across the Operation routine:

```
rung 1   CPT( UpStack_Target_Position ,
              Cfg_UpStack_HighMax_POS - (Upstack_Layer_Current * Cfg_UpStack_TrayHeight) )

rung 2   GEQ( target, LowMax ) LEQ( target, HighMax )
             MOV( target, UpStack_Outputs.Target_Position )

rung 3   [ NEQ( Layer_Current, Layer_Temp ) MOV( Layer_Current, Layer_Temp )
           TOF( Start_HLD_TMR ) , XIC( Start_HLD_TMR.DN ) ]
         XIO( UpStack_Inputs.Moving )
             OTE( UpStack_Outputs.Start_Move )
```

That is the whole motion system, and it has four problems.

### 1. There is no way to command a height

The target is a pure function of `Upstack_Layer_Current`, and the *only*
thing that starts a move is that layer number changing value. To move the
actuator anywhere you had to write a layer number into the sequence counter
and let the arithmetic decide where that lands. There was no manual mode, no
jog, and no way to say "go to 150 mm".

### 2. Nothing confirms arrival

`Start_Move` is gated on `XIO(Moving)` and nothing anywhere reads
`Position_Complete` (PEND) — the drive's own arrival flag, which is sitting
right there in the UDT, fully commented.

This matters beyond tidiness. The downstream interlocks were written as:

```
XIO(UpStack_Outputs.Start_Move) XIO(UpStack_Inputs.Moving) ... OTE(Upstack_Count_Permission)
```

"Not starting and not moving" is also true in the window *between* the
command being issued and the drive picking it up. The permission could
therefore release against an axis that had not begun to move yet.

### 3. A move that never completes hangs silently

No timeout anywhere. If the actuator stalled, the sequence simply stopped,
with nothing latched to say why.

### 4. An out-of-range target looks like a dead machine

Rung 2's `GEQ`/`LEQ` gate means an out-of-limits target is never written —
silently. The previous setpoint stays loaded, no alarm is raised, and the
machine just sits there.

## The jog bits were already there

`SCON_Outputs` defines `Jog_Forward` (JOG+), `Jog_Reverse` (JOG-),
`Inch_Select` (JISL), `Jog_Parameter_Select` (JVEL), `Manual_Select` (RMOD)
and `Release_Brake` (BKRL). Not one of them is referenced anywhere in either
program. The hardware capability for manual control was mapped and then
never used.

## Dead code

- **`XIC(WinTest.0)`** gating `OTL(Upstack_Complete)` in up stacker rung 10.
  `WinTest` is a `DINT` sitting at 0, so the up stack could never report
  complete unless someone set that bit by hand. A test gate left in.
- **`AFI()` branches** in down stacker rungs 6 and 7, and in up stacker rung
  1. `AFI` forces a branch permanently false. The pair in the down stacker
  disabled setting *and* clearing `DwnStack_Complete`.
- **`[XIO(DwnStack_Jam) ,]`** in down stacker rung 5 — a branch with an empty
  leg. An empty leg is always true, so this shorted the jam interlock out
  entirely rather than enforcing it.
- **`MOV(x,x)` self-moves** — four in up stacker rung 1, four in the down
  stacker. A trick to force HMI updates; they do nothing to the logic and
  make the rung harder to read.
- **The alarm routines.** 32 warning rungs and 32 fault rungs, each an
  identical template conditioned on `XIC(PlaceHolderBit)`. Not one alarm
  condition was ever filled in, so neither station could raise an alarm.

## Magic numbers

- `MOV(13, Upstack_Layer_Current)` on door open — 13 is `Cfg_Layer_Max + 1`.
- `GEQ(DwnStack_Layer_Current, 13)`, `LEQ(..., 12)` — same constant, spelled
  two different ways.
- `LES(IS3800:I.InspectionResults[96], 50)` — 50 is the tray-present score
  threshold.
- The eight Cognex result offsets (0, 6, 24, 30, 48, 54, 72, 78), hard-coded
  as nested `EQU`/`MOV` pairs, which is what froze the tray layout in logic.

## A note on tray size

The tray is described as having 12 holes, but the program is configured for
8:

```
Cfg_Row_Max    = 2
Cfg_Column_Max = 4
```

and the Cognex offset table in rung 6 only covers those 8 positions. The
underlying data type has room for more — `Data_Row` is `Row[4]` of
`Data_Column`, which is `Column[6]` of `Data_Item`, so up to 24 positions per
layer — and `IS3800:I.InspectionResults[96]`/`[97]` are the two tray-presence
scores, implying the 96 result words below them are 8 positions x 12 words.

So the array and the camera map are both sized for 8 today. Going to 12
(2 x 6, or 3 x 4) needs `Cfg_Row_Max`/`Cfg_Column_Max` changed, the Cognex
job extended to report the extra positions, and the offset table filled in.
The refactor makes that last part data rather than logic, but **the camera
job and the config values are yours to set** — worth confirming which layout
you actually want before commissioning.
