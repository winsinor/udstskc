# PLC-as-Master Rework — Design Decisions and Interface Spec

Target: the ControlLogix PLC becomes the point of control. It commands the KUKA robot to run
named routines and reads back a held status saying what the robot is doing and when it finished.

Status: **design agreed, not yet implemented.** Cell is in commissioning, not running production.

---

## 1. Decisions on record

These were settled deliberately. Anything built should conform to them, and any change to them
should be recorded here rather than discovered in the code later.

| Area | Decision |
|---|---|
| Control authority | PLC is master. Robot executes commanded routines and reports; it makes no scheduling decisions. |
| Command style | Routine-ID command word + held status word. Clean break from the condition-bit polling design. |
| Command granularity | One command per station job (9 routines, §3). PLC auto-sequencer chains them. |
| Concurrency | Overlap permitted where safe — stations may act while the robot is elsewhere, gated by zone interlocks. |
| Optix PC | **HMI only.** Displays status, takes operator input, writes no command tags. |
| Safety | **Hardwired relays only** (CRM / CRM_S / CRM_P). The standard PLC never makes a safety decision. All interlocks described here are functional, not safety-rated. |
| Inspection | **No vision.** Part-present sensors PE202 / PE203 at turntable station 2 are the only good/bad criterion. IV3 and Cognex gating is removed. |
| Finished parts | **Chute always.** `DStoR_DropInShoot` path is the production path. |
| Downstacker | Empty-tray stacking only — it receives spent trays from the layer-shift move. Tray pick/place grid logic is removed. |
| Parts per cycle | **2-up.** Cup A and cup B each carry one blank; two blanks per turntable nest, two inserts per shot, two finished parts per unload. |
| Fault policy | Faults assumed rare. Framework must exist: retry N times, then reject. Vacuum/grip verification is the canonical case. |
| Fault pose | On fault the robot **retreats to XHOME and holds**, then reports `Faulted` + fault code. |
| Reject drawer | Stays manual (`Station500_DrawerMove` is not being implemented). On full: alarm and stop **at cycle end**. |
| Part tracking | PLC owns it. Sequence numbers assigned by the PLC; full genealogy per part. |
| Stacker positions | PLC owns row/column/layer selection, sourced from `UpAxis_NextValidPos`. |
| Definition of done | Each of the 9 routines commandable individually from the PLC and reporting correctly, plus a rough auto-sequence framework that chains them. |

### Purpose of the machine

This is a **demo cell for an open house, 4–8 weeks out**. A visitor types a name at a kiosk, the
laser engraves it on a blank, the blank is insert-moulded, and the visitor picks their part out of
the chute by reading their own name off it. That reframes several priorities: the cell must look
alive, recover without help, and never hand someone the wrong part.

| Area | Decision |
|---|---|
| Laser marking | Company logo by default; a queued name engraved on request. |
| Name transport | Free text over EtherNet/IP to the MDX2. **Nothing in the PLC does this today** — zero STRING tags, zero MSG instructions. New construction. |
| String length | 20 characters. |
| Kiosk | An Optix screen that *submits* into a PLC-owned name queue. It never commands the cell. |
| Kiosk input guard | Character restrictions only (letters, digits, spaces, length clamp). |
| Queue control | Operator can cancel or edit a pending entry. |
| Part matching | The name is on the part — no tickets, no sorted bin, no post-delivery lookup. |
| 2-up naming | Two text fields per laser fire; a field with no queued name takes the logo. |
| Scrap of a named part | Name is pushed back to the **head** of the queue and re-run automatically. |
| Mark visibility | Readable on the finished moulded part. |
| Modes | Auto, Manual (single routine), Dry cycle, Purge. |
| Dry cycle | Operator selects per run whether the IMM leg is included. |
| Startup | Operator presses home, then start. Nothing moves unasked. |
| Tray density | Two blanks per tray position, one per cup. 8 positions × 11 layers = 176 blanks per stack. |
| Layer count | **11 layers.** See the bounds bug in §2. |
| Tray reload | Expected mid-event. New trays assumed full; the partly-used tray keeps its own map. Sensor counts trays, operator confirms; **sensor is authoritative**, mismatch warns. |
| Tray memory | Follows the tray, and tracks current position. **Expand the existing `UpAxis_Memory` logic — do not rewrite it.** |
| Downstacker | Simple empty-tray counter plus full detection. No position map. |
| Entry to load | Request-to-enter button → full stop, robot home, everything holds, then unlock. |
| Empty trays | Unloaded during the event, same entry request. |
| Position source | **Robot taught points win.** PLC sends the tray index; robot uses `US_Pick[row,col]`. The PLC's x/y/r `TrayPositions` path is not the source of truth. |
| Part memory | See [`PART_MEMORY.md`](PART_MEMORY.md). Adopt the `Part_Data` shape, retire `Data_Item`; locations hold a sequence number only; pair record with per-part sub-records. |

### Out of scope for this push

- Reject drawer indexing (`Station500_DrawerMove` stays empty; drawer is emptied by hand).
- Vision commissioning (IV3 / Cognex).
- Safety program work — there is no safety PLC.
- Cycle-time optimisation beyond enabling overlap structurally.

---

## 2. Blocking unknowns

Nothing in §4 onward is safe to build until these are closed. They are tasks 0.1–0.5 in `TODO.md`.

1. **`$config.dat` is not in the repo.** It is where every KRL global is declared and bound to an
   I/O address. Without it we cannot add signals or verify a single existing mapping.
2. **Free space in the `Station100_Robot` I/O assemblies is unverified.** §4 assumes bytes 64–91
   are available in both directions. If they are not, the layout changes.
3. **Nothing in the exported PLC code writes the stacker tags** — `UStoR_PickRowNumber`,
   `UStoR_PickColumnNumber`, `UStoR_PickSeqNumber`, `UStoR_ReqToPick`, `UStoR_ReqToMoveLayer`,
   `DStoR_PickRowNumber`, `DStoR_PickColumnNumber`, `DStoR_OpenLocation`. Almost certainly Optix
   writes them directly. Confirm from the Optix tag list before removing anything.
4. **Physical I/O inventory.** Confirm which of IV3, Cognex IS3800, PE202, PE203, PE307, PRX315
   are actually installed and wired, versus present in the I/O tree only.
5. **EuroMap 67 connection state.** Confirm the molder is physically connected and the EM67 / EM78
   signals in `Routine040700_OutputActions` are live.
6. **Can the MDX2 accept free text over EtherNet/IP?** The current connection carries discrete bits
   only — ready, busy, error, trigger, reset, and two bits that look like program select. Sending a
   string needs a larger assembly and the marker's command protocol. **Get the manual and prove one
   string end to end before any of the naming work is built on the assumption.** This is the single
   biggest schedule risk to the open house.
7. **The new tray-count sensor** is not specified yet — part number, mounting, and whether it counts
   trays or measures stack height. The replenishment logic can't be finished without it.
8. **Processor memory headroom.** `Part_Log[500]` at ~64 bytes is ~32 KB, which is modest, but the
   controller type isn't in these exports. Confirm before sizing anything larger.

### The layer-bounds bug

`UpAxis_Memory` is `SINT[12]` (valid indices 0–11), `UpAxis_Positions` is `DINT[14]`, rung 7 limits
requests to 1–13, rung 8 increments while `CurrentLayer < 13`, and rung 9 clamps at ≥11. Indexing
`UpAxis_Memory[UpAxis_CurrentLayer]` at layer 12 or 13 is **out of range and will major-fault the
processor.** The agreed answer is 11 layers: rung 9 is right, rungs 7 and 8 are wrong. Derive all
four from one constant.

---

## 3. Routine ID map

One command per station job. The robot owns all motion inside a routine; the PLC decides which
routine runs and when.

| ID | Routine | What the robot does | Preconditions the PLC must satisfy |
|---:|---|---|---|
| 0 | *(none)* | Idle. No command pending. | — |
| 10 | `Home` | Move to `XHOME`, clear tool state, restore IMM enables. | None. Always accepted. |
| 20 | `PickUpstacker` | Pick 2 blanks from tray cell (Row, Col), verify both cups. | Stacker at layer, cell valid and occupied, tool blank side empty. |
| 30 | `PlaceTurntable` | Place 2 blanks into nest at turntable station 1. | Nest empty, turntable stopped and in position. |
| 40 | `PickTurntable` | Pick 2 marked blanks from nest at station 1. | Nest holds a marked pair, turntable stopped. |
| 50 | `IMMExchange` | Enter mold, unload shot, load marked blanks, exit. | `IMMtoR_OpEnable`, mold open, tool blank side loaded. |
| 60 | `SprueCut` | Two cut pulses, release finished-side gripper. | Tool finished side loaded. |
| 70 | `DropChute` | Release finished parts down the chute. | Tool finished side loaded, chute clear. |
| 80 | `LayerShift` | Slide spent tray from upstacker to downstacker. | Both stackers stopped, tool empty. |
| 90 | `Reject` | Dump the tool halves selected by `Param1` into the drawer. | Drawer in position and not full. |

`Param1` on routine 90 keeps the existing encoding: `1` = blank side, `2` = finished side,
`3` = both.

---

## 4. Interface control document

### 4.1 Word layout

Existing words stay where they are. The new command/status block starts at byte 64. Each entry is
one DINT, copied with `COP(..., 4)` exactly as the existing words are.

**PLC → Robot — `Station100_Robot:O.Data[]`**

| Bytes | Tag | Meaning |
|---|---|---|
| 32–35 | `UStoR_PickRowNumber` | *(legacy — retained during migration)* |
| 36–39 | `UStoR_PickColumnNumber` | *(legacy)* |
| 40–43 | `UStoR_PickSeqNumber` | *(legacy)* |
| 44–47 | `TTtoR_PickSeqNumber` | *(legacy)* |
| 48–51 | `DStoR_PickRowNumber` | *(legacy — removed with downstacker grid)* |
| 52–55 | `DStoR_PickColumnNumber` | *(legacy — removed)* |
| 56–59 | `PLCtoR_MoveAccel` | Move accel scalar, clamped 10–100. |
| 64–67 | `Robot_Cmd_RoutineID` | Routine to run. See §3. |
| 68–71 | `Robot_Cmd_Seq` | Increments on every new command. Distinguishes a repeat of the same ID. |
| 72–75 | `Robot_Cmd_Param1` | Tray row / reject selector, per routine. |
| 76–79 | `Robot_Cmd_Param2` | Tray column. |
| 80–83 | `Robot_Cmd_Param3` | Part A sequence number. |
| 84–87 | `Robot_Cmd_Param4` | Part B sequence number. |
| 88–91 | `Robot_Cmd_RetryLimit` | Retries before the routine reports faulted. `0` = fail on first error. |

**Robot → PLC — `Station100_Robot:I.Data[]`**

| Bytes | Tag | Meaning |
|---|---|---|
| 32–35 | `RtoTT_PlaceSeqNumber` | *(legacy)* |
| 36–39 | `RtoDS_PlaceSeqNumber` | *(legacy)* |
| 40–43 | `RtoIMM_SeqNumber` | *(legacy)* |
| 44–47 | `RtoPLC_ToolBlnkSeqNumber` | *(legacy)* |
| 48–51 | `RtoPLC_ToolFinSeqNumber` | *(legacy)* |
| 64–67 | `Robot_Sts_State` | `0` Idle, `1` Running, `2` Complete, `3` Faulted, `4` Held. **Held, not pulsed.** |
| 68–71 | `Robot_Sts_RoutineID` | Routine currently running, or the one just completed/faulted. |
| 72–75 | `Robot_Sts_AckSeq` | Echo of `Robot_Cmd_Seq`. The command is latched when this matches. |
| 76–79 | `Robot_Sts_FaultCode` | `0` when not faulted. See §4.3. |
| 80–83 | `Robot_Sts_RetryCount` | Retries consumed on the current routine. |

### 4.2 Handshake

The whole point is that completion is a **held state**, not the 150–250 ms pulse the current code
uses. A held state survives a slow scan, a PLC fault, and an operator walking away.

```
PLC                                       Robot
 |  State == 0 (Idle)                        |
 |  write RoutineID, Params                  |
 |  Cmd_Seq := Cmd_Seq + 1  ----------------->|  sees Cmd_Seq != Sts_AckSeq
 |                                            |  latch params
 |                          <-----------------|  Sts_AckSeq := Cmd_Seq
 |                                            |  Sts_RoutineID := RoutineID
 |                                            |  Sts_State := 1 (Running)
 |  sees Running + AckSeq match               |
 |  (command accepted)                        |  ... executes ...
 |                          <-----------------|  Sts_State := 2 (Complete)
 |  consume completion                        |  (holds here)
 |  RoutineID := 0          ----------------->|  sees RoutineID == 0
 |                          <-----------------|  Sts_State := 0 (Idle)
```

Rules:

- The robot only latches a command when `Sts_State == 0` **and** `Cmd_Seq != Sts_AckSeq`.
  A command written while the robot is busy is ignored, not queued.
- The robot holds `Complete` or `Faulted` until the PLC writes `RoutineID = 0`. This is what makes
  the handshake idempotent and recovery possible.
- On fault: robot retreats to `XHOME`, sets `Sts_FaultCode`, sets `Sts_State = 3`, and holds.
  The PLC clears it by writing `RoutineID = 0` after acknowledging the alarm.
- `PLCtoR_Stop` still forces `Held` at the next safe point. `Sts_State = 4` replaces
  `RtoPLC_RobotReachedStop`, which is retained during migration.
- PLC-side timeout on `Running` is mandatory — a robot that stops scanning must not read as busy
  forever.

### 4.3 Fault codes

Grouped by station so the alarm text can be derived from the range.

| Code | Meaning |
|---:|---|
| 101 | Unknown or unsupported routine ID |
| 102 | Command received while not idle |
| 103 | Stop asserted mid-routine |
| 104 | Drives not enabled / move not permitted |
| 201 | Blank cup A no vacuum on upstacker pick |
| 202 | Blank cup B no vacuum on upstacker pick |
| 203 | Blank vacuum lost after lift |
| 204 | Tray row/column parameter out of range |
| 211 | Layer shift not confirmed |
| 301 | Blank not seated in nest (PE202 / PE203) |
| 302 | Turntable did not index |
| 303 | Blank cup A no vacuum on turntable pick |
| 304 | Blank cup B no vacuum on turntable pick |
| 401 | IMM operation enable timeout |
| 402 | Ejector-back timeout on entry |
| 403 | Mold open timeout |
| 404 | Finish cup A no vacuum |
| 405 | Finish cup B no vacuum |
| 406 | Ejector-forward timeout |
| 407 | Ejector-back timeout on exit |
| 408 | Blank not released into cavity |
| 501 | Sprue cut not confirmed |
| 502 | Reject drawer full |
| 503 | Reject drawer not in position |
| 601 | Part not released at chute |

Codes are reserved in blocks; add within a block rather than renumbering.

---

## 5. Zone interlocks for overlap

Overlap is permitted, so the PLC must own a zone occupancy model. The robot publishes which zone
it is in; no station may act in a zone the robot occupies.

| Zone | Contains | Blocks |
|---|---|---|
| Z1 Stackers | Upstacker, downstacker, tray slide | Stacker axis moves while robot is in Z1 |
| Z2 Turntable | Weiss nest at station 1 | Turntable index while robot is in Z2 |
| Z3 IMM | Mold area | Mold close — enforced today by `RtoIMM_MoldAreaFree` |
| Z4 Sprue/Reject | Cutter, reject drawer | Cutter actuation while robot is not present |
| Z5 Chute | Drop chute | — |

`RtoIMM_MoldAreaFree` is the single most dangerous bit in the codebase — it is the robot's promise
that the mold area is clear, and it is currently written unconditionally on every stop and every
startup. Zone Z3 must be derived from it, not alongside it.

---

## 6. Migration approach

Legacy condition bits (`UStoR_ReqToPick`, `TTtoR_ReqToPlace`, etc.) stay live and mapped
throughout. They are removed only after the command/status path is proven for that station. This
means at every point there is a working machine, and a bad day ends in reverting one station
rather than the whole cell.

Order of proving: **20 PickUpstacker → 30 PlaceTurntable → 40 PickTurntable → 70 DropChute →
60 SprueCut → 80 LayerShift → 90 Reject → 50 IMMExchange.** The IMM is last because it is the
most interlocked and the only one that can damage a mold.
