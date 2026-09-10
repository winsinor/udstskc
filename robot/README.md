# Robot side — PLC-as-master interface

The KUKA half of the interface. The PLC half is `../plc/Program031000_RobotSequencer_Program.L5X`.

| File | What it is |
|---|---|
| `CONFIG_ADDITIONS.dat` | SIGNAL declarations to paste into `$config.dat`. **Addresses are placeholders.** |
| `CmdIface.src` / `.dat` | Shared helpers every routine uses, plus the latched command snapshot |
| `Main_New.src` | The dispatcher. Replaces `Main.src`; keep the old one as `Main_Legacy.src`. |

## Install order

1. **Get `$config.dat` off the controller first.** `XHOME` and `FHOME` are declared there and
   nothing moves without them. This is task 0.1 and it blocks everything here.
2. Work out the real bit addresses (`CONFIG_ADDITIONS.dat` has the arithmetic) and paste the
   SIGNAL block in.
3. **Test byte order before anything else** — the procedure is at the bottom of
   `CONFIG_ADDITIONS.dat`. A byte swap presents as "the robot ignores my commands", not as a byte
   swap, and it will cost you an afternoon if you skip this.
4. Copy `CmdIface.src` / `.dat` to `KRC:\R1\Program`.
5. Rename the existing `Main.src` / `.dat` to `Main_Legacy.*`, then install `Main_New.src` as
   `Main.src`. **`Main.dat` is unchanged** — the dispatcher uses the same `PDEFAULT` and turn
   points the old one did.
6. Select `Main` in Ext Auto.

## What works today

**Routine 10 Home only.** Every other routine ID reports fault **199** — "not yet implemented" —
which is a clean, visible answer rather than silence. Wrap the stations one at a time, in the
proving order, replacing each `CmdReportFault(199)` with the real call.

## Wrapping a station

The existing station programs already are self-contained routines with their own error exits.
Wrapping one means giving it the standard shape:

```
CASE 20
   Rtn_PickUpstacker()
```

```
DEF Rtn_PickUpstacker()
   ; params arrive as Cmd_P1 (row) and Cmd_P2 (column) -- a latched snapshot,
   ; not the live interface words
   IF (Cmd_P1<1) OR (Cmd_P1>2) OR (Cmd_P2<1) OR (Cmd_P2>4) THEN
      CmdReportFault(204)          ; tray cell out of range
      RETURN
   ENDIF

   ... the motion, largely as Station200_UpStacker.src already has it ...

   IF <both cups verified> THEN
      ; fall through; Main reports Complete
   ELSE
      IF CmdRetryLeft() THEN
         ... try again ...
      ELSE
         CmdReportFault(201)
      ENDIF
   ENDIF
END
```

Three rules:

- **Never set `Robot_Sts_State` directly.** Use `CmdReportComplete()` / `CmdReportFault()`. They
  guard the ordering — a routine that already faulted cannot overwrite its own fault by falling
  through to the end.
- **Never move in a fault path.** Report the fault and return. `Main` retreats, once, after the
  routine has unwound, and it knows to hand the mould back first.
- **Read params from `Cmd_P1..P4`, never from `Robot_Cmd_Param1..4`.** The interface words are live
  network data and can change mid-routine.

## Two notes on the existing code

- **KRL has `RETURN`.** The existing programs use `GOTO EndOfModule` as an early return everywhere,
  which is a habit rather than a necessity. New routines should use `RETURN`.
- `CmdStopRequested()` replaces the stop-check block that appears **six times, copy-pasted**, in
  the old `Main.src`. A routine calls it at a safe point and faults with 103.
