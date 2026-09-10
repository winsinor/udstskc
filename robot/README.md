# Robot side — minimal change

**Nothing inside any station program changes.** `Station200_UpStacker`, `Station300_LaserMarker`,
`Station400_IMM`, `Station500_SprueCutter`, `Station500_Reject` and `Station600_DownStacker` are
called exactly as they exist today — same condition bits, same inline reject calls, same timers.

The only thing replaced is the **priority-poll loop in `Main.src`**, which becomes a dispatcher.

| File | What it is |
|---|---|
| `Main_New.src` | The dispatcher. Install as `Main.src`; keep the old one as `Main_Legacy.src`. |
| `CmdIface.src` / `.dat` | Two helpers and the latched command snapshot. ~50 lines. |
| `CONFIG_ADDITIONS.dat` | SIGNAL declarations for `$config.dat`. **Addresses are placeholders.** |

`Main.dat` is unchanged.

## The one thing the PLC has to do differently

Two station programs contain two behaviours each, selected by a condition bit, and that is left
alone. **The PLC must set the bit before issuing the command:**

| Routine | PLC sets first | Then calls |
|---|---|---|
| 20 PickUpstacker | `UStoR_ReqToMoveLayer` = FALSE | `Station200_UpStacker()` |
| 80 LayerShift | `UStoR_ReqToMoveLayer` = TRUE | `Station200_UpStacker()` |
| 30 PlaceTurntable | `TTtoR_ReqToPlace` = TRUE | `Station300_LaserMarker()` |
| 40 PickTurntable | `TTtoR_ReqToPickGood` or `...PickBad` = TRUE | `Station300_LaserMarker()` |
| 90 Reject | — | `Rjct_1Blnk_2Fin_3Both` = `Cmd_P1`, then `Station500_Reject()` |

Tray row and column still arrive in `UStoR_PickRowNumber` / `UStoR_PickColumnNumber` exactly as
today. Nothing about that changes.

## Faults

The stations already set `RobotCell_Error` when they fail. The dispatcher checks it after every
call and reports fault **100** — that one hook turns a silent internal failure into something the
PLC can see and hold on. It costs nothing and touches no station code.

Fault **101** is an unknown routine ID.

That is all the fault detail available without modifying stations. A station that rejects parts
internally still does so, and still reports only `RobotCell_Error`. Finer fault codes are a later
change, if you want them.

## Install order

1. **`$config.dat` off the controller.** `XHOME` and `FHOME` live there; nothing moves without it.
2. Work out the real bit addresses (arithmetic is in `CONFIG_ADDITIONS.dat`) and paste the SIGNAL
   block in.
3. **Test byte order** — procedure at the bottom of `CONFIG_ADDITIONS.dat`. A KUKA/Rockwell byte
   swap presents as "the robot ignores my commands", not as a byte swap.
4. Copy `CmdIface.src` / `.dat` to `KRC:\R1\Program`.
5. Rename `Main.src` to `Main_Legacy.src`, install `Main_New.src` as `Main.src`.
6. Select `Main` in Ext Auto.

## What this does and does not buy

**Does:** the PLC chooses which station runs and when, and gets a held answer back — Complete or
Faulted, surviving a slow scan or a PLC fault.

**Does not:** change how any station behaves internally. They still self-reject, still share
`$TIMER[2]`, still read their own condition bits. Those are all still on the list; none of them
blocks commanding the cell from the PLC.
