# Up stacker / down stacker refactor

Allen-Bradley Logix (v35) programs for the two IAI SCON actuators on the
Station 200 up stacker and the Station 600 down stacker, stripped down and
rebuilt around a single confirmed move command.

## The change in one paragraph

The original had no way to command a height. The only thing that started a
move was the layer counter changing value, nothing ever confirmed arrival,
and there was no manual mode at all. Both actuators now run through IAI's own
`SCON_Status` / `SCON_Operations` / `SCON_Moves` Add-On Instructions — which
shipped with the drives and were never used — driven by a plain-ladder step
sequencer in the program. A single move command confirms arrival from the
drive's POSITION COMPLETE bit, with held-to-run jog inside software travel
limits and a two-step set-then-confirm height entry.

**No custom Add-On Instruction.** The only AOIs are IAI's, imported
unmodified; everything else is ordinary ladder you can open and watch.

## Layout

```
source/    the original exports, untouched, for reference
source/iai/  IAI's three SCON Add-On Instructions, as supplied
src/       the readable sources -- ladder and tag lists
tools/     build and verification scripts
export/    generated .L5X files, ready to import
docs/      ANALYSIS.md -- what the original did, and what was wrong with it
           REFACTOR.md -- the new design, tag reference, commissioning notes
```

## Import order

1. `export/SCON_Moves_AOI.L5X` — installs all three IAI instructions
   (`SCON_Status`, `SCON_Operations`, `SCON_Moves`) in one file. Skip if
   they are already in the project.
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

## Before you import

Everything here was built and checked offline — there is no Studio 5000 in
the environment it was written in, so **none of it has been compiled**.
`tools/check_refs.py` verifies every operand, instruction, bracket and
duplicate output mechanically, and the program files are the original exports
with only the `<Program>` element swapped, but that is not the same as a
successful verify. Import into a copy of the project first. See
[what has and has not been verified](docs/REFACTOR.md#what-has-and-has-not-been-verified).

## Read this before commissioning

Jog direction, jog speed, the in-position band and the move timeout cannot be
verified from an offline export. The
[commissioning notes](docs/REFACTOR.md#before-you-run-it) list what to check
on first power-up, and
[the behaviour changes](docs/REFACTOR.md#what-changed-in-behaviour-deliberately)
list what now runs differently on purpose.
