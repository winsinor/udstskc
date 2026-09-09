# Next — the working list

The 100-item board is the reference. **This is the queue.** Ordered; work top to bottom.

Full list: [`TODO.md`](TODO.md) · Framework to build from: [`docs/AUTOSEQUENCE.md`](docs/AUTOSEQUENCE.md)

---

## This week

### Unblock, in parallel with everything else

- [ ] **Get `$config.dat` off the KRC.** Blocks all robot-side work. Ten minutes at the pendant.
- [ ] **Prove one string reaches the MDX2.** Biggest schedule risk to the open house, and it is an
      assumption right now — the PLC has zero STRING tags and zero MSG instructions. If the marker
      won't take free text over EtherNet/IP, the naming feature needs a different plan and you want
      to know in week 1, not week 5.
- [ ] **Check assembly sizes** on the `Station100_Robot` connection. The interface assumes bytes
      64–91 are free both ways.

### Build the framework

- [ ] **1. Create the three UDTs** — `STRING_20`, `Part_Record`, `Part_Pair`. §1 of AUTOSEQUENCE.
- [ ] **2. Create the tags.** §2.
- [ ] **3. `R100_CommandInterface`.** §4. Eight rungs. This is the piece everything else stands on —
      held completion instead of a 150 ms pulse.
- [ ] **4. `R900_Manual`.** §9. Two rungs plus a faceplate. **Build this before the sequencer** —
      it is how every routine gets proven.
- [ ] **5. Add the two `COP` rungs** to `Program040000`. §10.

At this point you can command the robot by hand and watch it answer, with no sequencer involved.
That is the milestone worth hitting first.

### Fix while you're in there

Independent of everything above, and each one is minutes:

- [ ] **Layer bounds.** `UpAxis_Memory` is `SINT[12]`; rung 7 allows layer requests to 13.
      Indexing at 12 or 13 **major-faults the processor**. Answer is 11 layers.
- [ ] **Turntable good/bad.** With no vision, both `Inspect_` statuses stay 0, `TTtoR_ReqToPickBad`
      latches, and **every part goes to the reject drawer**. Swap to PE202 / PE203.
- [ ] **Downstacker cup A** writes `RtoDS_PickErrorVG530` in four places where it should write the
      VG528 bit, and one guard reads `If VG530 Or VG530`.

---

## Next week

- [ ] **6. `R200_Requests`.** §6. Seven rungs.
- [ ] **7. `R400_PartMemory`.** §7. The lifecycle transitions.
- [ ] **8. `R300_Sequencer`.** §5. Step machine.
- [ ] **9. `R500_Modes`.** §8. Cycle control, zones, index trigger.
- [ ] **10. Robot side:** `CmdInterface.src`, then `Main.src` as a dispatcher. Keep the old file as
      `Main_Legacy.src`.

- [ ] Prove the routines one at a time from the faceplate, in this order:
      **20 PickUpstacker → 30 PlaceTurntable → 40 PickTurntable → 70 DropChute → 60 SprueCut →
      80 LayerShift → 90 Reject → 50 IMMExchange.**
      The IMM is last — most interlocked, and the only one that can damage a mould.

---

## Before the open house, not before the framework

- Naming: queue, kiosk, string path to the laser (Phase 9)
- Tray replenishment and request-to-enter (Phase 10)
- Alarms (Phase 7) — start with the vacuum cups; they are already detected and currently handled by
  silently dumping parts in the drawer
- Dry cycle and purge modes (Phase 11)

---

## Answer when you can

Not blocking today, but they need resolving:

- **Is the laser hood interlock safety-rated?** Rung 13 gates the fire on hood position in the
  *standard* PLC. Either something independent stops it firing with the hood up, or that rung is
  the only thing that does. Worth settling before there are visitors in the room.
- **Who writes the stacker tags today?** Eight are read across all nine programs and written by
  none. Almost certainly Optix.
- **Tray-count sensor** — part number and mounting.
