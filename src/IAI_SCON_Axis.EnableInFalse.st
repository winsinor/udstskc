(* =====================================================================
   IAI_SCON_Axis -- EnableInFalse

   Runs when the calling rung goes false.  Every command bit to the
   drive is dropped so the actuator cannot be left jogging or with DSTR
   held if the rung that calls this instruction is ever conditioned off.
   ===================================================================== *)
Drv_Out.Start_Move  := 0;
Drv_Out.Home        := 0;
Drv_Out.Jog_Forward := 0;
Drv_Out.Jog_Reverse := 0;
Drv_Out.Servo_On    := 0;

Sts_Busy        := 0;
Sts_Jogging     := 0;
Sts_InPosition  := 0;
Sts_MoveDone    := 0;
Sts_HomeDone    := 0;
Sts_Ready       := 0;
Sts_Step        := 0;
