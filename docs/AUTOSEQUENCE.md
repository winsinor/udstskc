# Auto-Sequence Framework

The PLC-as-master sequencer, ready to build. Every rung below is Logix **neutral text** — the same
syntax as the `<Text>` blocks in the L5X exports — so it pastes straight into a routine in
Studio 5000.

Companion to [`PLC_MASTER_PLAN.md`](PLC_MASTER_PLAN.md) (interface spec) and
[`PART_MEMORY.md`](PART_MEMORY.md) (data model).

> `?` in timer and counter operands is deliberate — set the presets in Studio 5000 after pasting.
> Suggested values are in the rung notes.

---

## Build order

1. Create the three UDTs (§1).
2. Create the tags (§2) — controller scope.
3. Create program `Program031000_RobotSequencer` with the six routines in §3–§8.
4. Add the two rungs in §9 to `Program040000_Station100_Robot`.
5. Commission with §8 (manual) before enabling §5 (auto).

---

## 1. UDTs

```
STRING_20            Family: StringFamily
   LEN      DINT
   DATA     SINT[20]        Radix: ASCII

Part_Record          Family: NoFamily
   Present  BOOL
   Good     BOOL
   Bad      BOOL
   Name     STRING_20

Part_Pair            Family: NoFamily
   Seq_Num  DINT
   State    DINT
   A        Part_Record
   B        Part_Record
```

## 2. Tags

**Robot interface** — these are the words that cross to the robot.

| Tag | Type | Notes |
|---|---|---|
| `Robot_Cmd_RoutineID` | DINT | 0 = none. See the routine map. |
| `Robot_Cmd_Seq` | DINT | Increments on every new command |
| `Robot_Cmd_Param1..4` | DINT | Row, column, seq A, seq B |
| `Robot_Cmd_RetryLimit` | DINT | Default 2 |
| `Robot_Sts_State` | DINT | 0 idle · 1 running · 2 complete · 3 faulted · 4 held |
| `Robot_Sts_RoutineID` | DINT | Echo of what is running / just finished |
| `Robot_Sts_AckSeq` | DINT | Echo of `Robot_Cmd_Seq` |
| `Robot_Sts_FaultCode` | DINT | 0 when not faulted |
| `Robot_Sts_RetryCount` | DINT | Retries consumed |
| `Robot_Sts_SubStep` | DINT | `IMMExchange` / `LayerShift` progress |

**Command handshake**

`Seq_ReqRoutineID` DINT · `Seq_ReqParam1..4` DINT · `Seq_IssueCmd` BOOL · `Seq_CmdBusy` BOOL ·
`Seq_CmdAccepted` BOOL · `Seq_CmdDone` BOOL · `Seq_CmdFault` BOOL · `Seq_CmdConsume` BOOL ·
`Seq_FaultCode` DINT · `Seq_AckTimer` TIMER · `Seq_RunTimer` TIMER · `Seq_ONS` DINT

**Sequencer**

`Seq_Step` DINT · `Seq_NextStep` DINT

**Cycle and modes**

`Mode_Auto` `Mode_Manual` `Mode_Dry` `Mode_Purge` BOOL ·
`Cyc_Start` `Cyc_Stop` `Cyc_InCycle` `Cyc_Faulted` `Cyc_StopRequested` BOOL ·
`Cyc_Homed` BOOL · `Purge_Active` BOOL

**Zones** — robot occupancy, one bit each: `Z1_Stackers` `Z2_Turntable` `Z3_Mold`
`Z4_SprueReject` `Z5_Chute` BOOL

**Requests** — what step 0 dispatches on: `Req_PickUpstacker` `Req_PlaceTurntable`
`Req_PickTurntable` `Req_IMMExchange` `Req_SprueCut` `Req_DropChute` `Req_LayerShift`
`Req_Reject` BOOL

**Part memory**

`Part_Log` Part_Pair[500] · `Part_Seq_Next` DINT · `Loc_RobotBlank` DINT ·
`Loc_RobotFinish` DINT · `Loc_Nest1..4` DINT · `Loc_Mold` DINT · `Loc_Delivered` DINT ·
`Reject_Sel` DINT

**Manual faceplate**

`Man_RoutineID` DINT · `Man_Param1..4` DINT · `Man_Fire` BOOL

---

## 3. `R000_Main`

```
JSR(R100_CommandInterface,0);
JSR(R200_Requests,0);
JSR(R300_Sequencer,0);
JSR(R400_PartMemory,0);
JSR(R500_Modes,0);
JSR(R900_Manual,0);
```

---

## 4. `R100_CommandInterface`

The whole point of the rework lives here. Completion is a **held state**, not a pulse, so a slow
scan or a PLC fault cannot lose it.

**Rung 0 — issue a command.** Only when the robot is idle. Increments `Robot_Cmd_Seq` so a repeat
of the same routine ID is still seen as a new command.

```
XIC(Seq_IssueCmd)EQU(Robot_Sts_State,0)XIO(Seq_CmdBusy)ONS(Seq_ONS.0)[MOV(Seq_ReqRoutineID,Robot_Cmd_RoutineID) ,MOV(Seq_ReqParam1,Robot_Cmd_Param1) MOV(Seq_ReqParam2,Robot_Cmd_Param2) ,MOV(Seq_ReqParam3,Robot_Cmd_Param3) MOV(Seq_ReqParam4,Robot_Cmd_Param4) ,ADD(Robot_Cmd_Seq,1,Robot_Cmd_Seq) ,OTL(Seq_CmdBusy) OTU(Seq_CmdDone) OTU(Seq_CmdFault) OTU(Seq_CmdAccepted) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ,OTU(Seq_IssueCmd) ];
```

**Rung 1 — wrap the sequence counter** before it can overflow.

```
GRT(Robot_Cmd_Seq,32000)MOV(1,Robot_Cmd_Seq);
```

**Rung 2 — command accepted.** The robot echoed our sequence number and is running it.

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,1)OTL(Seq_CmdAccepted);
```

**Rung 3 — complete.**

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,2)ONS(Seq_ONS.1)[OTL(Seq_CmdDone) ,OTU(Seq_CmdBusy) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ];
```

**Rung 4 — faulted.** Latch the robot's own fault code.

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,3)ONS(Seq_ONS.2)[OTL(Seq_CmdFault) ,MOV(Robot_Sts_FaultCode,Seq_FaultCode) ,OTU(Seq_CmdBusy) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ];
```

**Rung 5 — acceptance timeout.** The robot never acknowledged. Preset ~3 s.

```
XIC(Seq_CmdBusy)XIO(Seq_CmdAccepted)TON(Seq_AckTimer,?,?)XIC(Seq_AckTimer.DN)ONS(Seq_ONS.3)[OTL(Seq_CmdFault) ,MOV(9001,Seq_FaultCode) ,OTU(Seq_CmdBusy) ];
```

**Rung 6 — run timeout.** The robot accepted but never finished. Preset ~120 s; raise it if
`IMMExchange` legitimately runs longer.

```
XIC(Seq_CmdAccepted)XIC(Seq_CmdBusy)TON(Seq_RunTimer,?,?)XIC(Seq_RunTimer.DN)ONS(Seq_ONS.4)[OTL(Seq_CmdFault) ,MOV(9002,Seq_FaultCode) ,OTU(Seq_CmdBusy) ];
```

**Rung 7 — consume.** Writing `RoutineID = 0` is what releases the robot from its held state back
to idle. Nothing else does.

```
[XIC(Seq_CmdDone) ,XIC(Seq_CmdFault) ]XIC(Seq_CmdConsume)[MOV(0,Robot_Cmd_RoutineID) ,OTU(Seq_CmdDone) OTU(Seq_CmdFault) OTU(Seq_CmdAccepted) ,OTU(Seq_CmdConsume) ];
```

---

## 5. `R300_Sequencer`

**Rung 0 — step advance.** Also the reset: leaving cycle, or first scan, forces step 0.

```
[[XIO(Cyc_InCycle) ,XIC(S:FS) ][MOV(0,Seq_Step) ,MOV(0,Seq_NextStep) ] ,MOV(Seq_NextStep,Seq_Step) ];
```

**Rung 1 — step 0, the decision.**

> **Read this carefully.** All branches are evaluated in order, so the **last true branch wins**.
> The list is therefore written lowest priority first — `Req_Reject` at the bottom is the highest
> priority. If you reorder these, you change the cell's priority order.

```
EQU(Seq_Step,0)XIC(Cyc_InCycle)XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)[XIC(Req_PickUpstacker) MOV(200,Seq_NextStep) ,XIC(Req_PlaceTurntable) MOV(300,Seq_NextStep) ,XIC(Req_PickTurntable) MOV(400,Seq_NextStep) ,XIC(Req_DropChute) MOV(700,Seq_NextStep) ,XIC(Req_SprueCut) MOV(600,Seq_NextStep) ,XIC(Req_IMMExchange) MOV(500,Seq_NextStep) ,XIC(Req_LayerShift) MOV(800,Seq_NextStep) ,XIC(Req_Reject) MOV(900,Seq_NextStep) ];
```

**Rungs 2–10 — the action steps.** Every one is the same three-branch shape: issue, then on done go
back to 0, on fault go to 9999. The bookkeeping is *not* here — it lives in `R400_PartMemory`,
keyed off which routine completed, so these stay readable.

Step 100 — `Home`:
```
EQU(Seq_Step,100)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Seq_ONS.10)MOV(10,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) OTL(Cyc_Homed) MOV(0,Seq_NextStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Seq_NextStep) ];
```

Step 200 — `PickUpstacker`. Params carry the tray cell and the sequence number to allocate.
```
EQU(Seq_Step,200)XIC(Cyc_InCycle)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Seq_ONS.11)[MOV(20,Seq_ReqRoutineID) ,MOV(UpAxis_TrayRow,Seq_ReqParam1) MOV(UpAxis_TrayCol,Seq_ReqParam2) ,MOV(Part_Seq_Next,Seq_ReqParam3) ]OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Seq_NextStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Seq_NextStep) ];
```

Steps 300, 400, 600, 700, 800 follow the identical pattern — copy step 200 and change the
`EQU` step number, the `ONS` bit, and the routine ID:

| Step | `ONS` bit | Routine ID | Routine |
|---:|---|---:|---|
| 300 | `Seq_ONS.12` | 30 | `PlaceTurntable` |
| 400 | `Seq_ONS.13` | 40 | `PickTurntable` |
| 500 | `Seq_ONS.14` | 50 | `IMMExchange` |
| 600 | `Seq_ONS.15` | 60 | `SprueCut` |
| 700 | `Seq_ONS.16` | 70 | `DropChute` |
| 800 | `Seq_ONS.17` | 80 | `LayerShift` |
| 900 | `Seq_ONS.18` | 90 | `Reject` (Param1 = `Reject_Sel`) |

Step 900 — `Reject`, which needs the selector:
```
EQU(Seq_Step,900)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Seq_ONS.18)[MOV(90,Seq_ReqRoutineID) ,MOV(Reject_Sel,Seq_ReqParam1) ]OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) OTU(Req_Reject) MOV(0,Seq_NextStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Seq_NextStep) ];
```

**Rung 11 — step 9999, fault hold.** The cell sits here until acknowledged.
```
EQU(Seq_Step,9999)[OTE(Cyc_Faulted) ,XIC(HMI_Reset)ONS(Seq_ONS.19)[OTU(Seq_CmdFault) ,MOV(0,Seq_FaultCode) ,MOV(0,Seq_NextStep) ] ];
```

---

## 6. `R200_Requests`

What makes step 0 dispatch. Each request is a plain statement of "this is now possible", derived
from part memory and the zone bits — never from robot state directly.

```
EQU(Loc_RobotBlank,0)XIC(UpAxis_PosValid)XIO(RequestLayerShift)XIO(Purge_Active)OTE(Req_PickUpstacker);
```
```
NEQ(Loc_RobotBlank,0)EQU(Part_Log[Loc_RobotBlank].State,20)EQU(Loc_Nest1,0)XIO(Weiss:I.Active)OTE(Req_PlaceTurntable);
```
```
NEQ(Loc_Nest1,0)EQU(Part_Log[Loc_Nest1].State,40)EQU(Loc_RobotBlank,0)XIO(Weiss:I.Active)OTE(Req_PickTurntable);
```
```
NEQ(Loc_RobotBlank,0)EQU(Part_Log[Loc_RobotBlank].State,50)EQU(Loc_RobotFinish,0)XIC(IMMtoR_MoldOpen)XIC(IMMtoR_OpEnable)OTE(Req_IMMExchange);
```
```
NEQ(Loc_RobotFinish,0)EQU(Part_Log[Loc_RobotFinish].State,70)OTE(Req_SprueCut);
```
```
NEQ(Loc_RobotFinish,0)EQU(Part_Log[Loc_RobotFinish].State,80)OTE(Req_DropChute);
```
```
XIC(RequestLayerShift)EQU(Loc_RobotBlank,0)EQU(Loc_RobotFinish,0)OTE(Req_LayerShift);
```

`Req_Reject` is latched by whatever decides to scrap a pair, with `Reject_Sel` set to
1 (blank side), 2 (finished side) or 3 (both) — not derived here.

---

## 7. `R400_PartMemory`

Bookkeeping, keyed off which routine just completed. `Seq_CmdDone` is held, so a one-shot on each
is safe and cannot be missed.

**Allocate on a successful upstacker pick.** The pair is born anonymous — the name attaches at the
laser, not here.
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,20)ONS(Seq_ONS.20)[MOV(Part_Seq_Next,Loc_RobotBlank) ,MOV(Part_Seq_Next,Part_Log[Part_Seq_Next].Seq_Num) ,MOV(20,Part_Log[Part_Seq_Next].State) ,OTL(Part_Log[Part_Seq_Next].A.Present) OTL(Part_Log[Part_Seq_Next].B.Present) ,ADD(Part_Seq_Next,1,Part_Seq_Next) ];
```
```
GRT(Part_Seq_Next,500)MOV(1,Part_Seq_Next);
```

**Place into the nest** — the pair moves from the gripper to nest station 1.
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,30)ONS(Seq_ONS.21)[MOV(Loc_RobotBlank,Loc_Nest1) ,MOV(30,Part_Log[Loc_RobotBlank].State) ,MOV(0,Loc_RobotBlank) ];
```

**Pick from the nest** — back onto the gripper, now marked.
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,40)ONS(Seq_ONS.22)[MOV(Loc_Nest1,Loc_RobotBlank) ,MOV(50,Part_Log[Loc_Nest1].State) ,MOV(0,Loc_Nest1) ];
```

**Mould exchange.** Two transfers in one routine: the old shot comes out onto the finished side,
the new pair goes into the cavities.
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,50)ONS(Seq_ONS.23)[MOV(Loc_Mold,Loc_RobotFinish) ,NEQ(Loc_Mold,0) MOV(70,Part_Log[Loc_Mold].State) ,MOV(Loc_RobotBlank,Loc_Mold) ,MOV(60,Part_Log[Loc_RobotBlank].State) ,MOV(0,Loc_RobotBlank) ];
```

**Sprue cut** and **chute drop**:
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,60)ONS(Seq_ONS.24)MOV(80,Part_Log[Loc_RobotFinish].State);
```
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,70)XIO(VG528)XIO(VG530)ONS(Seq_ONS.25)[MOV(90,Part_Log[Loc_RobotFinish].State) ,MOV(Loc_RobotFinish,Loc_Delivered) ,MOV(0,Loc_RobotFinish) ];
```
> There is no chute sensor, so delivery is confirmed by **both finished-side vacuum switches
> reading released**. That catches a part still stuck to the tooling — the failure that actually
> matters with a visitor waiting at the chute.

**Turntable rotation** — four DINT moves, not five record copies. There are four stations, held in
four **scalar** tags: a nest location is used as a subscript into `Part_Log`, and Logix will not
accept an array element as an array subscript.
```
XIC(TurnTable_Move_ONS)[MOV(Loc_Nest4,Loc_NestTemp) ,MOV(Loc_Nest3,Loc_Nest4) ,MOV(Loc_Nest2,Loc_Nest3) ,MOV(Loc_Nest1,Loc_Nest2) ,MOV(Loc_NestTemp,Loc_Nest1) ];
```

**Reject** — clears whichever half the selector named.
```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,90)ONS(Seq_ONS.26)[[EQU(Reject_Sel,1) ,EQU(Reject_Sel,3) ] NEQ(Loc_RobotBlank,0) MOV(900,Part_Log[Loc_RobotBlank].State) MOV(0,Loc_RobotBlank) ,[EQU(Reject_Sel,2) ,EQU(Reject_Sel,3) ] NEQ(Loc_RobotFinish,0) MOV(900,Part_Log[Loc_RobotFinish].State) MOV(0,Loc_RobotFinish) ];
```

**Sensor corroboration.** Memory and sensors must agree; on disagreement the cell holds rather than
self-correcting. One rung per location, this is the nest pattern:
```
NEQ(Loc_Nest1,0)XIO(PE202)XIO(PE203)TON(Mem_Disagree_TMR[1],?,?)XIC(Mem_Disagree_TMR[1].DN)[OTL(Mem_Disagree) ,MOV(1,Mem_Disagree_Loc) ,OTL(Cyc_StopRequested) ];
```
> Preset ~1 s so a part in transit does not trip it. `Mem_Disagree_Loc` drives the alarm text, so
> the message names the location and the direction rather than saying something generic.

**Clear on first scan** — `Part_Log` is not retentive.
```
XIC(S:FS)[FLL(0,Part_Log[0],500) ,MOV(1,Part_Seq_Next) ,MOV(0,Loc_RobotBlank) MOV(0,Loc_RobotFinish) ,FLL(0,Loc_Nest0,5) ,MOV(0,Loc_Mold) MOV(0,Loc_Delivered) ];
```

---

## 8. `R500_Modes`

```
EQU(HMI_Mode_Select,1)XIC(EStop_OK)OTE(Mode_Manual);
EQU(HMI_Mode_Select,2)XIC(EStop_OK)OTE(Mode_Auto);
EQU(HMI_Mode_Select,3)XIC(EStop_OK)OTE(Mode_Dry);
EQU(HMI_Mode_Select,4)XIC(EStop_OK)OTE(Mode_Purge);
```

**In cycle.** Requires homing first — nothing moves unasked.
```
XIC(Mode_Auto)XIC(Cyc_Homed)XIO(Cyc_Faulted)[XIC(Cyc_Start)ONS(Seq_ONS.30)OTU(Cyc_StopRequested) ,XIC(Cyc_InCycle) ]XIO(Cyc_StopRequested)OTE(Cyc_InCycle);
```

**Cycle stop takes effect at end of part**, not mid-routine.
```
[XIC(Cyc_Stop) ,XIC(PLCtoR_DrawerFull) ,XIC(Mem_Disagree) ,XIO(Mode_Auto) ]OTL(Cyc_StopRequested);
```

**Purge** — stop feeding new blanks, let everything already in the cell finish.
```
XIC(Mode_Purge)OTE(Purge_Active);
XIC(Purge_Active)EQU(Loc_RobotBlank,0)EQU(Loc_RobotFinish,0)EQU(Loc_Nest1,0)EQU(Loc_Nest2,0)EQU(Loc_Nest3,0)EQU(Loc_Nest4,0)EQU(Loc_Mold,0)OTE(Cell_Empty);
```

**Zone occupancy.** With overlap permitted everywhere, the turntable is blocked only while the
robot is physically at the nest — one interlock, not a matrix.
```
XIC(Seq_CmdAccepted)[EQU(Robot_Sts_RoutineID,30) ,EQU(Robot_Sts_RoutineID,40) ]OTE(Z2_Turntable);
XIC(Z2_Turntable)OTU(VFD_Index_REQUEST);
```

**Turntable index trigger** — the sequencer owns it.
```
XIC(Cyc_InCycle)XIO(Z2_Turntable)XIC(Nest1_Serviced)ONS(Seq_ONS.31)OTL(VFD_Index_REQUEST);
```

---

## 9. `R900_Manual` — the commissioning tool

**Build this first.** Everything in Phase 3 is proven through it, one routine at a time, before the
auto sequencer is ever enabled.

```
XIC(Mode_Manual)XIC(Man_Fire)EQU(Robot_Sts_State,0)XIO(Seq_CmdBusy)ONS(Seq_ONS.40)[MOV(Man_RoutineID,Seq_ReqRoutineID) ,MOV(Man_Param1,Seq_ReqParam1) MOV(Man_Param2,Seq_ReqParam2) ,MOV(Man_Param3,Seq_ReqParam3) MOV(Man_Param4,Seq_ReqParam4) ,OTL(Seq_IssueCmd) ,OTU(Man_Fire) ];
```
```
XIC(Mode_Manual)[XIC(Seq_CmdDone) ,XIC(Seq_CmdFault) ]XIC(Man_Ack)ONS(Seq_ONS.41)[OTL(Seq_CmdConsume) ,OTU(Man_Ack) ];
```

The faceplate needs six fields and four indicators: routine ID, four params, fire; state, routine
echo, fault code, retry count.

---

## 10. Rungs for `Program040000_Station100_Robot`

Add to `Routine040700_OutputActions` — PLC to robot:
```
COP(Robot_Cmd_RoutineID,Station100_Robot:O.Data[64],4)COP(Robot_Cmd_Seq,Station100_Robot:O.Data[68],4)COP(Robot_Cmd_Param1,Station100_Robot:O.Data[72],4)COP(Robot_Cmd_Param2,Station100_Robot:O.Data[76],4)COP(Robot_Cmd_Param3,Station100_Robot:O.Data[80],4)COP(Robot_Cmd_Param4,Station100_Robot:O.Data[84],4)COP(Robot_Cmd_RetryLimit,Station100_Robot:O.Data[88],4);
```

Add to `Routine040300_InputStatus` — robot to PLC:
```
COP(Station100_Robot:I.Data[64],Robot_Sts_State,4)COP(Station100_Robot:I.Data[68],Robot_Sts_RoutineID,4)COP(Station100_Robot:I.Data[72],Robot_Sts_AckSeq,4)COP(Station100_Robot:I.Data[76],Robot_Sts_FaultCode,4)COP(Station100_Robot:I.Data[80],Robot_Sts_RetryCount,4)COP(Station100_Robot:I.Data[84],Robot_Sts_SubStep,4);
```

> Byte offsets 64–91 are **assumed free** and unverified — that is task 0.4. Check the assembly
> sizes in the EtherNet/IP config before pasting these.

---

## 11. Tags referenced but not defined here

These come from existing programs or are still to be created. The framework will not verify until
they exist:

`HMI_Reset` · `HMI_Mode_Select` · `EStop_OK` · `Weiss:I.Active` · `IMMtoR_MoldOpen` ·
`IMMtoR_OpEnable` · `VG528` · `VG530` · `PE202` · `PE203` · `PLCtoR_DrawerFull` ·
`RequestLayerShift` · `TurnTable_Move_ONS` · `VFD_Index_REQUEST` · `UpAxis_TrayRow` ·
`UpAxis_TrayCol` · `UpAxis_PosValid` · `Nest1_Serviced` · `Loc_NestTemp` · `Mem_Disagree` ·
`Mem_Disagree_Loc` · `Mem_Disagree_TMR` (TIMER[5]) · `Cell_Empty`

`UpAxis_TrayRow` / `UpAxis_TrayCol` / `UpAxis_PosValid` are the ones to add in the upstacker
program, derived from `UpAxis_NextValidPos` — which `R200_Tray_Positions_and_Data` already computes
correctly and currently sends nowhere.
