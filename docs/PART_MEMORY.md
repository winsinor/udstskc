# Part Memory — Design Spec

How the PLC knows what part is where, at every moment, everywhere in the cell.

Companion to [`PLC_MASTER_PLAN.md`](PLC_MASTER_PLAN.md). Status: **design agreed, not implemented.**

---

## 1. Why this exists

The cell is a demo machine for an open house. A visitor types a name at a kiosk, the laser engraves
it on a blank, the blank is insert-moulded, and the visitor picks their part out of the chute —
identified by reading their own name off it.

That only works if the PLC knows, without ambiguity, which physical part carries which name and
where that part currently is. Today it does not: part state lives partly in KRL globals on the
robot, partly in a turntable shift register, and the one model with the right shape is inert.

## 2. What exists today

| Model | Where | State |
|---|---|---|
| `Data_Item` / `TurnTable[5]` | Communication + LaserMarker programs | **Working.** 27 writes across three routines. `Data_Item[500]` master array indexed by sequence number; `TurnTable[5]` is a shift register of whole-record copies. Pair-shaped: `TurnTable_1_Pres`/`_2_Pres`, `Inspect_1`/`_2`, `Orig_X/Y/Angle_1`/`_2`. |
| `Part_Data` | System program | **Inert.** Zero writes anywhere. `Index_Table_Part_Data[5]`, `Robot_Blank_Side_Part_Data`, `Robot_Finished_Side_Part_Data`, read only by the inert sequencer. Single-part shaped, and carries `Human_Readable`, `QR_Data`, `Operator_Name`, `Shift`, `Time_Of_Day`, `Part_Number` as STRINGs. |
| KRL globals | Robot | `RtoPLC_ToolBlnkHasParts`, `ToolBlnkMrked`, `ToolFinHasParts`, `RtoPLC_ToolBlnkSeqNumber`, `RtoPLC_ToolFinSeqNumber`, `RtoIMM_SeqNumber`. Survive a robot power cycle only by accident, invisible to PLC part tracking. |

Someone had already sketched gripper records and a human-readable string field — exactly what this
spec needs — and never wired it up.

**Decision: adopt the `Part_Data` shape, retire `Data_Item`.** `Part_Data`'s six STRINGs are
inherited from another project and cost ~540 bytes per record (a Logix `STRING` is 88 bytes); only
the engraved name is wanted here, on a 20-character type.

## 3. Data model

### 3.1 Types

```
STRING_20                       -- 24 bytes, vs 88 for a stock STRING
   LEN      DINT
   DATA     SINT[20]

Part_Record                     -- one physical blank / moulded part
   Present  BIT
   Good     BIT
   Bad      BIT
   Name     STRING_20           -- engraved text; LEN = 0 means the default logo

Part_Pair                       -- the unit that travels the cell (~64 bytes)
   Seq_Num  DINT                -- identity, 1..500; also the Part_Log index
   State    DINT                -- lifecycle, §3.3
   A        Part_Record         -- cup A side  (VG524 / blank, VG528 / finished)
   B        Part_Record         -- cup B side  (VG526 / blank, VG530 / finished)
```

`A` / `B` rather than an array member: the whole cell is already named this way
(`BlankCupAVac`, `FinishCupBBlow`, `PickErrorVG524`), and ladder reads better without index maths.

The pair is the unit that moves — picked together, marked in one laser fire, moulded in one shot,
dropped together. The per-part sub-records exist because the two halves genuinely diverge: one may
carry a queued name while the other takes the logo, and a single cup can fail on its own.

### 3.2 Storage and locations

```
Part_Log         Part_Pair[500]   -- master record, indexed by Seq_Num
Part_Seq_Next    DINT             -- next sequence to allocate; wraps 1..500

Loc_RobotBlank   DINT             -- pair on the vacuum-cup half   (0 = empty)
Loc_RobotFinish  DINT             -- pair on the gripper half
Loc_Nest         DINT[5]          -- turntable stations 1..4; index 0 unused
Loc_Mold         DINT             -- pair in the cavities
Loc_Delivered    DINT             -- last pair confirmed out the chute
```

**Locations hold a sequence number and nothing else.** `Part_Log[seq]` is the single copy of the
truth, so no two places can disagree about a part. A location holding `0` is empty.

This replaces the current turntable shift, which COPs whole records between slots. The rotation
becomes four DINT moves instead of five 540-byte record copies:

```
temp := Loc_Nest[4]
Loc_Nest[4] := Loc_Nest[3]
Loc_Nest[3] := Loc_Nest[2]
Loc_Nest[2] := Loc_Nest[1]
Loc_Nest[1] := temp
```

`Loc_Nest` is dimensioned `[5]` with index 0 unused so the subscript matches the physical station
number. The existing code's `TurnTable[0]` is a scratch buffer, not a fifth station — rung 7 of
`Routine060500_Operation` reads `[4]→[0], [3]→[4], [2]→[3], [1]→[2], [0]→[1]`, a four-position
rotation through a temp slot. **There are four turntable stations.**

`Part_Log` is **not retentive**. It is cleared on first scan and `Part_Seq_Next` reset to 1;
sequence numbers wrap at 500 and reuse slots freely, because nothing is ever looked up after
delivery — matching is by reading the name off the part.

### 3.3 Lifecycle

Spaced in tens so states can be inserted without renumbering.

| State | Meaning | Set when |
|---:|---|---|
| 0 | Empty | Slot unused, or pair retired |
| 10 | Allocated | PLC commands `20 PickUpstacker` and allocates the sequence |
| 20 | On gripper, unmarked | Robot reports the pick complete, both cups verified |
| 30 | In nest | Robot reports `30 PlaceTurntable` complete |
| 40 | Marked | Laser reports the fire complete |
| 50 | On gripper, marked | Robot reports `40 PickTurntable` complete |
| 60 | In mould | Robot reports the blanks released into the cavities |
| 70 | On gripper, moulded | Robot reports the shot picked and the gripper closed |
| 80 | Sprue cut | Robot reports `60 SprueCut` complete |
| 90 | Delivered | Both finished-side cups confirmed released at the chute |
| 900 | Rejected | Any fault path that dumps the pair to the drawer |

### 3.4 Name queue

```
Name_Queue    STRING_20[20]   -- ring buffer, written by the Optix kiosk
Name_Q_Head   DINT
Name_Q_Tail   DINT
Name_Q_Count  DINT
```

The kiosk **submits** into this queue and does nothing else. It never commands the cell.

**The name attaches at the laser, not at the pick.** A pair is born anonymous at the upstacker.
When its nest arrives at the laser station and is about to fire, the PLC pulls up to two names off
the queue and writes them into `Part_Log[seq].A.Name` and `.B.Name`. Whichever half gets no name
takes the default logo.

This is deliberate: a pair scrapped anywhere between the tray and the laser costs nothing, and no
visitor's name is ever consumed without being engraved. The only window where a name can be lost is
between the laser and the chute — and that window is covered by re-queue on scrap.

**On scrap of a named pair** (state 900): any `Name` with `LEN > 0` is pushed back to the *head* of
the queue, so that visitor is served by the next available blank rather than going to the back of
the line.

### 3.5 Field ownership

Every field has exactly one writer. Nothing is written from two places.

| Field | Written by |
|---|---|
| `Seq_Num`, `State` | The auto-sequencer, on each robot routine completion |
| `A.Present` / `B.Present` | Sequencer, from robot completion plus the relevant vacuum switch |
| `A.Name` / `B.Name` | The laser station, at name attach |
| `A.Good` / `B.Good` | The laser station (mark confirmed) and the mould exchange |
| `A.Bad` / `B.Bad` | Any fault path, at the point of rejection |
| `Loc_*` | The auto-sequencer only |
| `Name_Queue` | Optix kiosk (submit) and the sequencer (consume, re-queue) |

## 4. Robustness

### 4.1 Startup — auto-purge

`Part_Log` clears on power up, but the cell may physically still hold parts. Before a cycle start is
accepted, the cell runs a purge routine: reject anything on either gripper half, index the turntable
until all four nests read empty on PE202 / PE203, and confirm the mould is clear. Only then is the
memory known to match reality.

This costs a few blanks and about a minute every morning, and it needs no human judgement — which
is the right trade for a machine being opened up by whoever gets there first on the day.

### 4.2 Memory versus sensors — hold and alarm

At every point where a sensor can corroborate the memory, it is checked:

| Location | Corroborating sensor |
|---|---|
| Turntable nests 1–4 | PE202 / PE203 part-present |
| Robot blank side | VG524 / VG526 vacuum switches |
| Robot finished side | VG528 / VG530 vacuum switches |
| Mould cavities | *none* — memory only |

**On disagreement the cycle holds and raises an alarm naming the location and the direction of the
error** — "nest 3 expects a part, PE202 reads empty" — rather than self-correcting. Nothing moves on
data known to be wrong, and the cause gets found instead of papered over.

The mould has no sensor, which is why §4.1 purge exists and why the mould is the one location the
operator must vouch for.

### 4.3 Delivery confirmation

There is no chute sensor. A pair reaches state 90 only when **both finished-side vacuum switches
confirm release** after the blow-off. That is free — the sensors already exist — and it catches the
failure that actually matters here: a part still stuck to the tooling while the visitor stands at
the chute waiting.

It does not catch a part that jams inside the chute after release. If that turns out to happen, a
through-beam at the chute exit is the fix, and the state machine already has the right place to put
it.

## 5. What this replaces

| Removed | Replaced by |
|---|---|
| `Data_Item[500]`, `Data_Item_Initialize` | `Part_Log[500]` |
| `TurnTable[5]` record shift register | `Loc_Nest[5]` sequence numbers |
| `Part_Data` six-STRING record | `Part_Pair` with one `STRING_20` per part |
| `Index_Table_Part_Data[5]` | `Loc_Nest[]` |
| `Robot_Blank_Side_Part_Data` | `Loc_RobotBlank` |
| `Robot_Finished_Side_Part_Data` | `Loc_RobotFinish` |
| `RtoPLC_ToolBlnkHasParts` / `ToolBlnkMrked` / `ToolFinHasParts` (KRL) | `Part_Log[Loc_RobotBlank].State` etc. Robot reports, PLC decides. |
| `RtoIMM_SeqNumber` — one number for a 2-up shot | `Loc_Mold` |

`UpAxis_Memory[]` in the upstacker is **not** replaced. It tracks tray occupancy, not part identity,
and it already works. Per the standing instruction on that program: expand it, do not rewrite it.
