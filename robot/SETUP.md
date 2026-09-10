# Robot setup and first test

Two things go on the controller: a `$config.dat` edit and one `.src` file. No `.dat` accompanies
`Main.src` — the two latched values are locals inside the DEF.

---

## Step 1 — Get `$config.dat` and see what you have

`KRC:\STEU\Mada\$config.dat`. Pull it off, commit it, and find these:

| Look for | Why |
|---|---|
| `XHOME`, `FHOME` | The home position and its frame. `Main.src` moves there and will not compile without them. |
| `PDEFAULT` | Motion parameters for that move. |
| Existing `SIGNAL` declarations | Tells you which `$IN` / `$OUT` numbers are already taken. |
| The highest `$IN[n]` / `$OUT[n]` in use | Where your free space starts. |
| `RobotCell_Error`, `Rjct_1Blnk_2Fin_3Both` | Confirm they are declared here as expected. |

**Do not add anything yet.** Read first.

## Step 2 — Work out the bit addresses

The PLC block sits at **byte 64** of each assembly. Convert:

```
bit number = (byte offset x 8) + 1 + (whatever the assembly's base offset is)
```

If the EtherNet/IP connection maps to `$IN[1]`, byte 64 is `$IN[513]`. It probably does not — the
existing signals already occupy space — so shift every number in `CONFIG_ADDITIONS.dat` by the same
amount and keep them contiguous.

Direction, because it is the easy mistake:

```
PLC output  ->  robot $IN      Robot_Cmd_*
robot $OUT  ->  PLC input      Robot_Sts_*
```

## Step 3 — Add the SIGNAL block

Paste the 13 declarations from `CONFIG_ADDITIONS.dat` into `$config.dat` with your corrected
addresses. Reboot the controller so the config takes.

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
