# Robot side — two files

| File | What |
|---|---|
| `Main.src` | The stock KUKA CELL template with the dispatch swapped. **Install as the robot's `Main.src`.** |
| `CONFIG_ADDITIONS.dat` | 13 SIGNAL declarations for `$config.dat`. **Addresses verified against the live config — no collisions.** |

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

## Install and test

Step by step in **[`SETUP.md`](SETUP.md)**, including the byte-order test and a first test that
proves the whole protocol with the robot standing still.

## Why not PGNO

KUKA's program-number mechanism does the selection half of this natively, and the stock template
uses it. It is **not** used here, deliberately:

- Your existing `Main.src` calls no `P00` and no `PGNO`.
- There is no PGNO tag anywhere in the PLC project. `Routine040600_Robot_Startup` drives only the
  *start* half of Ext Auto — DrivesOn, ConfMess, ExtStart.
- PGNO answers "which program" and "did you hear me". It does not carry parameters, a fault code,
  or a held result. The status half would have to be hand-rolled alongside it anyway.

So the stock template's `P00 (#CHK_HOME,...)` and `P00 (#INIT_EXT,...)` calls are **removed** —
`#INIT_EXT` validates the extern-mode PGNO configuration and would fault on startup on a cell where
PGNO is not set up. Ext Auto still starts this program exactly as it starts the current one.

### The live config makes this worse than "unused"

The real `$config.dat` carries a leftover Ext-Auto block whose addresses sit **on top of live
signals**:

| Ext Auto setting | Lands on | Which is |
|---|---|---|
| `PGNO_FBIT = 33` (`$IN[33..40]`) | `TTtoR_TurnTableCycle` `$IN[33]` | a live turntable input |
| `PGNO_REQ = 33` | `RtoIMM_PickErrorVG530` `$OUT[33]` | a live error output |
| `APPL_RUN = 34` | `RtoTT_PickErrorVG524` `$OUT[34]` | a live error output |
| `ERR_TO_PLC = 35` | `RtoTT_PickErrorVG526` `$OUT[35]` | a live error output |

Calling `P00 (#INIT_EXT,...)` would have started driving three real error outputs as Ext-Auto
handshake bits. Removing it was not just tidying.
