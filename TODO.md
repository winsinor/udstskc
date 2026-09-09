# TODO — PLC-as-Master Rework

Design and decisions: [`docs/PLC_MASTER_PLAN.md`](docs/PLC_MASTER_PLAN.md)
Code reading guide: published artifact — "Reading the Cell Robot Code"

Legend: `[ ]` open · `[~]` in progress · `[x]` done · **⛔** blocked on something above

---

## Phase 0 — Ground truth (blocking everything else)

- [ ] **0.1** Retrieve `$config.dat` from the KRC and commit it. Every KRL global in these programs
      is declared there; without it no signal can be added or verified.
- [ ] **0.2** Retrieve the rest of `KRC:\R1\` (`$machine.dat`, `TOOL_DATA` / `BASE_DATA` /
      `LOAD_DATA`, `$custom.dat`) and commit. Tool 1–4 and Base 1–6 are referenced but undefined here.
- [ ] **0.3** Build the signal map: every KRL global ↔ robot I/O byte/bit ↔ PLC tag. One table,
      committed. This is the artefact everything else is checked against.
- [ ] **0.4** Verify free space in the `Station100_Robot` I/O assemblies. The ICD assumes bytes
      64–91 are free in both directions — confirm the connection sizes in the EtherNet/IP config.
- [ ] **0.5** Export the Optix tag list and determine exactly which robot-facing tags it writes.
      Expected: `UStoR_PickRowNumber`, `UStoR_PickColumnNumber`, `UStoR_PickSeqNumber`,
      `UStoR_ReqToPick`, `UStoR_ReqToMoveLayer`, `DStoR_PickRowNumber`, `DStoR_PickColumnNumber`,
      `DStoR_OpenLocation`. Nothing in the PLC writes any of them.
- [ ] **0.6** Physical I/O inventory: confirm installed vs. tree-only for IV3, Cognex IS3800,
      PE202, PE203, PE307, PRX315, VG524/526/528/530.
- [ ] **0.7** Confirm the EuroMap 67 connection to the molder is live and the EM67/EM78 signals in
      `Routine040700_OutputActions` are real.

## Phase 1 — Interface definition (paper, no code)

- [ ] **1.1** ⛔0.4 — Finalise the word layout in `docs/PLC_MASTER_PLAN.md` §4.1 against real
      assembly sizes.
- [ ] **1.2** Review the 9-routine map (§3) against the physical sequence. Confirm nothing is
      missing — in particular whether `PlaceTurntable` and `PickTurntable` can ever be one visit.
- [ ] **1.3** Confirm the fault code list (§4.3) covers every failure the station programs already
      detect. Add codes for anything found.
- [ ] **1.4** Define the zone occupancy model (§5) concretely: which robot positions map to which
      zone, and how the robot publishes it.

## Phase 2 — Robot side

- [ ] **2.1** ⛔0.1 — Declare the new command/status signals in `$config.dat`.
- [ ] **2.2** New `CmdInterface.src` / `.dat`: decode the command word, publish held status.
      Helpers: `CmdLatch()`, `ReportRunning()`, `ReportComplete()`, `ReportFault(code)`.
- [ ] **2.3** Extract `CheckForStop()` from the six copy-pasted blocks in `Main.src`. Mechanical,
      zero behaviour change, makes the rest of the work readable.
- [ ] **2.4** Rewrite `Main.src` as a dispatcher on `Robot_Cmd_RoutineID`. Keep the current file as
      `Main_Legacy.src` until Phase 3 proves each station.
- [ ] **2.5** Give every station routine the standard prologue/epilogue: latch params, report
      running, report complete or fault. One station at a time, in the order in §6 of the plan.
- [ ] **2.6** Fault handling: on any station error, retreat to `XHOME`, hold, set the fault code.
      Replaces the current "dump both tool halves into the drawer and re-home" recovery.
- [ ] **2.7** Retry framework: honour `Robot_Cmd_RetryLimit`, publish `Robot_Sts_RetryCount`.
      Canonical case is the vacuum-verify helper — grip, check VG sensors, retry, then fault.
- [ ] **2.8** Add a routine `10 Home` that is genuinely idempotent, and delete the dead
      `RobotInitialHoming` flag (set False at `BeginningOfModule`, never set True anywhere).

### Phase 2b — Robot-side bug fixes (independent, do any time)

- [ ] **2.9** `Station600_DownStacker.src` — cup A faults write `RtoDS_PickErrorVG530` instead of
      the VG528 bit, in four places, and the guard reads `If VG530 Or VG530`. A cup-A-only failure
      is reported as cup B and the two-cup check isn't checking two cups.
- [ ] **2.10** `Station300_LaserMarker.src` — the pick timeout branch copies
      `UStoR_PickSeqNumber` into `RtoPLC_ToolBlnkSeqNumber`; should be `TTtoR_PickSeqNumber`.
      Copy-paste from Station 200. Breaks traceability on exactly the parts that errored.
- [ ] **2.11** `Main.src` — the `DStoR_PickFromTray` branch is unreachable: the outer condition
      requires `RtoPLC_ToolFinHasParts == True` and the first statement inside jumps out if it is
      True. Removed by the downstacker work (2.13) but worth understanding first.
- [ ] **2.12** Delete the empty `If ... Then / EndIf` shells (`Station300` line 349, `Station400`).
      They read as unfinished work and stop reviewers.
- [ ] **2.13** Strip the downstacker tray grid. Chute-always means `DS_Pick` / `DS_Place`,
      `DS_PickApproach*` and the tray branches of `Station600` are dead. Downstacker keeps only
      empty-tray stacking.
- [ ] **2.14** Move the ~450 dead lines after `GOTO EndOfModule` in `PickPlaceTrayTeach.src` into
      their own commissioning program. It contains at least one copy-paste error
      (`US_Pick[1,2] = XUS_TeachPick`, wrong point) that would crash the tool into the tray if the
      `GOTO` were ever removed.
- [ ] **2.15** Decide the fate of `$TIMER[2]` sharing. Every hand-rolled timeout in the codebase
      uses the same timer, including across nested calls (`Station400` → `Station500_Reject`).
      It works by accident. Give nested routines their own index.

## Phase 3 — PLC side, per-station commanding

- [ ] **3.1** ⛔1.1 — Add the new command/status words to `Routine040300_InputStatus` and
      `Routine040700_OutputActions` alongside the existing `COP` instructions.
- [ ] **3.2** Build a `Robot_Command` AOI: issue command, increment `Cmd_Seq`, wait for ack, latch
      complete/faulted, time out on `Running`. One object every caller uses.
- [ ] **3.3** Manual command faceplate on the HMI: choose routine ID, enter params, fire, watch
      status and fault code. **This is the commissioning tool** — build it before proving anything.
- [ ] **3.4** Prove routine `20 PickUpstacker` end to end from the faceplate.
- [ ] **3.5** Prove `30 PlaceTurntable`.
- [ ] **3.6** Prove `40 PickTurntable`.
- [ ] **3.7** Prove `70 DropChute`.
- [ ] **3.8** Prove `60 SprueCut`.
- [ ] **3.9** Prove `80 LayerShift`.
- [ ] **3.10** Prove `90 Reject` (all three `Param1` selectors).
- [ ] **3.11** Prove `50 IMMExchange`. **Last** — most interlocked, and the only routine that can
      damage a mold.

## Phase 4 — PLC auto-sequence framework

- [ ] **4.1** Rewrite `Routine030600_RobotAutoSequence` against the new command set. The skeleton
      is already right — decision step 0, action steps, explicit return to 0 — but it is inert:
      none of its five request bits is ever written, none of its four command bits is ever read.
- [ ] **4.2** Write the missing step handlers. Step 0 currently dispatches to step `1000` with no
      handler rung at all — reaching it hangs the sequencer permanently.
- [ ] **4.3** Wire the request bits that drive step 0: `IndexTable_New_Part_Requested`,
      `Robot_Good_Part_Unload_Request`, `IMM_Load_Request`, `Tray_Transfer_Request`. Nothing
      writes any of them today.
- [ ] **4.4** Cycle state machine: Idle / InCycle / Holding / Faulted, with cycle-stop taking
      effect at end of part. Extend what `Routine030200_Mode_Control` already has.
- [ ] **4.5** ⛔1.4 — Zone occupancy interlocks so overlap is safe. Derive Z3 from
      `RtoIMM_MoldAreaFree` rather than tracking it separately.
- [ ] **4.6** Finish the two rungs `Routine030200_Mode_Control` flags as incomplete in its own
      comments (`System_At_Home`, and the E-stop rung marked "NEEDS FINISHED").

## Phase 5 — Data ownership and part genealogy

- [ ] **5.1** PLC assigns sequence numbers, two per pick (2-up tooling). Robot stops inventing them.
- [ ] **5.2** Extend the `Data_Item` model — already working well for the turntable — to cover the
      two tool halves, so the robot becomes stateless.
- [ ] **5.3** Move `RtoPLC_ToolBlnkHasParts`, `ToolBlnkMrked`, `ToolFinHasParts` from KRL globals
      into PLC-owned state. Robot reports, PLC decides.
- [ ] **5.4** Drive `UStoR_PickRowNumber` / `ColumnNumber` from `UpAxis_NextValidPos`, which
      `R200_Tray_Positions_and_Data` already computes correctly and sends nowhere.
- [ ] **5.5** Wire `RobotPickStart` / `RobotPickComplete` — the newer stacker interface in
      `R200_Tray_Positions_and_Data` is gated on them and nothing writes either.
- [ ] **5.6** Trigger `80 LayerShift` from `RequestLayerShift` (already computed correctly in
      `R200` rung 2 — all eight positions in a layer consumed).
- [ ] **5.7** Genealogy readout: sequence number, tray origin cell, mark result, outcome per part.
- [ ] **5.8** ⛔0.5 — Remove Optix writes. Optix becomes read-only.

## Phase 6 — Turntable without vision

- [ ] **6.1** Replace the `Inspect_1_Status` / `Inspect_2_Status` gating in
      `Routine060500_Operation` rung 22 with PE202 / PE203 part-present from rung 9.
      **As written, with no vision reporting a pass, both statuses stay 0, `TTtoR_ReqToPickBad`
      latches, and every part goes to the reject drawer.** This alone would stop the cell.
- [ ] **6.2** Remove or bypass the IV3 trigger sequence (rungs 17–20) and the Cognex trigger.
- [ ] **6.3** Remove `XIC(Josh_test.26)` from the laser-fire permissive (rung 12). A commissioning
      toggle in the laser path.
- [ ] **6.4** Keep the `Data_Item` inspection fields for genealogy even though nothing writes them
      now — cheap, and vision may come later.

## Phase 7 — Alarms

- [ ] **7.1** Replace the `PlaceHolderBit` conditions with real ones. There are 468 of them across
      five programs; the warning arrays, delay timers and reset handling are all already built.
- [ ] **7.2** Map robot fault codes (§4.3) onto PLC alarms with derived text.
- [ ] **7.3** Vacuum cup alarms: VG524, VG526, VG528, VG530 — every one of these is already
      detected and currently handled by silently dumping parts in the reject drawer.
- [ ] **7.4** IMM alarms: `IMMtoR_PlaceErrorEjBck`, `PlaceErrorEjFrw`, `PlaceErrorMoldOpn`,
      `PreEntrErrorEjBck`. All four are declared and read by the robot; none is written by the PLC.
- [ ] **7.5** Drawer full (`PE307`) → warning, then cycle stop at end of part. Drawer stays manual.
- [ ] **7.6** Robot command timeout and comms-loss alarms.

## Phase 8 — Hygiene

- [ ] **8.1** Remove the `XIC(amp_Test_Bits.0)` gate from `Routine030300_InputStatus` rung 0.
      Door unlock, door open permission, `PLCtoR_Stop` and `StartRobotCycle` are all conditioned on
      a test bit.
- [ ] **8.2** Replace the `Optix_AlwaysDropInShootTimer` hack in `PC_to_PLC` rung 4 with an
      explicit chute-always mode.
- [ ] **8.3** Decide `Station500_DrawerMove` — it is called from two places and has an empty body,
      and the caller then blocks on `Wait For PLCtoR_DrawerInPos`. Either implement it or remove
      the call and document the drawer as manual.
- [ ] **8.4** `CollDetect_UserAction` is also empty — collision detection currently takes no
      application-level action. Decide whether that is intended.
- [ ] **8.5** Replace the `Rjct_1Blnk_2Fin_3Both` magic numbers with named constants.
- [ ] **8.6** Update `docs/PLC_MASTER_PLAN.md` with anything that changed during implementation.

---

## Quick wins — independent of the rework

Safe to do now, in any order, and each one pays for itself whether or not the rework proceeds.

- [ ] **2.9** Downstacker cup A/B error bits *(correctness — a diagnostic you think you have)*
- [ ] **6.1** Turntable good/bad without vision *(would otherwise reject 100% of parts)*
- [ ] **7.3** Vacuum cup alarms *(highest-value hour on the list)*
- [ ] **8.1** Remove the test-bit gate from the stop path
- [ ] **6.3** Remove `Josh_test.26` from the laser permissive
- [ ] **2.3** Extract `CheckForStop()`
- [ ] **2.10** Turntable sequence number fix
