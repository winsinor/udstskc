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

## How the machine cycle worked

There is no state machine anywhere in the original. The machine's state is
the combination of about fifteen latched bits and six counters, and the whole
cycle is driven by **one counter walking down**: `Upstack_Layer_Current`.

### The two stackers are mirror images

Both use the same arithmetic:

```
target = HighMax_POS - (Layer_Current * TrayHeight)
```

so **layer 0 is the top of travel** and a higher layer number is a lower
platform.

- The **up stacker counts down**. It starts at the tray count and
  decrements. Layer decreasing means position increasing, so the platform
  **rises** as trays are consumed — keeping the top tray at a constant pick
  height for the robot.
- The **down stacker counts up**. It increments as trays arrive, so the
  platform **descends** as the stack builds — keeping the top tray at a
  constant place height.

### The cycle, start to finish

**1. Doors open.** `Door_Open_Request` sends both stackers to `LowMax_POS`
(12 mm, the bottom) and writes 13 into both layer counters. The operator
loads a full stack of parts into the up stacker and empty trays into the down
stacker.

**2. Doors close.** `Upstack_Complete_TMR` times out, then loads
`UpStack_HMI_Tray_Qty` into both `Upstack_Layer_Current` and
`Upstack_Layer_Last` (same for the down stacker). That HMI number is the
operator telling the machine how many trays are in the stack.

**3. The layer counter changing is what moves the axis.** `Layer_Current` now
differs from `Layer_Temp`, so rung 3 fires `Start_Move` and the stacker
travels to that layer's height. This is the only motion trigger in the
program.

**4. The camera fires.** The down stacker latches `Trigger_Cognex` once
nothing is moving; the up stacker program services it — arms
`IS3800:O.Control.TriggerEnable`, waits for `Cognex_Hold_TMR.ACC > 500`, then
pulses `Trigger`. One camera shot covers **both** trays, which is why the
request originates in one program and the camera lives in the other.

**5. Results are unpacked into the tray array.** A changed `AcquisitionID`
latches `UpStack_Status_Fill` + `UpStack_Fill_Trays`. After `Data_Delay_TMR`:

- `InspectionResults[96]` and `[97]` are the tray-present scores for the up
  and down trays. Below 50 latches `Upstack_Jam` / `DwnStack_Jam`.
- A walker (rung 5) steps column 1→4 then row 1→2, one cell per scan,
  pulsing `New_Fill_Item`.
- For each cell, rung 6 looks up that hole's result offset from the
  hard-coded table (0, 6, 24, 30 / 48, 54, 72, 78) and loads X1, X2 (=X1+12),
  Y1, Y2, A1, A2 into the cell. **If either X is non-zero the hole is marked
  occupied**; if both are zero the cell is cleared. That is the entire
  part-present test.

**6. The pick walk.** Rung 10 is the heart of the machine, gated by two bits:

- `Upstack_Count_Permission` (rung 8) — door shut, not moving, no layer move
  pending, no jam, not complete, data delay done, no pick already
  outstanding.
- `Upstack_Count_Request` (rung 9) — turn table not full, or a fresh layer
  from the camera, or the robot just took the last hole in the tray, or a
  turn table slot is free.

With both true it increments the column pointer and asks: is this cell's
`Status` equal to 1 (occupied)? If yes, bump `UStoR_PickSeqNumber` and latch
`UStoR_ReqToPick`. If no, nothing happens and the counter simply walks past
on the next scan — **that is how empty holes get skipped**.

Column past 4 → next row, column back to 0. Row past 2 → decrement the layer
and latch `UStoR_ReqToMoveLayer`. Layer at 0 → the stack is done.

**7. Hand-off to the robot.** `UStoR_ReqToPick` publishes row and column to
`UStoR_PickRowNumber` / `UStoR_PickColumnNumber` and stamps the sequence
number into the tray cell. On `RtoUS_PickConfirm` the whole cell is copied
into `Data_Item[UStoR_PickSeqNumber]`, that record's Status becomes 2, the
tray cell is marked complete, and the request clears.

**8. Empty tray.** `UStoR_ReqToMoveLayer` asks the robot to slide the empty
tray across to the down stacker. `RtoUS_LayerMovedConfirm` clears the request
in the up stacker and increments `DwnStack_Layer_Current` in the down
stacker — which, being a layer change, is what makes the down stacker move.

**9. The down stacker side** runs its own smaller version of the same walk:
`DwnStack_Count_Permission` plus rung 6 steps its column/row pointers and
latches `DStoR_OpenLocation` for each free hole. Rung 8 publishes the
location; `RtoDS_PlacedConfirm` copies the part's travelling record into the
down stacker tray cell. Row past max latches `DwnStack_Full_Layer`.

**10. Completion.** `Upstack_Complete` latches `Door_Open_Request` once
everything has stopped, both stackers return to the bottom, the tray counts
reload from the HMI, and the cycle repeats.

### Part tracking

`Data_Item[500]` is the travelling database. `UStoR_PickSeqNumber` rolls
1..490 and indexes it. Each record carries the original X/Y/angle the camera
measured on the up stacker, plus a Status saying where the part is:

```
0 = not present            4 = robot picked from turn table
1 = present in upstack     5 = robot placed in downstack
2 = robot picked from upstack   6 = robot placed in chute
3 = turn table ready for pickup
```

So a part keeps its measured pose from the moment it is seen on the up
stacker all the way through the turn table to the down stacker. `TurnTable[5]`
holds the records for parts currently on the turn table.

The turn table and robot programs are **not** in these two exports — the up
stacker only reads `Turn_Table_Full`, `TurnTable[n].Seq_Num`,
`TurnTable_Move_ONS` and `RtoTT_PickConfirm` from elsewhere in the project.

### Resuming after a door open

A subtle bit worth knowing, in up stacker rung 1. Opening the doors stomps
`Layer_Current` to 13, but the branch that saves `Layer_Current` into
`Layer_Last` is gated on the door being shut — so `Layer_Last` keeps the
pre-interruption value. When the doors close, a `TON` runs and a one-shot
restores `Layer_Current := Layer_Last`. That is how the machine picks up
mid-stack instead of starting over. The completion path in rung 11 overwrites
both from `UpStack_HMI_Tray_Qty`, which is what starts a genuinely fresh
stack.

### The two programs are tightly coupled

They are not independent stations. The up stacker sets `Door_Open_Request`
and both read it; the down stacker requests the camera and the up stacker
fires it; the up stacker's rung 4 latches `DwnStack_Jam` and its rung 11
reloads the down stacker's layer counters. Neither program can be understood
or modified on its own.

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
