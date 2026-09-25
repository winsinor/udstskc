# Open House Robot Cell — Session Handoff

**Written:** 2026-09-25, end of a long working session
**Repo:** `winsinor/udstskc`, branch `Friday-From-Home`, last commit `b25b447`

---

## READ THIS FIRST

**The files in this repo do NOT match what is running on the hardware.** They have
diverged in *both* directions — some repo files are behind the controller, at least
one is ahead of it. Do not reason about cell behaviour from these files until fresh
exports replace them.

Anything below marked **UNVERIFIED** is an assumption, not a fact.

---

## 1. Exports needed before doing anything else

### From the KUKA controller (USB)

| File | Why |
|---|---|
| `KRC:\R1\System\$config.dat` | Repo copy has the OLD output addresses. See §3. |
| `KRC:\R1\Program\Main.src` | Typed in by hand on the pendant; repo copy is a reconstruction. |
| `KRC:\R1\Program\Main.dat` | Never exported this session. |
| `KRC:\R1\Program\Station400_IMM.src` | Edited on the pendant; repo copy is pre-edit. |
| `KRC:\R1\Program\Station500_Reject.src` | **Repo is AHEAD** — a change was committed but never transferred. |
| `KRC:\R1\System\sps.sub` | Repo copy is from an earlier export; confirm it is current. |
| `KRC:\R1\System\cell.src` | **Never seen.** Load-bearing for EXT mode. |

### From Logix Designer

Export the whole `Program040000_Station100_Robot` program, not individual routines.
The repo copy is a 2026-09-04 export and is missing four routines that now exist:

- `_01_Robot_Comms`
- `_02_Robot_Faults`
- `_03_RobotSequencer`
- `_08_HMI_Animations`

Also export controller tags, `Program050000_Station200_UpDownStackers`, and
`Program010000_Communication`.

---

## 2. Architecture as it stands

The PLC commands the robot to run whole routines. The robot runs one routine at a
time and reports back. Three tags carry it:

| Tag | Direction | Meaning |
|---|---|---|
| `Robot_Cmd_RoutineID` | PLC → Robot | non-zero = run that routine; 0 = idle |
| `Robot_Sts_State` | Robot → PLC | 0 idle, 1 running, 2 complete, 3 faulted |
| `Robot_Sts_RoutineID` | Robot → PLC | echo of the routine being run |

States 2 and 3 are **held** by the robot until the PLC writes the command back to 0.

### Routine IDs

| ID | Robot routine |
|---:|---|
| 10 | Home |
| 20 | `Station200_UpStacker` |
| 30 | `Station300_LaserMarker` |
| 40 | `Station400_IMM` |
| 50 | `Station500_SprueCutter` |
| 60 | `Station600_DownStacker` |
| 71 / 72 / 73 | `Station500_Reject` — blank / finished / both |

`Station500_DrawerMove` is an **empty stub** (DEF / INI / END, no motion). It had a
routine ID at one point; that was removed.

Each station program decides internally what to do based on request bits the PLC
already drives (`UStoR_ReqToMoveLayer`, `TTtoR_ReqToPlace`, `IMMtoR_PartInjected`,
etc.). The routine ID says *which station*, the request bits say *what to do there*.

---

## 3. I/O mapping — VERIFIED ON HARDWARE

EtherNet/IP, `Station100_Robot`, `AB:ETHERNET_MODULE_SINT_256Bytes`, 256 bytes each way.

**Bit ↔ byte:** `bit = (byte × 8) + 1`. Little-endian both directions.

### Outputs above 512 are NOT MAPPED

This was the hard-won finding of the session. `$OUT[513]` and above report
`variable write-protected` and cannot be written from KRL or the pendant. Inputs
above 512 **are** mapped and work fine (proven: `$IN[577]` / `O.Data[72]`).

Current working assignments after the fix:

```
SIGNAL Robot_Cmd_RoutineID   $IN[513]  TO $IN[544]     ; O.Data[64]   (works)
SIGNAL Robot_Sts_State       $OUT[417] TO $OUT[448]    ; I.Data[52]
SIGNAL Robot_Sts_RoutineID   $OUT[449] TO $OUT[480]    ; I.Data[56]
```

**The repo `$config.dat` still shows `$OUT[513]` / `$OUT[545]`. That is stale.**

Free output space: `$OUT[481..512]` (byte 60). Existing signals occupy `$OUT[1..58]`
(bytes 0–7) and `$OUT[257..416]` (bytes 32–51).

### COP lengths

COP length counts **destination** elements, and the two directions differ:

```
COP(Robot_Cmd_RoutineID, Station100_Robot:O.Data[64], 4)   ; dest SINT → 4 bytes
COP(Station100_Robot:I.Data[52], Robot_Sts_State,     1)   ; dest DINT → 1 element
```

**Known bug:** five pre-existing COPs in `Routine040300_InputStatus` use length 4
into a DINT destination — copying 16 bytes into 4 consecutive DINTs and overrunning
into neighbouring tags. Not fixed.

```
COP(Station100_Robot:I.Data[32], RtoTT_PlaceSeqNumber,     4)   ← should be 1
COP(Station100_Robot:I.Data[36], RtoDS_PlaceSeqNumber,     4)   ← should be 1
COP(Station100_Robot:I.Data[40], RtoIMM_SeqNumber,         4)   ← should be 1
COP(Station100_Robot:I.Data[44], RtoPLC_ToolBlnkSeqNumber, 4)   ← should be 1
COP(Station100_Robot:I.Data[48], RtoPLC_ToolFinSeqNumber,  4)   ← should be 1
```

---

## 4. Robot `Main.src` — current design

Roughly 87 lines, no `;FOLD` markers, plain KRL. Structure:

```
BeginningOfModule:          reset flags, save override, home at 30%, restore override,
                            set the three IMM enables, clear ToolBlnkMrked
LOOP
  stop check                PLCtoR_Stop or NOT PLCtoR_DrawerInPos → home, release IMM,
                            RtoPLC_RobotReachedStop, WAIT FOR $EXT_START
  WAIT FOR                  command OR stop
  latch Cmd, State=1
  SWITCH Cmd                10/20/30/40/50/60/71/72/73, DEFAULT → RobotCell_Error
  State = 2 or 3
  WAIT FOR Robot_Cmd_RoutineID==0
  fault → GOTO BeginningOfModule
ENDLOOP
```

### KRL rules learned the hard way

- The `&ACCESS` / `&REL` / `&PARAM` header block must be followed **immediately** by
  `DEF`. A blank line between them gives `ReadHeader() 66 — File format not correct
  (header syntax)`.
- All `DECL` statements must come **before** any instruction, including
  `GLOBAL INTERRUPT DECL`, `INTERRUPT ON` and `BAS(#INITMOV,0)`. Otherwise:
  error 2038, "Declaration not in declaration section".
- `&PARAM DISKPATH` is optional — a working module on this controller has none.
- Files must be CRLF, ANSI (no BOM). `.gitattributes` enforces CRLF in the repo.
- `$config.dat` is a **linked module** — it cannot be overwritten from USB. It must be
  edited in place in the pendant editor.

### Main.dat

Unchanged. It declares a module-local `PDEFAULT` at `ACC 35.000`, which **shadows**
the `$config.dat` global at `ACC 100.000`. Without it the home move runs at roughly
3× the intended joint acceleration.

---

## 5. PLC sequencer — `_03_RobotSequencer`

Two layers in one routine. **Rung numbers below were correct at one point in the
session and have since shifted — do not trust them, read the routine.**

### Layer 1: handshake (~rungs 0–13)

`HS_Step` walks 0 → 10 → 20 → 30 → 0, or to 90 on fault.

| `HS_Step` | Meaning |
|---:|---|
| 0 | idle; a non-zero `Cmd_Request` with the robot idle issues the command |
| 10 | waiting for the robot to accept (state 1 + matching echo). 5 s → 90 |
| 20 | waiting for state 2 or 3. 120 s → 90 |
| 30 | command written to 0, waiting for the robot to confirm idle, then pulses `Cmd_Done` |
| 90 | faulted, held until `Seq_Reset` |

`Cmd_Done` is an **OTE** on the rung that also zeroes `HS_Step`, so it self-clears
after one scan. Nothing needs to unlatch it.

Nothing outside this block should ever write `Robot_Cmd_RoutineID`.

### Layer 2: request translator

One rung per condition, in priority order (first match blocks the rest via
`EQU(Cmd_Request,0)`). The bits it reads were already driven by the existing station
logic — the translator only turns them into routine IDs.

```
UStoR_ReqToMoveLayer                                            → 20
UStoR_ReqToPick      AND NOT ToolBlnkHasParts                   → 20
TTtoR_ReqToPlace     AND NOT ToolBlnkMrked                      → 30
(ReqToPickGood OR ReqToPickBad) AND NOT ToolBlnkHasParts        → 30
ToolBlnkMrked AND IMMtoR_MoldOpen AND IMMtoR_OpEnable           → 40
ToolFinHasParts AND NOT SprueCutDone                            → 50
ToolFinHasParts AND SprueCutDone AND DStoR_DropInShoot          → 60
```

Plus two rungs maintaining `SprueCutDone`: OTL when routine 50 completes, OTU when
60 completes.

**The `ReqToPickGood` / `ReqToPickBad` contacts must be in PARALLEL (a branch), not
series.** This was wrong once already.

### Tool state — the arbitration that matters

| `RtoPLC_ToolBlnkHasParts` | `RtoPLC_ToolBlnkMrked` | Meaning |
|---|---|---|
| F | F | empty → can pick from upstacker |
| T | F | holding an unmarked blank → belongs on the turntable |
| T | T | holding a marked blank → belongs in the IMM |

Both are robot outputs, maintained by the station programs:
- `UpStacker` L162/171 → `HasParts = True`
- `LaserMarker` L147 → `HasParts = False`; L298/324/341 → `True`; L315 → `Mrked = True`
- `IMM` L507/509 → both `False`
- `Reject` L57/58 → both `False`

---

## 6. Starting the robot in EXT

`Routine040600_Robot_Startup` already contains the whole Ext Auto chain. It hangs off
two things:

```
[XIC(CRM) XIO(Unlock_Doors), XIC(Optix_RobotMoveEnable)] OTE(PLCtoR_MoveEnable)
XIC(PLCtoR_MoveEnable) OTE(PLCtoR_DrivesOff)
... gated on PLCtoR_Start and RtoPLC_InAuto → DrivesOn → ConfMess → ExtStart
```

**A door-unlock request blocks `PLCtoR_MoveEnable` and therefore everything.** That
bit us this session.

### Cold start procedure

1. Select `Main`
2. Switch to **T1**
3. Hold **Start** until "programmed path reached (BCO)". Releasing early aborts it.
4. Switch to **EXT**
5. `PLCtoR_MoveEnable` true, then `PLCtoR_Start`

Diagnostic screen: **Main menu → Diagnosis → Ext Auto**, which shows each required
signal green/red.

Useful facts:
- `$DRIVES_OFF` is **normally HIGH**. Low means "turn drives off".
- Manual I/O writes from the pendant are **blocked in AUT/EXT**. Test in T1.
- `$PRO_STATE1` should read `#P_ACTIVE` when running.
- The `T1 B0` cluster in the top right is **Tool 1 / Base 0**, not the operating mode.
  The mode is the box next to `R`.

---

## 7. IMM routine — `Station400_IMM.src`

### Edit made this session (on the controller, NOT in the repo)

Lines 72 and 109 had the `RtoIMM_SeqNumber` terms removed:

```krl
; line 72  (pick)
If (IMMtoR_MoldOpen==True) AND (IMMtoR_PartInjected==True) Then
; line 109 (place)
If (IMMtoR_MoldOpen==True) AND (IMMtoR_PartInjected==False) Then
```

Branch selection now depends purely on `IMMtoR_PartInjected`, which the PLC owns.
Previously `RtoIMM_SeqNumber` (a robot-owned register, the mould's only part-present
memory — there is no cavity sensor) was OR'd in, which meant the PLC could force a
pick but never a place.

**One routine-40 visit does BOTH**: extract the shot if there is one, then load
blanks. It is not either/or.

### Entry gate — both branches

| Signal | Note |
|---|---|
| `IMMtoR_OpEnable` TRUE | L31, **no timeout** — robot hangs here silently |
| `PLCtoR_Start` TRUE | `sps.sub` uses it to clear `RtoIMM_RobotWithIMM` for L32 |
| `IMMtoR_EjectPosBck` TRUE | L49, 5 s window |
| `IMMtoR_MoldOpen` TRUE | L72 / L109 |

`sps.sub` (Submit interpreter) owns `RtoIMM_RobotWithIMM`:
```
IMMtoR_OpEnable FALSE                        → RobotWithIMM = True
IMMtoR_OpEnable TRUE AND PLCtoR_Start TRUE   → RobotWithIMM = False
```

### Pick additionally needs

- `IMMtoR_PartInjected` TRUE
- `PLCtoR_FinishCupAVacOn` + `BVacOn` TRUE (vacuum switch feedback)
- Ejector handshake, **5 s each**:
  `RtoIMM_MoldEjectFrw` → answer `IMMtoR_EjectPosFrw`;
  `RtoIMM_MoldEjectBack` → answer `IMMtoR_EjectPosBck`

Miss the ejector-forward window and the robot **blows the part off and aborts**
(vacuum off, blow-off on, `RtoIMM_SeqNumber` cleared). This presents as "it rejected
the part" and is not a reject at all.

### Place additionally needs

- `IMMtoR_PartInjected` FALSE
- `RtoPLC_ToolBlnkHasParts` TRUE
- `PLCtoR_BlankCupAVacOn` + `BVacOn` TRUE

### How `IMMtoR_PartInjected` is driven — **PROBLEM**

```
[ XIC(EM67_ZA5),
  XIC(amp_Test_Bits.28),
  XIC(Good_Part_Pick_From_IMM) XIO(Place_In_IMM),
  XIC(Bad_Part_Pick_From_IMM) ]  OTE(IMMtoR_PartInjected)
```

`EM67_ZA5` is aliased to `Local:2:I.Data.0` and its description is
**"IMM - ROBOT REJECT"**. Euromap 67 ZA5 is the reject signal, not part-injected.

`IMMtoR_Rejected` — which `Station400_IMM.src` L73 actually reads — is **driven by
nothing in the entire project**.

So when the real IMM is connected, "this shot is bad" will tell the robot "there is a
part to pick", and the robot's reject handling will never fire. Needs resolving before
the machine goes live. **Not fixed.**

Note the asymmetry in that rung: the `Good_Part` leg has `XIO(Place_In_IMM)`, the
`Bad_Part` leg does not.

---

## 8. Open items — NOT DONE

### PLC

- [ ] `Seq_Reset` rung needs `MOV(0,Robot_Cmd_RoutineID)` added, or pressing reset
      mid-routine strands the robot waiting for a zero that never comes
- [ ] Confirm `Seq_Run` and `Seq_Reset` are actually driven by something
- [ ] Confirm `Program031000_RobotSequencer` (the old 66-rung sequencer) is unscheduled
- [ ] Five COP lengths in `Routine040300_InputStatus` (§3)
- [ ] Manual reject buttons for 71/72/73 — nothing commands a reject today
- [ ] IMM simulation rungs are woven into the auto-sequencer conditions. They will
      still be there at the open house. Move them out or remove them.

### Robot

- [ ] `Station500_Reject.src` line 123 `$OV_PRO=100` — slams override to full on every
      reject. **Removed in the repo, never transferred to the controller.**
- [ ] `Station400_IMM.src` lines 166, 235, 413 set `$OV_PRO=30` on error paths and
      never restore it. `Main.src` now saves/restores around its home move, so these
      leave the robot at 30% until a fault restart.
- [ ] `Station600_DownStacker` writes `RtoDS_PickErrorVG530` where it should be VG528
- [ ] Row/column of 0 or out of range indexes `E6POS[2,4]` out of bounds and faults
      the robot. `UpAxis_Memory` is `SINT[12]` while rung 7 allows 13 — that one
      major-faults the processor.

### Hardware

- [ ] Controller battery defective (`KSS13103`). Reboot only from the HMI. A hard
      power pull risks losing mastering.
- [ ] A door interlock was manually overridden during testing. **Verify it is restored
      before the open house.**

---

## 9. Behaviour notes

- A bad-marked blank currently takes the same path as a good one — straight into the
  mould. Nothing diverts it. This has always been true; it is not a regression.
- If `RtoPLC_ToolFinHasParts` is already true at startup (part left on the tool), the
  translator commands a sprue cut immediately, before anything else.
- The robot cannot abort mid-routine. Dropping `Seq_Run` only prevents the *next*
  command.

---

## 10. Working style for the next session

The person doing this work is a controls engineer at the machine. They want:

- Answers, not repo edits. Do not commit or push unless asked.
- Factual answers about what the code does, grounded in the files — not design
  proposals, and not assumptions about what "should" be there.
- Small, verifiable changes. Every round trip to the pendant costs ten minutes.
- When something is unknown, say so rather than inferring.

**Get the fresh exports first.** Several hours were lost this session to reasoning
about stale files.
