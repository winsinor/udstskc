# TODO — PLC-as-Master Rework

Design and decisions: [`docs/PLC_MASTER_PLAN.md`](docs/PLC_MASTER_PLAN.md)
Part memory spec: [`docs/PART_MEMORY.md`](docs/PART_MEMORY.md)
Code reading guide: published artifact — "Reading the Cell Robot Code"

**Context: this is a demo cell for an open house 4–8 weeks out.** A visitor types a name at a
kiosk, the laser engraves it, the blank is insert-moulded, and they pick their part out of the
chute by reading their own name off it.

Legend: `[ ]` open · `[~]` in progress · `[x]` done · **⛔** blocked on something above

---

## Phase 0 — Ground truth (blocking everything else)

- [ ] **0.1** Retrieve `$config.dat` from the KRC and commit it. Every KRL global is declared and
      bound to an I/O address there; without it no signal can be added or verified.
- [ ] **0.2** Retrieve the rest of `KRC:\R1\` (`$machine.dat`, `TOOL_DATA` / `BASE_DATA` /
      `LOAD_DATA`, `$custom.dat`) and commit. Tools 1–4 and Bases 1–6 are referenced but undefined here.
- [ ] **0.3** Build the signal map: every KRL global ↔ robot I/O byte/bit ↔ PLC tag. One table.
- [ ] **0.4** Verify free space in the `Station100_Robot` I/O assemblies. The ICD assumes bytes
      64–91 are free in both directions.
- [ ] **0.5** Export the Optix tag list and determine exactly which robot-facing tags it writes.
      Eight of them are read across all nine PLC programs and written by none.
- [ ] **0.6** Physical I/O inventory — installed vs. tree-only: IV3, Cognex IS3800, PE202, PE203,
      PE307, PRX315, VG524/526/528/530.
- [ ] **0.7** Confirm the EuroMap 67 link to the molder is live.
- [ ] **0.8** **Get the MDX2 manual and prove one string end to end.** The current connection is
      discrete bits only — zero STRING tags and zero MSG instructions exist in the whole project.
      *This is the single biggest schedule risk to the open house.* Nothing in Phase 9 should be
      built until a string has actually reached the marker.
- [ ] **0.9** Specify the new tray-count sensor — part number, mounting, and whether it counts trays
      or measures stack height. Phase 10 can't be finished without it.
- [ ] **0.10** Confirm the controller type and memory headroom. `Part_Log[500]` is ~32 KB, which is
      modest, but the processor isn't identified in these exports.

## Phase 1 — Interface definition (paper, no code)

- [ ] **1.1** ⛔0.4 — Finalise the word layout against real assembly sizes.
- [ ] **1.2** Review the 9-routine map against the physical sequence. Can `PlaceTurntable` and
      `PickTurntable` ever be one visit?
- [ ] **1.3** Confirm the fault code list covers every failure the station programs already detect.
- [ ] **1.4** Define the zone occupancy model concretely — which robot positions map to which zone.

## Phase 2 — Robot side

- [ ] **2.1** ⛔0.1 — Declare the new command/status signals in `$config.dat`.
- [ ] **2.2** New `CmdInterface.src`: decode the command word, publish held status. Helpers
      `CmdLatch()`, `ReportRunning()`, `ReportComplete()`, `ReportFault(code)`.
- [ ] **2.3** Extract `CheckForStop()` from the six copy-pasted blocks in `Main.src`.
- [ ] **2.4** Rewrite `Main.src` as a dispatcher on `Robot_Cmd_RoutineID`. Keep the current file as
      `Main_Legacy.src` until Phase 3 proves each station.
- [ ] **2.5** Give every station routine the standard prologue/epilogue.
- [ ] **2.6** Fault handling: retreat to `XHOME`, hold, set the fault code.
- [ ] **2.7** Retry framework: honour `Robot_Cmd_RetryLimit`, publish `Robot_Sts_RetryCount`.
- [ ] **2.8** Idempotent `10 Home` routine; delete the dead `RobotInitialHoming` flag.

### Phase 2b — Robot-side bug fixes (independent, do any time)

- [ ] **2.9** `Station600_DownStacker.src` — cup A faults write `RtoDS_PickErrorVG530` instead of
      the VG528 bit, in four places, and the guard reads `If VG530 Or VG530`.
- [ ] **2.10** `Station300_LaserMarker.src` — pick timeout branch copies `UStoR_PickSeqNumber`
      where it should be `TTtoR_PickSeqNumber`.
- [ ] **2.11** `Main.src` — the `DStoR_PickFromTray` branch is unreachable. Understand it, then it
      goes with 2.13.
- [ ] **2.12** Delete the empty `If … Then / EndIf` shells (Station 300 line 349, Station 400).
- [ ] **2.13** Strip the downstacker tray grid. Chute-always makes `DS_Pick` / `DS_Place` and both
      tray branches of Station 600 dead.
- [ ] **2.14** Move the ~450 dead lines after `GOTO EndOfModule` in `PickPlaceTrayTeach.src` into
      their own commissioning program. Contains a wrong-point copy-paste error.
- [ ] **2.15** Stop every hand-rolled timeout sharing `$TIMER[2]`, including across nested calls.

## Phase 3 — PLC commanding, one station at a time

- [ ] **3.1** ⛔1.1 — Add the command/status words to `Routine040300_InputStatus` and
      `Routine040700_OutputActions`, alongside the existing `COP` instructions.
- [ ] **3.2** Build a `Robot_Command` AOI: issue, increment `Cmd_Seq`, wait for ack, latch
      complete/faulted, time out on Running.
- [ ] **3.3** Manual command faceplate on the HMI. **The commissioning tool — build it first.**
- [ ] **3.4** Prove `20 PickUpstacker`.
- [ ] **3.5** Prove `30 PlaceTurntable`.
- [ ] **3.6** Prove `40 PickTurntable`.
- [ ] **3.7** Prove `70 DropChute`.
- [ ] **3.8** Prove `60 SprueCut`.
- [ ] **3.9** Prove `80 LayerShift`.
- [ ] **3.10** Prove `90 Reject`, all three selectors.
- [ ] **3.11** Prove `50 IMMExchange`. **Last** — most interlocked, only one that can damage a mould.

## Phase 4 — Auto-sequence framework

- [ ] **4.1** Rewrite `Routine030600_RobotAutoSequence` against the new command set. Its four
      command bits are read by nothing and never reach the robot's output words.
- [ ] **4.2** Write the missing step handlers. Step 0 dispatches to step `1000`, which has no
      handler rung at all — reaching it hangs the sequencer permanently.
- [ ] **4.3** Wire the request bits that drive step 0. Nothing writes any of them, so the sequencer
      can never leave step 0.
- [ ] **4.4** Cycle state machine: Idle / InCycle / Holding / Faulted, cycle stop at end of part.
- [ ] **4.5** ⛔1.4 — Zone occupancy interlocks so overlap is safe. Derive the mould zone from
      `RtoIMM_MoldAreaFree` rather than tracking it separately.
- [ ] **4.6** Finish the two rungs `Routine030200_Mode_Control` flags in its own comments.

## Phase 5 — Part memory

Full spec in [`docs/PART_MEMORY.md`](docs/PART_MEMORY.md).

- [ ] **5.1** Define the UDTs: `STRING_20`, `Part_Record` (present/good/bad + name),
      `Part_Pair` (seq, state, `.A`, `.B`).
- [ ] **5.2** Create `Part_Log[500]` and `Part_Seq_Next`. Non-retentive; cleared on first scan,
      sequence wraps 1–500.
- [ ] **5.3** Create the location tags: `Loc_RobotBlank`, `Loc_RobotFinish`, `Loc_Nest[5]`,
      `Loc_Mold`, `Loc_Delivered`. Each holds a sequence number only, `0` = empty.
- [ ] **5.4** Port the turntable shift from whole-record COPs to four DINT moves on `Loc_Nest`.
      There are **four** stations — `TurnTable[0]` is a scratch buffer, not a fifth.
- [ ] **5.5** Retire `Data_Item`, `Data_Item_Initialize`, `TurnTable[5]`, `Part_Data`,
      `Index_Table_Part_Data`, `Robot_Blank_Side_Part_Data`, `Robot_Finished_Side_Part_Data`.
- [ ] **5.6** Sequence allocation and lifecycle transitions on every routine completion
      (0 → 10 → 20 → 30 → 40 → 50 → 60 → 70 → 80 → 90, or 900).
- [ ] **5.7** Move the robot tool-state flags into `Part_Log`. `RtoPLC_ToolBlnkHasParts`,
      `ToolBlnkMrked`, `ToolFinHasParts` and the KRL sequence numbers stop being the truth.
      `RtoIMM_SeqNumber` — one number for a 2-up shot — is replaced by `Loc_Mold`.
- [ ] **5.8** Sensor corroboration at every location that has one (PE202/PE203, VG524/526/528/530).
      **On disagreement: hold, and alarm naming the location and the direction of the error.**
- [ ] **5.9** Delivery confirmation — state 90 only when both finished-side vacuum switches confirm
      release. There is no chute sensor.
- [ ] **5.10** Auto-purge on start: reject anything on either gripper, cycle the turntable until all
      four nests read empty, confirm the mould is clear. The mould has no sensor, so it is the one
      location the operator must vouch for.
- [ ] **5.11** ⛔0.5 — Remove Optix writes. Optix becomes submit-and-display only.

## Phase 6 — Turntable without vision

- [ ] **6.1** Replace the `Inspect_1_Status` / `Inspect_2_Status` gating in rung 22 with PE202 /
      PE203 part-present. **As written, with no vision reporting a pass, both statuses stay 0,
      `TTtoR_ReqToPickBad` latches, and every part goes to the reject drawer.**
- [ ] **6.2** Remove or bypass the IV3 trigger sequence (rungs 17–20) and the Cognex trigger.
- [ ] **6.3** Remove `XIC(Josh_test.26)` from the laser-fire permissive (rung 12).
- [ ] **6.4** Keep inspection fields in the part record for a future vision system.

## Phase 7 — Alarms

- [ ] **7.1** Replace the 468 `PlaceHolderBit` conditions with real ones. The warning arrays, delay
      timers and reset handling are all already built.
- [ ] **7.2** Map robot fault codes onto PLC alarms with derived text.
- [ ] **7.3** Vacuum cup alarms — VG524, VG526, VG528, VG530. Already detected, currently handled by
      silently dumping parts in the drawer.
- [ ] **7.4** IMM alarms — the four `PlaceError` bits, declared and read by the robot, written by
      nothing.
- [ ] **7.5** Drawer full (`PE307`) → warning, then cycle stop at end of part.
- [ ] **7.6** Robot command timeout, comms loss, and part-memory disagreement alarms.

## Phase 8 — Hygiene

- [ ] **8.1** Remove the `XIC(amp_Test_Bits.0)` gate from `Routine030300_InputStatus` rung 0. Door
      unlock, door open permission, `PLCtoR_Stop` and `StartRobotCycle` all hang off one test bit.
- [ ] **8.2** Replace the `Optix_AlwaysDropInShootTimer` hack with an explicit chute-always mode.
- [ ] **8.3** Decide `Station500_DrawerMove` — empty body, called from two places, caller then
      blocks on `Wait For PLCtoR_DrawerInPos`.
- [ ] **8.4** Decide whether `CollDetect_UserAction` being empty is intended.
- [ ] **8.5** Replace the `Rjct_1Blnk_2Fin_3Both` magic numbers with named constants.
- [ ] **8.6** Keep the design docs current as implementation changes things.

## Phase 9 — Naming, kiosk and laser text

- [ ] **9.1** ⛔0.8 — Expand the MDX2 EtherNet/IP connection to carry text.
- [ ] **9.2** Build the string write path — two independent text fields per fire.
- [ ] **9.3** `Name_Queue` ring buffer (`STRING_20[20]`) with head, tail and count, owned by the PLC.
- [ ] **9.4** Optix kiosk screen. **Submit only** — it writes into the queue and commands nothing.
- [ ] **9.5** Character restrictions and length clamp at 20 in the kiosk.
- [ ] **9.6** Operator can cancel or edit a pending queue entry.
- [ ] **9.7** Name attach **at the laser, immediately before firing** — not at the pick. Up to two
      names pulled per fire; a field with no name takes the logo. A pair scrapped before the laser
      costs no one their name.
- [ ] **9.8** On scrap of a named pair, push the name back to the **head** of the queue so that
      visitor is served next rather than going to the back of the line.

## Phase 10 — Tray replenishment and cell entry

- [ ] **10.1** **Fix the layer bounds.** `UpAxis_Memory` is `SINT[12]`, `UpAxis_Positions` is
      `DINT[14]`, rung 7 limits to 1–13, rung 8 increments below 13, rung 9 clamps at ≥11.
      Indexing memory at layer 12 or 13 is **out of range and will major-fault the processor.**
      The answer is 11 layers; derive all four from one constant.
- [ ] **10.2** ⛔0.9 — Wire the tray-count sensor. Sensor is authoritative.
- [ ] **10.3** Fill loop in `R201_Data_Fill_Loop` — mark each newly added layer all-eight-present.
      The routine exists, is called by a `FOR`, and is empty; the `FOR` indexing needs rethinking to
      be driven by the sensor count.
- [ ] **10.4** Clear loop in `R202_Data_Clear_Loop` — same situation.
- [ ] **10.5** Preserve the partly-used tray's map across a reload. Memory follows the tray and
      tracks its current position. **Expand the existing logic; do not rewrite it.**
- [ ] **10.6** Operator tray-count confirmation with a warning on mismatch — sensor still wins.
- [ ] **10.7** Downstacker empty-tray counter and full detection. It has 52 tags and not one is
      tray-related; a counter is all it needs now that parts go down the chute.
- [ ] **10.8** Request-to-enter button: full stop → robot home → stackers and turntable stopped →
      unlock. Build on the existing `Door_Open_Request` / `Door_Open_Permission` / `Unlock_Doors`
      logic rather than adding a parallel path.

## Phase 11 — Operating modes

- [ ] **11.1** Mode selection: Auto, Manual (single routine), Dry cycle, Purge.
- [ ] **11.2** Dry cycle — motion with vacuum and grippers inhibited, IMM leg included or excluded
      by operator choice per run.
- [ ] **11.3** Purge — stop feeding new blanks, finish everything in the turntable and the mould,
      stop clean. `Station_Purge_Mode` and `Stations_Data_Empty` already exist and are unused.
- [ ] **11.4** Startup: operator presses home, then start. Nothing moves unasked.
- [ ] **11.5** Resume after a stop **with parts still on the tool** — the cell keeps them and
      carries on rather than dumping to the drawer.

---

## Quick wins — independent of the rework

Safe to do now, in any order, each pays for itself whether or not the rework proceeds.

- [ ] **10.1** Layer-bounds fix *(will major-fault the processor as written)*
- [ ] **6.1** Turntable good/bad without vision *(would otherwise reject 100% of parts)*
- [ ] **2.9** Downstacker cup A/B error bits *(a diagnostic you think you have)*
- [ ] **7.3** Vacuum cup alarms *(highest-value hour on the list)*
- [ ] **8.1** Remove the test-bit gate from the stop path
- [ ] **6.3** Remove `Josh_test.26` from the laser permissive
- [ ] **2.3** Extract `CheckForStop()`
- [ ] **2.10** Turntable sequence number fix
