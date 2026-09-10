# Auto-Sequence Framework — ladder reference

**Generated from `plc/Program031000_RobotSequencer_Program.L5X`. Do not hand-edit.**
The L5X is the source of truth; this file exists so the logic is readable and diffable in the repo
and so rungs can be pasted individually if the import is ever a problem.

Design rationale: [`PLC_MASTER_PLAN.md`](PLC_MASTER_PLAN.md) · Data model:
[`PART_MEMORY.md`](PART_MEMORY.md) · Import guide: [`../plc/README.md`](../plc/README.md)

Timer presets are already in the tag data — `TON(tag,?,?)` is just how neutral text renders a timer
whose preset lives in the tag.

---

## Data types

### `UDT_Routine_Control`

| Member | Type | Notes |
|---|---|---|
| `Routine_Name` | STRING | Name Of Routine, Used for Data Logging Final Inspection Data |
| `Step_Description` | STRING | Text description for Current Cycle Step |
| `Routine_CurrentCycleStep` | DINT | Cycle Step Dint For Auto Control |
| `Routine_NextCycleStep` | DINT | Next Cycle Step For Auto Control |
| `Routine_CycleComplete` | BIT (bit 0) | Routine is Done |
| `Routine_CycleStarted` | BIT (bit 1) | Routine is Starting |
| `Fault_Dint` | DINT | Fault Bits |
| `Msg_Dint` | DINT | Message bits |
| `ONS_Dint` | DINT | One Shot |
| `Station_Cycle_Time` | DINT | Stations Last cycle Time |

### `Part_Pair`

| Member | Type | Notes |
|---|---|---|
| `Seq_Num` | DINT | Identity, 1..500. Same as the Part_Log index. |
| `State` | DINT | 0 empty, 10 allocated, 20 on gripper unmarked, 30 in nest, 40 marked, 50 on gripper marked, 60 in mould, 70 on gripper moulded, 80 sprue cut, 90 delivered, 900 rejected. |
| `A_Present` | BIT (bit 0) | Cup A side holds a part. |
| `A_Good` | BIT (bit 1) | Cup A part is good. |
| `A_Bad` | BIT (bit 2) | Cup A part is scrap. |
| `B_Present` | BIT (bit 3) | Cup B side holds a part. |
| `B_Good` | BIT (bit 4) | Cup B part is good. |
| `B_Bad` | BIT (bit 5) | Cup B part is scrap. |

## Controller-scoped tags — the words that cross to the robot

| Tag | Type | Preset / init | Notes |
|---|---|---|---|
| `Robot_Cmd_RoutineID` | DINT | `—` | Routine the robot is commanded to run. 0 = none. |
| `Robot_Cmd_Seq` | DINT | `—` | Increments on every new command so a repeat of the same routine ID is still a new command. |
| `Robot_Cmd_Param1` | DINT | `—` | Tray row, or reject selector on routine 90. |
| `Robot_Cmd_Param2` | DINT | `—` | Tray column. |
| `Robot_Cmd_Param3` | DINT | `—` | Sequence number for part A. |
| `Robot_Cmd_Param4` | DINT | `—` | Sequence number for part B. |
| `Robot_Cmd_RetryLimit` | DINT | `2` | Retries the robot may take before reporting faulted. |
| `Robot_Sts_State` | DINT | `—` | 0 idle, 1 running, 2 complete, 3 faulted, 4 held. HELD, not pulsed. |
| `Robot_Sts_RoutineID` | DINT | `—` | Routine running, or the one just completed or faulted. |
| `Robot_Sts_AckSeq` | DINT | `—` | Echo of Robot_Cmd_Seq. Command is latched when this matches. |
| `Robot_Sts_FaultCode` | DINT | `—` | 0 when not faulted. |
| `Robot_Sts_RetryCount` | DINT | `—` | Retries consumed on the current routine. |
| `Robot_Sts_SubStep` | DINT | `—` | IMMExchange / LayerShift progress. 1 entered, 2 shot gripped, 3 blanks released, 4 clear. |

## Program-scoped tags

| Tag | Type | Preset / init | Notes |
|---|---|---|---|
| `Seq_ReqRoutineID` | DINT | `—` | Routine the sequencer or faceplate wants issued. |
| `Seq_ReqParam1` | DINT | `—` |  |
| `Seq_ReqParam2` | DINT | `—` |  |
| `Seq_ReqParam3` | DINT | `—` |  |
| `Seq_ReqParam4` | DINT | `—` |  |
| `Seq_IssueCmd` | BOOL | `—` | Set to request that a command be issued. Cleared once issued. |
| `Seq_CmdBusy` | BOOL | `—` | A command is outstanding. |
| `Seq_CmdAccepted` | BOOL | `—` | Robot acknowledged our sequence number and is running. |
| `Seq_CmdDone` | BOOL | `—` | Robot reported complete. Held until consumed. |
| `Seq_CmdFault` | BOOL | `—` | Robot reported faulted, or a timeout expired. Held until consumed. |
| `Seq_CmdConsume` | BOOL | `—` | Set to release the robot from its held state back to idle. |
| `Robot_Seq` | UDT_Routine_Control | `—` | Sequencer control block. Supersedes the inert Robot_Auto in Routine030600_RobotAutoSequence, which can be deleted once this runs. |
| `Seq_CycleTimer` | TIMER | `[0,600000,0]` | Measures how long the last commanded routine took. Preset is large so it free-runs; only .ACC is read. |
| `Seq_AckTimer` | TIMER | `[0,3000,0]` | Acceptance timeout: robot never acknowledged. Preset 3 s. |
| `Seq_RunTimer` | TIMER | `[0,120000,0]` | Run timeout: accepted but never finished. Preset 120 s. Raise if IMMExchange legitimately runs longer. |
| `HMI_Mode_Select` | DINT | `—` | 1 manual, 2 auto, 3 dry, 4 purge. |
| `Mode_Manual` | BOOL | `—` |  |
| `Mode_Auto` | BOOL | `—` |  |
| `Mode_Dry` | BOOL | `—` |  |
| `Mode_Purge` | BOOL | `—` |  |
| `Cyc_HomeReq` | BOOL | `—` | Operator home button. |
| `Cyc_Homed` | BOOL | `—` | Home routine has completed at least once since power up. |
| `Cyc_Start` | BOOL | `—` | Operator cycle start. |
| `Cyc_Stop` | BOOL | `—` | Operator cycle stop. |
| `Cyc_InCycle` | BOOL | `—` |  |
| `Cyc_StopRequested` | BOOL | `—` | Stop takes effect at end of part, not mid-routine. |
| `Cyc_Faulted` | BOOL | `—` |  |
| `Purge_Active` | BOOL | `—` | Stop feeding new blanks; let the cell run itself empty. |
| `Cell_Empty` | BOOL | `—` | No pair anywhere in the cell. |
| `Z2_Turntable` | BOOL | `—` | Robot is physically at the turntable nest. |
| `Idx_Request` | BOOL | `—` | Sequencer asks the turntable to index. |
| `Nest1_Serviced` | BOOL | `—` | Station 1 has been placed into or picked from since the last index. |
| `Req_PickUpstacker` | BOOL | `—` |  |
| `Req_PlaceTurntable` | BOOL | `—` |  |
| `Req_PickTurntable` | BOOL | `—` |  |
| `Req_IMMExchange` | BOOL | `—` |  |
| `Req_SprueCut` | BOOL | `—` |  |
| `Req_DropChute` | BOOL | `—` |  |
| `Req_LayerShift` | BOOL | `—` |  |
| `Req_Reject` | BOOL | `—` |  |
| `Reject_Sel` | DINT | `—` | 1 blank side, 2 finished side, 3 both. |
| `Part_Log` | Part_Pair[501] | `—` | Master part record, indexed by sequence number. Not retentive. |
| `Part_Seq_Next` | DINT | `1` | Next sequence to allocate. Wraps 1..500. |
| `Loc_RobotBlank` | DINT | `—` | Pair on the vacuum-cup half. 0 = empty. |
| `Loc_RobotFinish` | DINT | `—` | Pair on the gripper half. 0 = empty. |
| `Loc_Nest1` | DINT | `—` | Pair at turntable station 1 (robot load/unload). 0 = empty. Scalar, not an array element, because Logix cannot use an array element as an array subscript. |
| `Loc_Nest2` | DINT | `—` | Pair at turntable station 2. |
| `Loc_Nest3` | DINT | `—` | Pair at turntable station 3 (laser). |
| `Loc_Nest4` | DINT | `—` | Pair at turntable station 4. |
| `Loc_NestTemp` | DINT | `—` | Scratch for the nest rotation. |
| `Loc_Mold` | DINT | `—` | Pair in the cavities. No sensor corroborates this. |
| `Loc_Delivered` | DINT | `—` | Last pair confirmed out the chute. |
| `Mem_Disagree` | BOOL | `—` | Memory and a sensor disagree. Cell holds. |
| `Mem_Disagree_Loc` | DINT | `—` | Which location disagreed. Drives the alarm text. |
| `Mem_Disagree_TMR` | TIMER[5] | `[[0,1000,0],[0,1000,0],[0,1000,0],[0,1000,0],[0,1000,0]]` | Memory/sensor disagreement debounce, 1 s, so a part in transit does not trip it. |
| `Sim_MarkAtStation3` | BOOL | `—` | COMMISSIONING ONLY. Marks a pair complete on arrival at station 3 so the loop can be exercised with no laser wired. |
| `Man_RoutineID` | DINT | `—` |  |
| `Man_Param1` | DINT | `—` |  |
| `Man_Param2` | DINT | `—` |  |
| `Man_Param3` | DINT | `—` |  |
| `Man_Param4` | DINT | `—` |  |
| `Man_Fire` | BOOL | `—` | Momentary. Issues Man_RoutineID. |
| `Man_Ack` | BOOL | `—` | Momentary. Consumes a held complete or fault. |
| `Ext_EStopOK` | BOOL | `—` | MAP: safety relay OK. |
| `Ext_Reset` | BOOL | `—` | MAP: HMI / pushbutton reset. |
| `Ext_TurntableMoving` | BOOL | `—` | MAP: Weiss:I.Active. |
| `Ext_TurntableMoved` | BOOL | `—` | MAP: one-shot pulse when an index completes. |
| `Ext_TurntableIndexReq` | BOOL | `—` | MAP: drives VFD_Index_REQUEST. |
| `Ext_MoldOpen` | BOOL | `—` | MAP: IMMtoR_MoldOpen. |
| `Ext_OpEnable` | BOOL | `—` | MAP: IMMtoR_OpEnable. |
| `Ext_DrawerFull` | BOOL | `—` | MAP: PLCtoR_DrawerFull. |
| `Ext_LayerShiftReq` | BOOL | `—` | MAP: RequestLayerShift from the upstacker program. |
| `Ext_TrayPosValid` | BOOL | `—` | MAP: upstacker has a valid next position. |
| `Ext_TrayRow` | DINT | `—` | MAP: tray row from UpAxis_NextValidPos. |
| `Ext_TrayCol` | DINT | `—` | MAP: tray column from UpAxis_NextValidPos. |
| `Ext_MarkComplete` | BOOL | `—` | MAP: laser reports the fire complete. Unused until the marker is wired. |
| `Ext_Nest1PartA` | BOOL | `—` | MAP: PE202. |
| `Ext_Nest1PartB` | BOOL | `—` | MAP: PE203. |
| `Ext_FinCupAReleased` | BOOL | `—` | MAP: NOT VG528. |
| `Ext_FinCupBReleased` | BOOL | `—` | MAP: NOT VG530. |

---

## Routines

### `R000_Main`

```
JSR(R999_ExternalInterface,0);
```

```
JSR(R100_CommandInterface,0);
```

```
JSR(R200_Requests,0);
```

```
JSR(R300_Sequencer,0);
```

```
JSR(R400_PartMemory,0);
```

```
JSR(R500_Modes,0);
```

```
JSR(R900_Manual,0);
```

### `R999_ExternalInterface`

> MAP THESE TO THE REAL SIGNALS. Every Ext_ tag below is a stub so this program imports with no unresolved references and no module dependencies. Wire each one here, then delete this comment.

```
NOP();
```

> Ext_EStopOK        <- safety relay OK (CRM_S or equivalent)
> Ext_Reset          <- HMI_Reset
> Ext_TurntableMoving<- Weiss:I.Active
> Ext_TurntableMoved <- one-shot when an index completes (TurnTable_Move_ONS)

```
NOP();
```

> Ext_MoldOpen       <- IMMtoR_MoldOpen
> Ext_OpEnable       <- IMMtoR_OpEnable
> Ext_DrawerFull     <- PLCtoR_DrawerFull
> Ext_LayerShiftReq  <- RequestLayerShift (upstacker program)

```
NOP();
```

> Ext_TrayPosValid / Ext_TrayRow / Ext_TrayCol <- derived from UpAxis_NextValidPos, which R200_Tray_Positions_and_Data already computes and currently sends nowhere.

```
NOP();
```

> Ext_Nest1PartA <- PE202
> Ext_Nest1PartB <- PE203
> Ext_FinCupAReleased <- NOT VG528
> Ext_FinCupBReleased <- NOT VG530
> Ext_MarkComplete <- laser fire complete (leave clear until the marker is wired; use Sim_MarkAtStation3 instead)

```
NOP();
```

> OUTPUT: drive VFD_Index_REQUEST from Ext_TurntableIndexReq.

```
XIC(Idx_Request)OTE(Ext_TurntableIndexReq);
```

### `R100_CommandInterface`

> Issue a command. Only when the robot is idle. Robot_Cmd_Seq increments so a repeat of the same routine ID is still seen as a new command.

```
XIC(Seq_IssueCmd)EQU(Robot_Sts_State,0)XIO(Seq_CmdBusy)ONS(Robot_Seq.ONS_Dint.0)[MOV(Seq_ReqRoutineID,Robot_Cmd_RoutineID) ,MOV(Seq_ReqParam1,Robot_Cmd_Param1) MOV(Seq_ReqParam2,Robot_Cmd_Param2) ,MOV(Seq_ReqParam3,Robot_Cmd_Param3) MOV(Seq_ReqParam4,Robot_Cmd_Param4) ,ADD(Robot_Cmd_Seq,1,Robot_Cmd_Seq) ,OTL(Seq_CmdBusy) ,OTU(Seq_CmdDone) OTU(Seq_CmdFault) OTU(Seq_CmdAccepted) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ,OTU(Seq_IssueCmd) ];
```

> Wrap the sequence counter before it can overflow.

```
GRT(Robot_Cmd_Seq,32000)MOV(1,Robot_Cmd_Seq);
```

> Command accepted: the robot echoed our sequence number and is running it.

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,1)OTL(Seq_CmdAccepted);
```

> Complete. Held until consumed - this is the whole point of the rework. A slow scan or a PLC fault cannot lose it the way a 150 ms pulse can.

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,2)ONS(Robot_Seq.ONS_Dint.1)[OTL(Seq_CmdDone) ,OTU(Seq_CmdBusy) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ];
```

> Faulted. Latch the robot's own fault code.

```
XIC(Seq_CmdBusy)EQU(Robot_Sts_AckSeq,Robot_Cmd_Seq)EQU(Robot_Sts_State,3)ONS(Robot_Seq.ONS_Dint.2)[OTL(Seq_CmdFault) ,MOV(Robot_Sts_FaultCode,Robot_Seq.Fault_Dint) ,OTU(Seq_CmdBusy) ,RES(Seq_AckTimer) RES(Seq_RunTimer) ];
```

> Acceptance timeout - the robot never acknowledged. SET PRESET: 3000 ms.

```
XIC(Seq_CmdBusy)XIO(Seq_CmdAccepted)TON(Seq_AckTimer,?,?)XIC(Seq_AckTimer.DN)ONS(Robot_Seq.ONS_Dint.3)[OTL(Seq_CmdFault) ,MOV(9001,Robot_Seq.Fault_Dint) ,OTU(Seq_CmdBusy) ];
```

> Run timeout - accepted but never finished. SET PRESET: 120000 ms, longer if IMMExchange legitimately runs longer.

```
XIC(Seq_CmdAccepted)XIC(Seq_CmdBusy)TON(Seq_RunTimer,?,?)XIC(Seq_RunTimer.DN)ONS(Robot_Seq.ONS_Dint.4)[OTL(Seq_CmdFault) ,MOV(9002,Robot_Seq.Fault_Dint) ,OTU(Seq_CmdBusy) ];
```

> Cycle time and the UDT status flags. Station_Cycle_Time is the last commanded routine's duration in ms.

```
[XIC(Seq_CmdAccepted)XIC(Seq_CmdBusy)[OTE(Robot_Seq.Routine_CycleStarted) ,TON(Seq_CycleTimer,?,?) ] ,XIC(Seq_CmdDone)ONS(Robot_Seq.ONS_Dint.5)[MOV(Seq_CycleTimer.ACC,Robot_Seq.Station_Cycle_Time) ,OTL(Robot_Seq.Routine_CycleComplete) ,RES(Seq_CycleTimer) ] ,XIC(Seq_IssueCmd)OTU(Robot_Seq.Routine_CycleComplete) ];
```

> Consume. Writing RoutineID 0 is what releases the robot from its held state back to idle. Nothing else does.

```
[XIC(Seq_CmdDone) ,XIC(Seq_CmdFault) ]XIC(Seq_CmdConsume)[MOV(0,Robot_Cmd_RoutineID) ,OTU(Seq_CmdDone) OTU(Seq_CmdFault) OTU(Seq_CmdAccepted) ,OTU(Seq_CmdConsume) ];
```

### `R200_Requests`

> What makes step 0 dispatch. Each is a plain statement of 'this is now possible', derived from part memory - never from robot state directly.

```
EQU(Loc_RobotBlank,0)XIC(Ext_TrayPosValid)XIO(Ext_LayerShiftReq)XIO(Purge_Active)OTE(Req_PickUpstacker);
```

```
NEQ(Loc_RobotBlank,0)EQU(Part_Log[Loc_RobotBlank].State,20)EQU(Loc_Nest1,0)XIO(Ext_TurntableMoving)OTE(Req_PlaceTurntable);
```

```
NEQ(Loc_Nest1,0)EQU(Part_Log[Loc_Nest1].State,40)EQU(Loc_RobotBlank,0)XIO(Ext_TurntableMoving)OTE(Req_PickTurntable);
```

```
NEQ(Loc_RobotBlank,0)EQU(Part_Log[Loc_RobotBlank].State,50)EQU(Loc_RobotFinish,0)XIC(Ext_MoldOpen)XIC(Ext_OpEnable)OTE(Req_IMMExchange);
```

```
NEQ(Loc_RobotFinish,0)EQU(Part_Log[Loc_RobotFinish].State,70)OTE(Req_SprueCut);
```

```
NEQ(Loc_RobotFinish,0)EQU(Part_Log[Loc_RobotFinish].State,80)OTE(Req_DropChute);
```

```
XIC(Ext_LayerShiftReq)EQU(Loc_RobotBlank,0)EQU(Loc_RobotFinish,0)OTE(Req_LayerShift);
```

> Req_Reject is latched by whatever decides to scrap a pair, with Reject_Sel set to 1 blank / 2 finished / 3 both. Not derived here.

```
NOP();
```

### `R300_Sequencer`

> Step advance, and the reset: leaving cycle or first scan forces step 0.

```
[[XIO(Cyc_InCycle) ,XIC(S:FS) ][MOV(0,Robot_Seq.Routine_CurrentCycleStep) ,MOV(0,Robot_Seq.Routine_NextCycleStep) ] ,MOV(Robot_Seq.Routine_NextCycleStep,Robot_Seq.Routine_CurrentCycleStep) ];
```

> STEP 0 - THE DECISION. READ THIS BEFORE REORDERING. All branches are evaluated in order, so the LAST TRUE BRANCH WINS. The list is written lowest priority first: Req_Reject at the bottom is the highest priority. Reordering these changes the cell's priority order.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,0)XIC(Cyc_InCycle)XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)[XIC(Req_PickUpstacker) MOV(200,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_PlaceTurntable) MOV(300,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_PickTurntable) MOV(400,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_DropChute) MOV(700,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_SprueCut) MOV(600,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_IMMExchange) MOV(500,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_LayerShift) MOV(800,Robot_Seq.Routine_NextCycleStep) ,XIC(Req_Reject) MOV(900,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 100 - Home. Not gated on Cyc_InCycle: homing is what makes cycle possible.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,100)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.6)MOV(10,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) OTL(Cyc_Homed) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 200 - PickUpstacker. Params carry the tray cell and the sequence number to allocate.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,200)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.7)[MOV(20,Seq_ReqRoutineID) ,MOV(Ext_TrayRow,Seq_ReqParam1) MOV(Ext_TrayCol,Seq_ReqParam2) ,MOV(Part_Seq_Next,Seq_ReqParam3) ]OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 300 - PlaceTurntable.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,300)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.8)MOV(30,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 400 - PickTurntable.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,400)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.9)MOV(40,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 500 - IMMExchange. The only routine that can damage a mould. Prove it last.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,500)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.10)MOV(50,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 600 - SprueCut.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,600)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.11)MOV(60,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 700 - DropChute.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,700)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.12)MOV(70,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 800 - LayerShift.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,800)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.13)MOV(80,Seq_ReqRoutineID)OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 900 - Reject. Param1 carries the selector.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,900)[XIO(Seq_CmdBusy)XIO(Seq_CmdDone)XIO(Seq_CmdFault)ONS(Robot_Seq.ONS_Dint.14)[MOV(90,Seq_ReqRoutineID) ,MOV(Reject_Sel,Seq_ReqParam1) ]OTL(Seq_IssueCmd) ,XIC(Seq_CmdDone) OTL(Seq_CmdConsume) OTU(Req_Reject) MOV(0,Robot_Seq.Routine_NextCycleStep) ,XIC(Seq_CmdFault) OTL(Seq_CmdConsume) MOV(9999,Robot_Seq.Routine_NextCycleStep) ];
```

> Step 9999 - fault hold. The cell sits here until acknowledged.

```
EQU(Robot_Seq.Routine_CurrentCycleStep,9999)[OTE(Cyc_Faulted) ,XIC(Ext_Reset)ONS(Robot_Seq.ONS_Dint.15)[OTU(Seq_CmdFault) ,MOV(0,Robot_Seq.Fault_Dint) ,MOV(0,Robot_Seq.Routine_NextCycleStep) ] ];
```

### `R400_PartMemory`

> Clear on first scan. Part_Log is NOT retentive - after a power cycle the cell is auto-purged rather than trusted.

```
XIC(S:FS)[FLL(0,Part_Log[0],501) ,MOV(1,Part_Seq_Next) ,MOV(0,Loc_RobotBlank) MOV(0,Loc_RobotFinish) ,MOV(0,Loc_Nest1) MOV(0,Loc_Nest2) MOV(0,Loc_Nest3) MOV(0,Loc_Nest4) ,MOV(0,Loc_Mold) MOV(0,Loc_Delivered) ];
```

> Allocate on a successful upstacker pick. The pair is born anonymous; a name would attach at the laser, not here.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,20)ONS(Robot_Seq.ONS_Dint.16)[MOV(Part_Seq_Next,Loc_RobotBlank) ,MOV(Part_Seq_Next,Part_Log[Part_Seq_Next].Seq_Num) ,MOV(20,Part_Log[Part_Seq_Next].State) ,OTL(Part_Log[Part_Seq_Next].A_Present) OTL(Part_Log[Part_Seq_Next].B_Present) ,ADD(Part_Seq_Next,1,Part_Seq_Next) ];
```

```
GRT(Part_Seq_Next,500)MOV(1,Part_Seq_Next);
```

> Place into the nest - the pair moves from the gripper to station 1.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,30)ONS(Robot_Seq.ONS_Dint.17)[MOV(30,Part_Log[Loc_RobotBlank].State) ,MOV(Loc_RobotBlank,Loc_Nest1) ,MOV(0,Loc_RobotBlank) ,OTL(Nest1_Serviced) ];
```

> Pick from the nest - back onto the gripper, now marked.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,40)ONS(Robot_Seq.ONS_Dint.18)[MOV(50,Part_Log[Loc_Nest1].State) ,MOV(Loc_Nest1,Loc_RobotBlank) ,MOV(0,Loc_Nest1) ,OTL(Nest1_Serviced) ];
```

> Mould exchange - two transfers in one routine. The old shot comes out onto the finished side, the new pair goes into the cavities.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,50)ONS(Robot_Seq.ONS_Dint.19)[NEQ(Loc_Mold,0) MOV(70,Part_Log[Loc_Mold].State) ,MOV(Loc_Mold,Loc_RobotFinish) ,MOV(60,Part_Log[Loc_RobotBlank].State) ,MOV(Loc_RobotBlank,Loc_Mold) ,MOV(0,Loc_RobotBlank) ];
```

> Sprue cut.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,60)NEQ(Loc_RobotFinish,0)ONS(Robot_Seq.ONS_Dint.20)MOV(80,Part_Log[Loc_RobotFinish].State);
```

> Delivered. There is no chute sensor, so delivery is confirmed by BOTH finished-side vacuum switches reading released. That catches a part still stuck to the tooling - the failure that matters with someone waiting at the chute.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,70)NEQ(Loc_RobotFinish,0)XIC(Ext_FinCupAReleased)XIC(Ext_FinCupBReleased)ONS(Robot_Seq.ONS_Dint.21)[MOV(90,Part_Log[Loc_RobotFinish].State) ,MOV(Loc_RobotFinish,Loc_Delivered) ,MOV(0,Loc_RobotFinish) ];
```

> Reject - clears whichever half the selector named.

```
XIC(Seq_CmdDone)EQU(Robot_Sts_RoutineID,90)ONS(Robot_Seq.ONS_Dint.22)[[EQU(Reject_Sel,1) ,EQU(Reject_Sel,3) ] NEQ(Loc_RobotBlank,0) MOV(900,Part_Log[Loc_RobotBlank].State) OTL(Part_Log[Loc_RobotBlank].A_Bad) MOV(0,Loc_RobotBlank) ,[EQU(Reject_Sel,2) ,EQU(Reject_Sel,3) ] NEQ(Loc_RobotFinish,0) MOV(900,Part_Log[Loc_RobotFinish].State) OTL(Part_Log[Loc_RobotFinish].B_Bad) MOV(0,Loc_RobotFinish) ];
```

> Turntable rotation - four DINT moves, not five record copies. There are FOUR stations: the old TurnTable[0] was a scratch buffer, not a fifth.

```
XIC(Ext_TurntableMoved)ONS(Robot_Seq.ONS_Dint.23)[MOV(Loc_Nest4,Loc_NestTemp) ,MOV(Loc_Nest3,Loc_Nest4) ,MOV(Loc_Nest2,Loc_Nest3) ,MOV(Loc_Nest1,Loc_Nest2) ,MOV(Loc_NestTemp,Loc_Nest1) ,OTU(Nest1_Serviced) ];
```

> Mark complete at station 3. Ext_MarkComplete comes from the laser once it is wired. Sim_MarkAtStation3 lets the whole loop be exercised now, with no marker at all - CLEAR IT before the laser goes in.

```
NEQ(Loc_Nest3,0)EQU(Part_Log[Loc_Nest3].State,30)[XIC(Ext_MarkComplete) ,XIC(Sim_MarkAtStation3) ]ONS(Robot_Seq.ONS_Dint.24)[MOV(40,Part_Log[Loc_Nest3].State) ,OTL(Part_Log[Loc_Nest3].A_Good) OTL(Part_Log[Loc_Nest3].B_Good) ];
```

> Sensor corroboration at station 1. Memory and sensors must agree; on disagreement the cell HOLDS rather than self-correcting, and the alarm names the location. SET PRESET: 1000 ms so a part in transit does not trip it.

```
NEQ(Loc_Nest1,0)XIO(Ext_Nest1PartA)XIO(Ext_Nest1PartB)XIO(Z2_Turntable)TON(Mem_Disagree_TMR[1],?,?)XIC(Mem_Disagree_TMR[1].DN)[OTL(Mem_Disagree) ,MOV(1,Mem_Disagree_Loc) ,OTL(Cyc_StopRequested) ];
```

> Reverse check: a part is sitting in station 1 that the memory does not know about.

```
EQU(Loc_Nest1,0)[XIC(Ext_Nest1PartA) ,XIC(Ext_Nest1PartB) ]XIO(Z2_Turntable)TON(Mem_Disagree_TMR[2],?,?)XIC(Mem_Disagree_TMR[2].DN)[OTL(Mem_Disagree) ,MOV(2,Mem_Disagree_Loc) ,OTL(Cyc_StopRequested) ];
```

```
XIC(Ext_Reset)[OTU(Mem_Disagree) ,MOV(0,Mem_Disagree_Loc) ];
```

### `R500_Modes`

```
[EQU(HMI_Mode_Select,1) XIC(Ext_EStopOK) OTE(Mode_Manual) ,EQU(HMI_Mode_Select,2) XIC(Ext_EStopOK) OTE(Mode_Auto) ,EQU(HMI_Mode_Select,3) XIC(Ext_EStopOK) OTE(Mode_Dry) ,EQU(HMI_Mode_Select,4) XIC(Ext_EStopOK) OTE(Mode_Purge) ];
```

> Home on request. Nothing moves unasked - this is the operator's first of two deliberate actions.

```
XIC(Cyc_HomeReq)XIO(Cyc_InCycle)EQU(Robot_Seq.Routine_CurrentCycleStep,0)ONS(Robot_Seq.ONS_Dint.25)[MOV(100,Robot_Seq.Routine_NextCycleStep) ,OTU(Cyc_HomeReq) ];
```

> In cycle. Requires homing first.

```
[XIC(Mode_Auto) ,XIC(Mode_Dry) ]XIC(Cyc_Homed)XIO(Cyc_Faulted)[XIC(Cyc_Start)ONS(Robot_Seq.ONS_Dint.26)OTU(Cyc_StopRequested) ,XIC(Cyc_InCycle) ]XIO(Cyc_StopRequested)OTE(Cyc_InCycle);
```

> Cycle stop takes effect at end of part, not mid-routine.

```
[XIC(Cyc_Stop) ,XIC(Ext_DrawerFull) ,XIC(Mem_Disagree) ,XIO(Mode_Auto) XIO(Mode_Dry) ]OTL(Cyc_StopRequested);
```

> Purge - stop feeding new blanks and let everything already in the cell finish.

```
XIC(Mode_Purge)OTE(Purge_Active);
```

```
EQU(Loc_RobotBlank,0)EQU(Loc_RobotFinish,0)EQU(Loc_Nest1,0)EQU(Loc_Nest2,0)EQU(Loc_Nest3,0)EQU(Loc_Nest4,0)EQU(Loc_Mold,0)OTE(Cell_Empty);
```

> Zone occupancy. With overlap permitted everywhere, the turntable is blocked only while the robot is physically at the nest - one interlock, not a matrix.

```
XIC(Seq_CmdAccepted)[EQU(Robot_Sts_RoutineID,30) ,EQU(Robot_Sts_RoutineID,40) ]OTE(Z2_Turntable);
```

> Turntable index trigger - the sequencer owns it. Index when station 1 has been serviced and the robot is out of the zone.

```
[XIC(Cyc_InCycle)XIO(Z2_Turntable)XIC(Nest1_Serviced)XIO(Ext_TurntableMoving)ONS(Robot_Seq.ONS_Dint.27)OTL(Idx_Request) ,XIC(Ext_TurntableMoving)OTU(Idx_Request) ];
```

### `R900_Manual`

> THE COMMISSIONING TOOL. Build the faceplate and prove every routine through this before the sequencer is ever enabled. Six fields: routine ID and four params, plus fire. Four indicators: Robot_Sts_State, Robot_Sts_RoutineID, Robot_Sts_FaultCode, Robot_Sts_RetryCount.

```
[XIC(Mode_Manual) ,XIC(Mode_Dry) ]XIC(Man_Fire)EQU(Robot_Sts_State,0)XIO(Seq_CmdBusy)ONS(Robot_Seq.ONS_Dint.28)[MOV(Man_RoutineID,Seq_ReqRoutineID) ,MOV(Man_Param1,Seq_ReqParam1) MOV(Man_Param2,Seq_ReqParam2) ,MOV(Man_Param3,Seq_ReqParam3) MOV(Man_Param4,Seq_ReqParam4) ,OTL(Seq_IssueCmd) ,OTU(Man_Fire) ];
```

> Acknowledge a held complete or fault, which releases the robot back to idle.

```
[XIC(Seq_CmdDone) ,XIC(Seq_CmdFault) ]XIC(Man_Ack)ONS(Robot_Seq.ONS_Dint.29)[OTL(Seq_CmdConsume) ,OTU(Man_Ack) ];
```

---

## Rungs for `Program040000_Station100_Robot`

Add to `Routine040700_OutputActions` — PLC to robot:
```
COP(Robot_Cmd_RoutineID,Station100_Robot:O.Data[64],4)COP(Robot_Cmd_Seq,Station100_Robot:O.Data[68],4)COP(Robot_Cmd_Param1,Station100_Robot:O.Data[72],4)COP(Robot_Cmd_Param2,Station100_Robot:O.Data[76],4)COP(Robot_Cmd_Param3,Station100_Robot:O.Data[80],4)COP(Robot_Cmd_Param4,Station100_Robot:O.Data[84],4)COP(Robot_Cmd_RetryLimit,Station100_Robot:O.Data[88],4);
```

Add to `Routine040300_InputStatus` — robot to PLC:
```
COP(Station100_Robot:I.Data[64],Robot_Sts_State,4)COP(Station100_Robot:I.Data[68],Robot_Sts_RoutineID,4)COP(Station100_Robot:I.Data[72],Robot_Sts_AckSeq,4)COP(Station100_Robot:I.Data[76],Robot_Sts_FaultCode,4)COP(Station100_Robot:I.Data[80],Robot_Sts_RetryCount,4)COP(Station100_Robot:I.Data[84],Robot_Sts_SubStep,4);
```

> Byte offsets 64–91 are **assumed free and unverified** — that is task 0.4. Check the assembly
> sizes in the EtherNet/IP config before pasting these.

## Editing rules

- **Never use an array element as an array subscript.** `Part_Log[Loc_Nest[1]]` is rejected and
  renders as `??`. That is why the nest locations are scalar `Loc_Nest1..Loc_Nest4`.
- **Step 0's branches are ordered lowest priority first** — all branches evaluate, so the last true
  one wins. `Req_Reject` at the bottom is highest priority.
- **One-shot bits `Robot_Seq.ONS_Dint.0` through `.29` are each used exactly once.** A DINT has 32
  bits; take 30 and 31 next, then add a word. Sharing one between two rungs breaks both silently.
