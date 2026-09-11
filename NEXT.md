# Next — the working list

**State: `Program031000_RobotSequencer` is imported.** The PLC half of the interface exists. The
robot half does not, so nothing moves yet — that is expected and step 1 below turns it into a test.

The 100-item board is the reference. **This is the queue.** Ordered; work top to bottom.

Full list: [`TODO.md`](TODO.md) · Ladder reference: [`docs/AUTOSEQUENCE.md`](docs/AUTOSEQUENCE.md) ·
Import guide: [`plc/README.md`](plc/README.md)

---

## 1. Prove the handshake with no robot at all — 10 minutes, nothing else needed

Do this first. It verifies the entire PLC-side interface with zero dependencies.

- [ ] Confirm the program verified clean after import. If `UDT_Routine_Control` conflicted, you
      should have taken **Use Existing**.
- [ ] Delete the orphaned `Loc_Nest` array tag if the first import left one behind.
- [ ] Set `HMI_Mode_Select` = 1. Confirm `Mode_Manual` comes on (needs `Ext_EStopOK` — force it for
      this test if it isn't mapped yet).
- [ ] Put `10` in `Man_RoutineID`. Pulse `Man_Fire`.
- [ ] Watch, in order: `Robot_Cmd_RoutineID` becomes 10 · `Robot_Cmd_Seq` increments ·
      `Seq_CmdBusy` latches · `Seq_AckTimer` runs · after 3 s `Seq_CmdFault` sets and
      `Robot_Seq.Fault_Dint` reads **9001**.
- [ ] Pulse `Man_Ack`. `Robot_Cmd_RoutineID` returns to 0 and the fault clears.

Fault 9001 is the **correct** result — it means "the robot never acknowledged", and there is no
robot listening yet. If you see that whole sequence, the command path, the sequence counter, the
timeout and the consume handshake all work.

## 2. Map the `Ext_` stubs — independent of the robot

In `R999_ExternalInterface`. Until these are mapped the sequencer sits at step 0 forever.

- [ ] `Ext_EStopOK`, `Ext_Reset` — safety relay OK, HMI reset
- [ ] `Ext_TurntableMoving` ← `Weiss:I.Active` · `Ext_TurntableMoved` ← index-complete one-shot
- [ ] `Ext_MoldOpen` ← `IMMtoR_MoldOpen` · `Ext_OpEnable` ← `IMMtoR_OpEnable`
- [ ] `Ext_DrawerFull` ← `PLCtoR_DrawerFull` · `Ext_LayerShiftReq` ← `RequestLayerShift`
- [ ] `Ext_Nest1PartA/B` ← PE202 / PE203
- [ ] `Ext_FinCupAReleased/BReleased` ← NOT VG528 / NOT VG530
- [ ] `Ext_TrayPosValid`, `Ext_TrayRow`, `Ext_TrayCol` ← derived from `UpAxis_NextValidPos`
- [ ] `Ext_TurntableIndexReq` → drives `VFD_Index_REQUEST`
- [ ] Leave `Ext_MarkComplete` clear — no laser. Use `Sim_MarkAtStation3` instead.

## 3. Critical path: the robot side

- [x] **3.1 `$config.dat` pulled and read.** Everything `Main.src` references is declared. It compiles.
- [x] **3.3 SIGNAL declarations written and verified** — `robot/CONFIG_ADDITIONS.dat`, 13 signals,
      zero collisions with the live config. Paste as written.
- [x] **3.5 / 3.6 Dispatcher written** — folded into a single `robot/Main.src`. No separate
      `CmdInterface.src`, no station file touched.
- [x] **3.2 Assembly sizes confirmed — 256 bytes each way.** `Station100_Robot` is a generic
      `AB:ETHERNET_MODULE` with `SINT[256]` on both `I` and `O`. The block needs bytes 64–91; there is
      room to spare. **No Plan B needed.**
- [x] **Mapping verified on hardware.** Writing `Station100_Robot:O.Data[72] = 17` reads back as
      `Robot_Cmd_Param1 = 17` on the pendant. That confirms `bit = (byte × 8) + 1`, confirms byte 72
      is mapped on the KUKA side, and confirms the `SIGNAL` declarations are live.
- [x] **Byte order verified both directions.** `O.Data[72]`=17 → `Robot_Cmd_Param1`=17.
      `Robot_Sts_SubStep`=65536 → `I.Data[86]`=1. Little-endian, no swap, nothing to flip.
- [ ] **3.4 Add the two `COP` rungs** to `Program040000_Station100_Robot` — see the end of
      [`docs/AUTOSEQUENCE.md`](docs/AUTOSEQUENCE.md). **This is the next thing to do.** Until it
      exists, the sequencer's tags never reach the wire.
- [ ] **3.7** Install per [`robot/SETUP.md`](robot/SETUP.md): byte-order test, then the no-motion
      protocol test (command 99 → expect fault 101).

## 4. First real motion

- [ ] Fire `10 Home` from the faceplate. `Robot_Sts_State` should go 0 → 1 → 2 and **hold at 2**
      until you pulse `Man_Ack`. That is the whole design working.

## 5. Then, one routine at a time

Prove each from the faceplate before anything chains them:

**20 PickUpstacker → 30 PlaceTurntable → 40 PickTurntable → 70 DropChute → 60 SprueCut →
80 LayerShift → 90 Reject → 50 IMMExchange.**

The IMM is last — most interlocked, and the only one that can damage a mould.

## 6. Only then, auto

- [ ] Set `Sim_MarkAtStation3` so pairs can get past the nest with no laser.
- [ ] `HMI_Mode_Select` = 2, press home, then start.
- [ ] Watch `Robot_Seq.Routine_CurrentCycleStep` walk 0 → 200 → 0 → 300 → 0 → …

---

## Fix these whenever — independent of everything above

- [ ] **Layer bounds.** `UpAxis_Memory` is `SINT[12]`; rung 7 allows layer requests to 13. Indexing
      at 12 or 13 **major-faults the processor**. The answer is 11 layers.
- [ ] **Turntable good/bad.** With no vision, both `Inspect_` statuses stay 0,
      `TTtoR_ReqToPickBad` latches, and **every part goes to the reject drawer**. Swap to
      PE202 / PE203.
- [ ] **Downstacker cup A** writes `RtoDS_PickErrorVG530` in four places where it should write the
      VG528 bit, and one guard reads `If VG530 Or VG530`.
- [ ] Remove `XIC(Josh_test.26)` from the laser-fire permissive.
- [ ] Remove the `XIC(amp_Test_Bits.0)` gate from the stop path.
- [ ] Interlock or delete `Sim_MarkAtStation3` before the laser goes in — it forces every part to
      "good", which is the same species as `Josh_test.26`.

## Answer when you can

- **Is the laser hood interlock safety-rated?** Rung 13 gates the fire on hood position in the
  *standard* PLC. Settle it before there are visitors in the room.
- **Who writes the stacker tags today?** Eight are read across all nine programs and written by
  none. Almost certainly Optix.
- **Tray-count sensor** — part number and mounting.
- **MDX2 free text over EtherNet/IP** — still the biggest risk to the open house, still unproven.
