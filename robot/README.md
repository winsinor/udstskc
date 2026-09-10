# Robot side — two files

| File | What |
|---|---|
| `Main.src` | The stock KUKA CELL template with the dispatch swapped. **Install as the robot's `Main.src`.** |
| `CONFIG_ADDITIONS.dat` | 13 SIGNAL declarations for `$config.dat`. **Addresses are placeholders.** |

That is everything. **No `.dat` file is needed for `Main.src`** — the two latched values are
`DECL INT` locals inside the DEF. No station program is modified.

## What changed from the stock template

20 lines, all marked `;===` in the file. The skeleton — `INIT`, `BASISTECH INI`, `CHECK HOME`,
`PTP HOME`, `AUTOEXT INI`, `LOOP`, `SWITCH`, `ENDLOOP` — is untouched.

| Stock | Now |
|---|---|
| `P00 (#EXT_PGNO,#PGNO_GET,DMY[],0)` | `WAIT FOR` a sequence-number change on `Robot_Cmd_Seq` |
| `SWITCH PGNO` | `SWITCH Cmd_Routine` (the latched copy) |
| `CASE 1/2/3` → `EXAMPLE1/2/3` | `CASE 10..90` → the existing station programs |
| `P00 (#EXT_PGNO,#PGNO_ACKN,...)` in each case | gone — the ack is `Robot_Sts_AckSeq` |
| `P00 (#EXT_PGNO,#PGNO_FAULT,...)` | fault code 101 |
| — | status publishing and the held-complete handshake |

`P00 (#INIT_EXT,...)` and `P00 (#CHK_HOME,...)` are **kept**. Ext Auto still starts this program
and still checks home.

## Routine map

| ID | Calls | PLC must set first |
|---:|---|---|
| 10 | `PTP XHOME` inline | — |
| 20 | `Station200_UpStacker()` | `UStoR_ReqToMoveLayer` = FALSE |
| 30 | `Station300_LaserMarker()` | `TTtoR_ReqToPlace` = TRUE |
| 40 | `Station300_LaserMarker()` | `TTtoR_ReqToPickGood` or `...PickBad` = TRUE |
| 50 | `Station400_IMM()` | — |
| 60 | `Station500_SprueCutter()` | — |
| 70 | `Station600_DownStacker()` | — |
| 80 | `Station200_UpStacker()` | `UStoR_ReqToMoveLayer` = TRUE |
| 90 | `Station500_Reject()` | — (`Param1` carries the selector) |

Two stations contain two behaviours each, chosen by a condition bit. Leaving them unmodified means
that bit still chooses, so the PLC sets it before issuing the command. Tray row and column still
arrive in `UStoR_PickRowNumber` / `ColumnNumber` exactly as today.

## Faults

- **100** — station set `RobotCell_Error`
- **101** — unknown routine ID

That is all the detail available without modifying stations. They still reject parts internally and
still report only that one flag.

## Install

1. **`$config.dat` off the controller first.** `XHOME`, `FHOME`, `CHECK_HOME` and every existing
   signal are declared there.
2. Work out the real bit addresses and paste in the SIGNAL block.
3. **Test byte order** — procedure is at the bottom of `CONFIG_ADDITIONS.dat`. A KUKA/Rockwell byte
   swap presents as "the robot ignores my commands", not as a byte swap.
4. Rename the existing `Main.src` / `.dat` to `Main_Legacy.*`, install this as `Main.src`.
   **It needs no `.dat`.**
5. Select `Main` in Ext Auto, as now.

## The alternative, if you want it

This does **not** use `PGNO`, for the same reason your current `Main.src` doesn't: Ext Auto starts
the program and the program loops.

Keeping `PGNO` is the other option and it is arguably better — the request/acknowledge handshake
would be the controller's rather than mine, and `Robot_Cmd_Seq` would disappear entirely. It costs
a `$config.dat` change (point `PGNO_FBIT` at the command word, set `PGNO_TYPE` / `PGNO_LENGTH`) and
a PLC change (drive the PGNO request/ack signals instead of the sequence counter). The robot side
would get *smaller*, not bigger.

Worth deciding once `$config.dat` shows how `PGNO` is currently configured.
