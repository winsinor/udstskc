# Up stacker / down stacker — barebones axis

Two Logix programs, one per IAI SCON actuator. Each is **two routines and
six rungs**: read the drive, turn the servo on, hand the move to IAI's own
Add-On Instructions, write the drive. Nothing else — no sequencing, no
tray logic, no alarms. That is yours to add.

## To move the actuator

```
set    UpAxis_Target         where to go, in 0.01 mm   (12500 = 125.00 mm)
pulse  UpAxis_Cmd_StartMove  SCON_Moves takes the rising edge
```

That is the whole command. Then watch:

```
UpAxis_Position          where it actually is, 0.01 mm
UpAxis_Moving            running
UpAxis_PositionComplete  arrived        <-- the confirmation (PEND)
UpAxis_AlarmActive       faulted, code in UpAxis_AlarmCode
```

Down stacker is identical with the `DnAxis_` prefix.

Also wired and ready if you want them: `Cmd_JogFwd` / `Cmd_JogRev` (run while
held), `Cmd_Home` (rising edge), `Cmd_Reset`, `Cmd_Pause`.

## The rungs

```
R000_Main       JSR(R100_Axis,0)

R100_Axis   0   CPS(IAI_UpStacker:I, UpStack_Inputs, 1)
            1   SCON_Status(...)          unpack the drive into UpAxis_* tags
            2   servo permissive + CR614  (drops with the doors unlocked)
            3   SCON_Operations(...)      servo, jog, reset, pause
            4   SCON_Moves(...)           home and the positioning move
            5   CPS(UpStack_Outputs, IAI_UpStacker:O, 1)
```

`SCON_Moves` owns the START handshake: it latches START with the move data on
the rising edge and drops it when the drive acknowledges by clearing POSITION
COMPLETE. Nothing here reimplements that.

Speed, accel and decel come from the controller tags that were already there —
`UpStack_Target_Speed`, `UpStack_Output_Acceleration`,
`UpStack_Output_Deceleration`.

## Tags

44 program-scoped tags per station. Nearly all of them exist only because
IAI's instructions require an argument for every parameter — 23 of them are
status outputs from `SCON_Status`. The two you touch to move the axis are
`UpAxis_Target` and `UpAxis_Cmd_StartMove`.

HMI path: `Program:Program050000_Station200_UpStacker.<tag>`.

## Import order

1. `export/SCON_Moves_AOI.L5X` — all three IAI instructions in one file.
   Skip if they are already in the project.
2. `export/Program050000_Station200_UpStacker.L5X`
3. `export/Program090000_Station600_DownStacker.L5X`

## Layout

```
source/      the original exports, untouched
source/iai/  IAI's three SCON Add-On Instructions, as supplied
src/         the readable sources — ladder and tag lists
tools/       build and verification scripts
export/      generated .L5X files, ready to import
docs/        ANALYSIS.md — what the original program did, and its problems
```

## Rebuilding

```
python3 tools/make_axis_ladder.py   # regenerate src/ ladder and tag lists
python3 tools/build_l5x.py          # regenerate export/ from src/
python3 tools/check_refs.py         # verify every operand resolves
```

## Notes

- **Jog direction is unverified.** `Cmd_JogFwd` is extend (JOG+). Which way
  that moves the stacker needs checking on the machine.
- **No range check on `Target`.** The drive's own soft stroke limits are the
  only guard. For reference, the original program ran between 1200 and 28525
  (12.00–285.25 mm) on the up stacker, 1200 and 28377 on the down stacker.
- The previous version of this branch had the full sequencing, manual
  faceplate, tray data and alarm logic. It is in the git history if you want
  anything back, and the original program is untouched in `source/`.
