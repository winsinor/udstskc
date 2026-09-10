# Robot setup and first test

Two things go on the controller: a `$config.dat` edit and one `.src` file. No `.dat` accompanies
`Main.src` — the two latched values are locals inside the DEF.

---

## Step 1 — `$config.dat` — DONE, verified

`KRC:\STEU\Mada\$config.dat` has been pulled and checked. Everything `Main.src` needs is already
declared there: `XHOME`, `FHOME`, `PDEFAULT`, `Rjct_1Blnk_2Fin_3Both`, `RobotCell_Error`,
`US_Pick[2,4]`. **`Main.src` will compile.**

## Step 2 — Bit addresses — DONE, verified

The mapping was confirmed against 12 existing signal pairs, in both directions:

```
bit = (PLC byte offset x 8) + 1          base $IN[1] / $OUT[1], no extra offset
```

`UStoR_PickRowNumber` is PLC byte 32 and is declared `$IN[257]`. 32x8+1 = 257. It holds for every
existing pair — inputs at bytes 32/36/40/44/48/52/56 and outputs at 32/36/40/44/48.

Free space in the current config:

| | Free |
|---|---|
| Inputs | `$IN[34]`, `$IN[37..256]`, `$IN[481..1025]` |
| Outputs | `$OUT[59..256]`, `$OUT[417..1024]` |

All 13 addresses in `CONFIG_ADDITIONS.dat` land in that free space. **Zero collisions.** Paste them
as written — no shifting needed.

### The one thing left to check: assembly size

`$config.dat` does not record how big the EtherNet/IP connection is. The highest input in use today
is `$IN[480]` = byte 59, so the connection is **at least 60 bytes**. This block needs it to reach
**byte 92 in both directions**.

Open the `Station100_Robot` module properties in Logix (or the connection in WorkVisual) and confirm
the input and output sizes are 92 bytes or more. If they are short, the robot never sees the command
— no error, no warning, nothing happens. Growing the connection requires a download, so do it before
you plan a test window.

## Step 3 — Add the SIGNAL block

Paste the 13 declarations from `CONFIG_ADDITIONS.dat` into `$config.dat` **exactly as written** —
they are verified against the live config. Put them with the other `SIGNAL` declarations. Reboot the
controller so the config takes.

## Step 4 — Test byte order BEFORE anything else

Do not skip this. KUKA fills a signal group LSB-first; Rockwell lays a DINT out little-endian in the
assembly. They usually agree. When they do not, it presents as *"the robot ignores my commands"*,
not as a byte swap, and you will lose an afternoon.

No robot program needs to be running. From the PLC, write `Robot_Cmd_Param1` and read the value on
the pendant under **Display > Variable > Single**:

| Write | Expect | Catches |
|---:|---:|---|
| 1 | 1 | basic mapping |
| 256 | 256 | **byte swap** |
| 65536 | 65536 | word swap |
| 16777216 | 16777216 | full reversal |

If 256 comes back as 1, or 16777216 comes back as 256, the bytes are reversed. Fix it by flipping
the group order in the SIGNAL declarations — every one of the thirteen — before going further.

## Step 5 — Install the program

1. Rename the existing `Main.src` and `Main.dat` to `Main_Legacy.src` / `.dat`. **Keep them.**
2. Copy this `Main.src` into `KRC:\R1\Program`.
3. It needs **no** `.dat`.
4. Open it on the pendant and confirm it compiles clean. Unresolved names here mean a `$config.dat`
   global is missing — most likely `XHOME`, `FHOME` or one of the new signals.

## Step 6 — First test: does it answer at all

**No motion. Robot in T1, drives off is fine.** You are testing the handshake, not the robot.

1. Select `Main` and start it. It should run to the `WAIT FOR` and sit there.
2. On the pendant watch `Robot_Sts_AckSeq` — it should have adopted whatever `Robot_Cmd_Seq` is.
3. From the PLC, set `HMI_Mode_Select` = 1 for manual mode.
4. Put **99** — deliberately invalid — in `Man_RoutineID`. Pulse `Man_Fire`.

Expect:

| Watch | Should show |
|---|---|
| `Robot_Sts_AckSeq` | matches `Robot_Cmd_Seq` within a scan |
| `Robot_Sts_RoutineID` | 99 |
| `Robot_Sts_FaultCode` | **101** — unknown routine ID |
| `Robot_Sts_State` | **3**, and it stays there |

5. Pulse `Man_Ack`. `Robot_Cmd_RoutineID` goes to 0, and the robot returns to state 0.

**That is the whole protocol proven with the robot standing still.** Latch, acknowledge, dispatch,
fault, hold, consume, idle. If this works, everything after it is just motion.

If `Robot_Sts_AckSeq` never matches, go back to step 4 — it is byte order.

## Step 7 — First motion

Robot in **T1**, reduced override, hand on the enabling switch, and be ready on the E-stop.

Command **10**. The robot should PTP to `XHOME` and report state 2. Acknowledge, and it returns to 0.

That is the first real motion under PLC command. Everything past this point is proving one station
at a time.

## Step 8 — Then, one station at a time

In this order. For each, set the condition bits the station expects **first**, then command it:

| Order | ID | Set first |
|---:|---:|---|
| 1 | 20 PickUpstacker | `UStoR_ReqToMoveLayer` = FALSE, row/column in `UStoR_PickRowNumber` / `ColumnNumber` |
| 2 | 30 PlaceTurntable | `TTtoR_ReqToPlace` = TRUE |
| 3 | 40 PickTurntable | `TTtoR_ReqToPickGood` or `...PickBad` = TRUE |
| 4 | 70 DropChute | — |
| 5 | 60 SprueCut | — |
| 6 | 80 LayerShift | `UStoR_ReqToMoveLayer` = TRUE |
| 7 | 90 Reject | `Man_Param1` = 1, 2 or 3 |
| 8 | 50 IMMExchange | — |

**IMM last.** Most interlocked, and the only one that can damage a mould.

---

## What to expect when something goes wrong

| Symptom | Meaning |
|---|---|
| `Robot_Sts_AckSeq` never matches | Byte order, or the robot program is not running |
| PLC fault **9001** | Robot never acknowledged — same causes |
| PLC fault **9002** | Robot accepted but never finished. Raise `Seq_RunTimer` or the station is stuck. |
| Robot fault **101** | Unknown routine ID — the PLC sent something outside 10..90 |
| Robot fault **100** | The station set `RobotCell_Error`. Look at the station, not at this program. |
| Robot sits at state 2 forever | The PLC is not consuming. It must write `Robot_Cmd_RoutineID` = 0. |

That last one is by design, not a bug. There is no timeout on the hold: if the PLC never consumes,
the robot should be obviously stuck rather than quietly going idle and accepting new work.
