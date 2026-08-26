# The refactored program

## The vendor instructions do the drive interface

IAI supplies three Add-On Instructions with the SCON drives. They were in the
project all along and the original program used none of them — it hand-wrote
the bit manipulation instead. They are now the whole drive interface, imported
unmodified:

| Instruction | What it does |
|---|---|
| `SCON_Status` | unpacks the drive input image into readable tags |
| `SCON_Operations` | writes servo on, pause, jog, reset, brake release |
| `SCON_Moves` | writes home and the positioning move, and owns the START (DSTR) handshake |

`SCON_Moves` is the important one. Its rung 6 latches START and loads the
move data on a rising edge; its rung 7 drops START once the drive
acknowledges by clearing POSITION COMPLETE. That is the handshake the
original program never performed, and it comes from the vendor — nothing
here reimplements it.

Everything else is plain ladder in the program. **There is no custom
Add-On Instruction.**

## The step sequencer

Plain ladder in `R100_AxisControl`. `<prefix>_Step` (`UpAxis_Step`,
`DnAxis_Step`) is the tag to watch:

| Step | Meaning |
|---:|---|
| 0 | initialising |
| 10 | not ready — no servo, not homed, drive alarm, or E-stop |
| 20 | idle, ready and holding position |
| 30 | move: range-check the target and load it |
| 35 | move: hand the move to `SCON_Moves` (one scan) |
| 40 | move: waiting for the drive to accept it |
| 50 | move: running, waiting for POSITION COMPLETE |
| 60 | move: arrival confirmed (one scan) |
| 70 | home: hand the home request to `SCON_Moves` |
| 80 | home: waiting for HOME COMPLETE |
| 90 | jogging |

Two rules keep it correct, and both matter if you edit it:

1. **Every command tag is written by exactly one rung**, and that rung names
   the step that owns it. No duplicate destructive bits. `tools/check_refs.py`
   enforces this.
2. **The transition rungs are in descending step order.** That is what limits
   the sequencer to one step per scan. In ascending order a move would run
   30-35-40 in a single scan and the start pulse would never reach
   `SCON_Moves`.

Stuck at 40 means the drive is not accepting the command; stuck at 50 means
it accepted and is not arriving. Different faults, and now distinguishable.

### The move command

```
<prefix>_Set_Position   the height you want, 0.01 mm
<prefix>_Move_Req       one-scan pulse: go

<prefix>_Busy           running
<prefix>_InPosition     arrived -- from the drive's POSITION COMPLETE
<prefix>_MoveDone       one-scan pulse on arrival
```

### Faults

| Tag | Raised when |
|---|---|
| `<prefix>_AlarmActive` | drive alarm (ALM). Code in `<prefix>_AlarmCode` |
| `<prefix>_Fault_Timeout` | move or home did not confirm inside `Cfg_MoveTimeout` |
| `<prefix>_Fault_Range` | commanded target was outside the travel limits, and was refused |
| `<prefix>_EStop` | drive E-stop (EMGS) |

`<prefix>_Fault` is the drive alarm or the timeout. `_Fault_Range` is
deliberately excluded — a mistyped height is a bad command, not a broken
machine, and must not lock the operator out of retyping it.

`<prefix>_Motion_OK` gates every command rung, so a fault drops the command
bits in the same scan it appears; the abort rung then sends the sequencer
back to step 10.

## Program layout

Both programs, same five routines:

| Routine | Job |
|---|---|
| `R000_Main` | JSRs, in scan order |
| `R100_AxisControl` | the only routine that touches the drive: I/O copy, the three vendor instructions, servo permissive, config, manual/auto arbitration, the step sequencer, watchdog, comms faults |
| `R200_Manual` | manual height control and jog |
| `R300_AutoSequence` | layer number to height, auto move requests, tray walk |
| `R400_TrayData` | Cognex results into the tray array, robot handshake |
| `R900_Alarms` | real alarms |

Scan order note: `R100` runs first, so it consumes the move requests `R200`
and `R300` produced on the previous scan and their status reads are always
fresh. One scan of command latency, which at a normal scan time is nothing
for a stacker.

`R100` is longer than the others (about 46 short rungs) because it is the
whole axis, read top to bottom: read the drive, decide, sequence, write the
drive. That is the cost of not hiding it in an instruction, and it is the
point — every part of it is visible on a rung you can watch online.

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
| `UpAxis_Position` | DINT | actual height, 0.01 mm |
| `UpAxis_Target` | DINT | commanded height |
| `UpAxis_Step` | DINT | sequencer step, per the table above |
| `UpAxis_AlarmCode` | INT | drive alarm code |

(Down stacker: same names with the `DnAxis_` prefix.)

`UpStack_Target_Position` / `DwnStack_Target_Position` are still written
every scan from `UpAxis_Target` / `DnAxis_Target`, so existing HMI screens
pointing at them
keep working.

## What changed in behaviour, deliberately

These are the changes that alter how the machine runs. Everything else is
structural.

1. **Interlocks now require confirmed in-position.**
   `Upstack_Count_Permission`, `DwnStack_Count_Permission` and the Cognex
   trigger were gated on "not moving"; they are gated on
   `UpAxis_InPosition` / `DnAxis_InPosition` now. This closes the window where a permission
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
- **Jog speed.** Jog goes through `SCON_Operations` (JOG+/JOG-), and the jog
  speeds come from the SCON's own parameters, not from the PLC. `Cfg_JogFast`
  picks between jog speed 1 and 2 via JVEL — that bit is written directly to
  the output image because `SCON_Operations` does not expose it. Check what
  those drive parameters are set to before jogging with the guard open.
  `Manual_Select` (RMOD) is left at 0: the drive stays in auto mode, where
  both positioning and jog work.
- **`Cfg_PosBand`** defaults to 50 (0.50 mm) and **`Cfg_MoveTimeout`** to
  15000 ms. Both are guesses at sane values; tune them to the machine.
- **Accel/decel are 1** (0.01 G) in the existing config, carried over
  unchanged. That is very gentle. If moves feel slow, that is why — but it
  was the original setting, so it is left alone.
- The Cognex, robot handshake and tray-array logic is carried over with the
  same behaviour, only split into readable rungs. It has not been redesigned,
  and it has not been tested.

## What has and has not been verified

Everything here was built and checked offline. There is no Studio 5000 in this
environment, so **nothing below has been compiled or downloaded**, and this is
not a claim that the import will be clean.

Checked mechanically by `tools/check_refs.py`, on every rung of both programs:

- every operand resolves to a program tag, a controller tag, a module name,
  an alias tag, a UDT member or a routine name
- every instruction mnemonic is a real one
- every rung ends in a semicolon; branch brackets and parentheses balance
- no bit is driven by two OTEs (the duplicate destructive bit Logix rejects)
- each `SCON_*` call passes the backing tag plus one argument per Required
  parameter, counted from IAI's own definition

Checked by construction:

- the program files are the original exports with only the `<Program>`
  element replaced, so the controller context, data types, modules and tag
  dependencies are byte-for-byte the originals
- tag and Program elements use the same attribute set Studio 5000 emits
- the three IAI AOI files are copied through unmodified (SHA-256 identical to
  the vendor files)
- structured tags (TIMER, the AOI backing tags) carry no `<Data>` element, so
  Studio 5000 initialises them from the type definition rather than from a
  hand-built structure that could have a member wrong

**The one thing that could not be verified offline:** the argument list of an
AOI call. Logix passes the backing tag plus every `Required` parameter in
declaration order, which is what is generated here. IAI's AOIs also declare an
`EN` output as `Visible` but not `Required`; if Studio 5000 disagrees about
whether that takes an argument slot, the three `SCON_*` rungs in
`R100_AxisControl` will be rejected on import. Each call is on its own rung
with nothing else in it, so the fix is to delete that rung and drag the
instruction in from the toolbar. Nothing else in either program is affected.

Import into a copy of the project, or an offline one, and verify before you
download.

## Import order

1. `export/SCON_Moves_AOI.L5X` — one file, installs all three IAI
   instructions. Skip it if they are already in the project; it is IAI's
   file byte for byte, so importing it again changes nothing.
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
tags, controller tags, module names, vendor AOI parameters and UDT members.
It also checks that every rung ends in a semicolon, that branch brackets and
parentheses balance, and that no bit is driven by two OTEs — the duplicate
destructive bit that Logix rejects on verify and the classic way a ladder
step sequencer goes wrong.

The AOI call operand lists are generated from IAI's own definitions rather
than typed by hand: Logix expects every Required parameter in declaration
order, and `SCON_Status` alone takes 25 operands.

It is not a Studio 5000 compiler. It will not catch a semantic error, and it
cannot tell you the machine is safe.
