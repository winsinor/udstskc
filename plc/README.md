# `Program031000_RobotSequencer_Program.L5X`

The PLC-as-master robot sequencer as a **single importable program**. Self-contained: it imports
with no unresolved references and no module dependencies.

## Import

Studio 5000 → right-click **Tasks → MainTask** (or wherever it belongs) → **Add → Import Program**
→ pick the file.

It brings its own `Part_Pair` UDT and its own copy of `UDT_Routine_Control`. If
`UDT_Routine_Control` already exists in the project, Logix matches it by name — the definition here
mirrors the existing one member for member, so it should collide cleanly.

## What's inside

| Routine | Rungs | What it does |
|---|---:|---|
| `R000_Main` | 7 | JSRs |
| `R999_ExternalInterface` | 6 | **Map the `Ext_` stubs here.** Mostly NOPs with comments naming what wires to what. |
| `R100_CommandInterface` | 9 | The handshake. Issue on idle, latch accepted/done/faulted, two timeouts, consume. |
| `R200_Requests` | 8 | What makes step 0 dispatch |
| `R300_Sequencer` | 12 | Step 0 decision plus nine action steps and a fault hold |
| `R400_PartMemory` | 14 | Lifecycle transitions, nest rotation, sensor corroboration |
| `R500_Modes` | 8 | Mode select, home, cycle, purge, zone, index trigger |
| `R900_Manual` | 2 | The commissioning faceplate |

Sequencer state lives in `Robot_Seq`, a `UDT_Routine_Control` — the same shape as every other
station, and the same one the inert `Robot_Auto` uses. **`Robot_Auto` and
`Routine030600_RobotAutoSequence` can be deleted once this runs.**

## Before you download

1. **Set four timer presets.** They export as `?`:
   - `Seq_AckTimer` — 3000 ms (robot never acknowledged)
   - `Seq_RunTimer` — 120000 ms (accepted but never finished; raise if `IMMExchange` runs longer)
   - `Seq_CycleTimer` — 600000 ms (free-runs; it only measures)
   - `Mem_Disagree_TMR[1]` and `[2]` — 1000 ms (debounce, so a part in transit doesn't trip it)

2. **Map the `Ext_` stubs** in `R999_ExternalInterface`. Until then the sequencer will sit at step 0.

3. **Add the two `COP` rungs** to `Program040000_Station100_Robot` — see §10 of
   [`../docs/AUTOSEQUENCE.md`](../docs/AUTOSEQUENCE.md). Byte offsets 64–91 are **assumed free and
   unverified**; check the assembly sizes first.

4. **Nothing moves until the robot side exists.** This half is complete and will run, but it is
   commanding a robot that does not yet speak the protocol — `Robot_Sts_State` stays 0 and every
   command times out at `Seq_AckTimer` with fault 9001. That is the correct behaviour, and it is a
   useful first test.

## Commissioning it

Set `HMI_Mode_Select` = 1 (manual), then drive `R900_Manual`: put a routine number in
`Man_RoutineID`, params in `Man_Param1..4`, pulse `Man_Fire`, watch `Robot_Sts_State` and
`Robot_Sts_FaultCode`, pulse `Man_Ack` to clear. Prove every routine this way before setting
`HMI_Mode_Select` = 2.

`Sim_MarkAtStation3` is a commissioning aid: with no laser wired, it advances a pair from state 30
to 40 when it reaches nest station 3, so the whole loop can be exercised. **Clear it before the
marker goes in.**

## Two things to read before editing

- **Step 0's branches are ordered lowest priority first.** All branches evaluate, so the *last true
  branch wins*. `Req_Reject` at the bottom is the highest priority. Reordering them changes the
  cell's priority order.
- **One-shot bits are `Robot_Seq.ONS_Dint.0` through `.29`, each used exactly once.** A DINT has 32
  bits. If you add rungs, take 30 and 31, then add another word — sharing a one-shot bit between
  two rungs breaks both silently.
