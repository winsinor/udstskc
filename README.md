# Up stacker / down stacker refactor

Allen-Bradley Logix (v35) programs for the two IAI SCON actuators on the
Station 200 up stacker and the Station 600 down stacker, stripped down and
rebuilt around a single confirmed move command.

## The change in one paragraph

The original had no way to command a height. The only thing that started a
move was the layer counter changing value, nothing ever confirmed arrival,
and there was no manual mode at all — the SCON jog bits were mapped in the
UDT and never used. Both actuators now run on one Add-On Instruction with a
single move command (`Set_Position` + a `Cmd_MoveAbs` edge) that confirms
arrival from the drive's own PEND bit, plus held-to-run jog with software
travel limits and a two-step set-then-confirm height entry.

## Layout

```
source/    the original exports, untouched, for reference
src/       the readable sources -- ST, ladder, tag lists
tools/     build and verification scripts
export/    generated .L5X files, ready to import
docs/      ANALYSIS.md -- what the original did, and what was wrong with it
           REFACTOR.md -- the new design, tag reference, commissioning notes
```

## Import order

1. `export/IAI_SCON_Axis.L5X` (the AOI, first)
2. `export/Program050000_Station200_UpStacker.L5X`
3. `export/Program090000_Station600_DownStacker.L5X`

## Manual operation

Type a height into `Man_Position_Entry` (0.01 mm), or a layer into
`Man_Layer_Entry` and press **GO TO LAYER** to fill the height in. Press
**SET** to range-check and arm it, then **GO** to run it.
`Man_Move_Confirmed` comes on when the drive confirms arrival.

**JOG UP** / **JOG DN** run while held and stop at the travel limits.

Full tag reference in [`docs/REFACTOR.md`](docs/REFACTOR.md).

## Rebuilding

```
python3 tools/build_l5x.py     # regenerate export/ from src/
python3 tools/check_refs.py    # verify every tag and identifier resolves
```

## Read this before commissioning

Jog direction, jog speed, the in-position band and the move timeout cannot be
verified from an offline export. The
[commissioning notes](docs/REFACTOR.md#before-you-run-it) list what to check
on first power-up, and
[the behaviour changes](docs/REFACTOR.md#what-changed-in-behaviour-deliberately)
list what now runs differently on purpose.
