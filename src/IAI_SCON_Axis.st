(* =====================================================================
   IAI_SCON_Axis  --  driver for one IAI SCON actuator
                      (EtherNet/IP, direct numerical specification mode)

   One instance per actuator.  The calling program copies the module
   image in and out around this call:

       CPS( IAI_UpStacker:I , UpStack_Inputs , 1 )
       IAI_SCON_Axis( UpStack_Axis , UpStack_Inputs , UpStack_Outputs )
       CPS( UpStack_Outputs , IAI_UpStacker:O , 1 )

   Everything else is done through the backing tag, e.g.
       UpStack_Axis.Set_Position := 12500 ;
       UpStack_Axis.Cmd_MoveAbs  := 1 ;    -- rising edge is the "go"
       ... then wait for ...
       UpStack_Axis.Sts_InPosition         -- arrival confirmed

   UNITS -- native SCON units throughout:
       position   0.01 mm      (12500 = 125.00 mm)
       speed      0.01 mm/s    (10000 = 100.00 mm/s)
       accel/dec  0.01 G       (   30 =   0.30 G)
       timeout    ms

   THE ONE MOVE COMMAND
       Load Set_Position, then give Cmd_MoveAbs a rising edge.
       The instruction range-checks the target, loads the drive,
       pulses DSTR, and holds Sts_Busy until the drive reports
       PEND (position complete).  Sts_InPosition is the confirmation.
       Nothing else starts a positioning move.

   ===================================================================== *)


(* ---------------------------------------------------------------------
   1.  Status mirror  --  everything the HMI and the calling program read
   --------------------------------------------------------------------- *)
Sts_Position    := Drv_In.Actual_Position;
Sts_Speed       := Drv_In.Actual_Speed;
Sts_AlarmCode   := Drv_In.Alarm_Code;
Sts_ServoOn     := Drv_In.Servo_is_On;
Sts_Homed       := Drv_In.Home_Complete;
Sts_Fault_Drive := Drv_In.Alarm_Active;
Sts_EStop       := Drv_In.E_Stop_Active;

(* Sts_Fault_Range is deliberately NOT part of Sts_Fault. A refused target
   is a bad command, not a broken machine: it must not drop Sts_Ready and
   lock the operator out of simply retyping the height. It clears itself on
   the next accepted move, or on a reset. *)
Sts_Fault := Sts_Fault_Drive OR Sts_Fault_Timeout;

Sts_Ready := Drv_In.Ready
             AND Drv_In.Servo_is_On
             AND Drv_In.Home_Complete
             AND NOT Sts_Fault
             AND NOT Sts_EStop;

(* one-scan pulses -- cleared every scan, set by the state machine *)
Sts_MoveDone := 0;
Sts_HomeDone := 0;


(* ---------------------------------------------------------------------
   2.  Servo enable, pause, and alarm reset
   --------------------------------------------------------------------- *)
Drv_Out.Servo_On := Cmd_ServoOn;
Drv_Out.Pause    := Cmd_Stop;

(* RES is pulsed for 200 ms, and only while the drive is actually alarmed,
   so holding the HMI reset button down cannot sit on the reset bit. *)
ResetTMR.PRE         := 200;
ResetTMR.TimerEnable := Cmd_Reset AND Drv_In.Alarm_Active;
TONR(ResetTMR);
Drv_Out.Reset := ResetTMR.TimerEnable AND NOT ResetTMR.DN;

IF NOT Cmd_Reset THEN
    ResetTMR.ACC := 0;
    ResetTMR.DN  := 0;
END_IF;

(* a reset also clears the two soft faults raised by this instruction *)
IF Cmd_Reset THEN
    Sts_Fault_Timeout := 0;
    Sts_Fault_Range   := 0;
END_IF;


(* ---------------------------------------------------------------------
   3.  Motion parameters  --  refreshed every scan so an HMI edit takes
       effect on the next move without a download
   --------------------------------------------------------------------- *)
Drv_Out.Target_Speed  := Cfg_Speed;
Drv_Out.Acceleration  := Cfg_Accel;
Drv_Out.Deceleration  := Cfg_Decel;
Drv_Out.Position_Band := Cfg_Band;

(* Never leave the move watchdog at zero -- an unconfigured instance
   would fault the instant it was asked to move. *)
IF Cfg_Move_Timeout > 0 THEN
    MoveTMR.PRE := Cfg_Move_Timeout;
ELSE
    MoveTMR.PRE := 10000;
END_IF;


(* ---------------------------------------------------------------------
   4.  Command edge detection
   --------------------------------------------------------------------- *)
Req_Move := Cmd_MoveAbs AND NOT OS_Move;
OS_Move  := Cmd_MoveAbs;

Req_Home := Cmd_Home AND NOT OS_Home;
OS_Home  := Cmd_Home;


(* ---------------------------------------------------------------------
   5.  Abort  --  anything that makes motion unsafe drops the sequencer
       back to NOT READY and clears every command bit to the drive
   --------------------------------------------------------------------- *)
IF Sts_Step > 0 AND
   ( Drv_In.Alarm_Active OR Drv_In.E_Stop_Active
     OR NOT Drv_In.Servo_is_On OR Sts_Fault_Timeout ) THEN

    Drv_Out.Start_Move  := 0;
    Drv_Out.Home        := 0;
    Drv_Out.Jog_Forward := 0;
    Drv_Out.Jog_Reverse := 0;
    Sts_Busy        := 0;
    Sts_Jogging     := 0;
    Sts_InPosition  := 0;
    Sts_Step        := 10;
END_IF;


(* ---------------------------------------------------------------------
   6.  Sequencer
        0   initialise
        10  not ready      -- no servo, not homed, or drive alarm
        20  idle           -- ready and holding position
        30  move: range check and load the target
        40  move: assert DSTR, wait for the drive to take it
        50  move: wait for PEND -- this is the confirmation
        60  move: confirmed in position
        70  home: assert HOME
        80  home: wait for HEND
        90  jog            -- runs only while a jog button is held
   --------------------------------------------------------------------- *)
CASE Sts_Step OF

    0:  (* ---- initialise ------------------------------------------- *)
        Drv_Out.Start_Move  := 0;
        Drv_Out.Home        := 0;
        Drv_Out.Jog_Forward := 0;
        Drv_Out.Jog_Reverse := 0;
        Sts_Busy        := 0;
        Sts_Jogging     := 0;
        Sts_InPosition  := 0;
        Sts_Step        := 10;

    10: (* ---- not ready --------------------------------------------- *)
        Sts_Busy       := 0;
        Sts_InPosition := 0;
        Drv_Out.Start_Move := 0;
        Drv_Out.Home       := 0;

        IF Drv_In.Servo_is_On AND NOT Drv_In.Alarm_Active AND NOT Drv_In.E_Stop_Active THEN
            IF Drv_In.Home_Complete THEN
                Sts_Step := 20;
            ELSIF Req_Home THEN
                Sts_Step := 70;
            END_IF;
        END_IF;

    20: (* ---- idle: ready and holding ------------------------------- *)
        Sts_Busy       := 0;
        Sts_Jogging    := 0;
        Drv_Out.Start_Move := 0;
        Drv_Out.Home       := 0;
        Sts_InPosition := Drv_In.Position_Complete AND NOT Drv_In.Moving;

        IF NOT Cmd_Stop THEN
            IF Req_Move THEN
                Sts_Step := 30;
            ELSIF Req_Home THEN
                Sts_Step := 70;
            ELSIF Cmd_JogUp XOR Cmd_JogDn THEN
                Sts_Step := 90;
            END_IF;
        END_IF;

    30: (* ---- move 1: range check, then load the target ------------- *)
        IF Set_Position < Cfg_Pos_Min OR Set_Position > Cfg_Pos_Max THEN
            (* Target refused.  Nothing is written to the drive and the
               axis does not move -- the old code silently ignored an
               out-of-range target, which looked like a dead machine. *)
            Sts_Fault_Range := 1;
            Sts_Step        := 20;
        ELSE
            Sts_Target          := Set_Position;
            Drv_Out.Target_Position := Sts_Target;
            Sts_Fault_Range     := 0;
            Sts_InPosition      := 0;
            MoveTMR.ACC         := 0;
            MoveTMR.DN          := 0;
            Sts_Step            := 40;
        END_IF;

    40: (* ---- move 2: assert DSTR until the drive accepts ----------- *)
        Sts_Busy       := 1;
        Sts_InPosition := 0;
        Drv_Out.Start_Move := 1;

        IF Drv_In.Moving OR NOT Drv_In.Position_Complete THEN
            Sts_Step := 50;
        END_IF;

    50: (* ---- move 3: wait for PEND -- the confirmation ------------- *)
        Sts_Busy       := 1;
        Drv_Out.Start_Move := 0;

        IF Drv_In.Position_Complete AND NOT Drv_In.Moving THEN
            Sts_Step := 60;
        END_IF;

    60: (* ---- move 4: arrival confirmed ----------------------------- *)
        Sts_Busy       := 0;
        Sts_InPosition := 1;
        Sts_MoveDone   := 1;
        Sts_Step       := 20;

    70: (* ---- home 1 ------------------------------------------------ *)
        Sts_Busy    := 1;
        Drv_Out.Home    := 1;
        MoveTMR.ACC := 0;
        MoveTMR.DN  := 0;

        IF Drv_In.Homing THEN
            Sts_Step := 80;
        END_IF;

    80: (* ---- home 2: wait for HEND --------------------------------- *)
        Sts_Busy := 1;
        Drv_Out.Home := 0;

        IF Drv_In.Home_Complete AND NOT Drv_In.Homing THEN
            Sts_HomeDone := 1;
            Sts_Step     := 20;
        END_IF;

    90: (* ---- jog: held-to-run -------------------------------------- *)
        Sts_Busy                 := 1;
        Sts_Jogging              := 1;
        Drv_Out.Inch_Select          := 0;
        Drv_Out.Jog_Parameter_Select := Cfg_Jog_Fast;

        Drv_Out.Jog_Forward := Cmd_JogUp AND NOT Cmd_JogDn AND NOT Cmd_Stop;
        Drv_Out.Jog_Reverse := Cmd_JogDn AND NOT Cmd_JogUp AND NOT Cmd_Stop;

        IF NOT (Cmd_JogUp XOR Cmd_JogDn) OR Cmd_Stop THEN
            Drv_Out.Jog_Forward := 0;
            Drv_Out.Jog_Reverse := 0;
            Sts_Jogging     := 0;
            Sts_Step        := 20;
        END_IF;

ELSE
    Sts_Step := 0;

END_CASE;


(* ---------------------------------------------------------------------
   7.  Move / home watchdog
       If the drive never reports PEND (or HEND) inside the timeout, the
       instruction faults instead of hanging.  The old program had no
       such check -- a stalled actuator simply stopped the line with no
       indication of why.
   --------------------------------------------------------------------- *)
MoveTMR.TimerEnable := (Sts_Step >= 40 AND Sts_Step <= 50)
                       OR (Sts_Step >= 70 AND Sts_Step <= 80);
TONR(MoveTMR);

IF NOT MoveTMR.TimerEnable THEN
    MoveTMR.ACC := 0;
    MoveTMR.DN  := 0;
END_IF;

IF MoveTMR.DN THEN
    Sts_Fault_Timeout := 1;
END_IF;
