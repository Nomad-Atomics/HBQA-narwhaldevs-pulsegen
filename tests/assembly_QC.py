import numpy as np
import struct
import time

import sys
import os
from pathlib import Path
current_file_path = Path(__file__).resolve()
sys.path.insert(0, str(current_file_path.parent.parent / 'src'))
import ndpulsegen


def ref_clk(pg):
    '''
    Connections:
    Ref_clk_out -> Scope_ch1
    Signal_gen_output1 (BNC T piece) -> Scope_ch2
                                     -> Ref_clk_in

    Scope settings:
    Time: 50ns/div
    Scope_ch1: 1V/div
    Scope_ch2: 1V/div
    Trig: Scope_ch1, 1.5V, Normal

    Signal_gen settings:
    Output1
    Wave: CMOS
    Freq: 10MHz
    Ampl: 3.3V
    
    Instructions
    1. Check for NDPG clock signal. 
    2. Turn on signal_gen_output1. Check clocks are locked.
    3. Disconnect Ref_clk_in. Check clocks unlock.

    Pack up
    Turn off Signal_gen_output1
    '''
    pass

def trigger(pg):
    '''
    Connections:
    Ch0 -> Scope_ch1
    Signal_gen_output1 (BNC T piece) -> Scope_ch2
                                     -> Trigger_in
    Scope settings:
    Time: 20ns/div
    Scope_ch1: 1V/div
    Scope_ch2: 1V/div
    Trig: Scope_ch1, 1.5V, Normal

    Signal_gen settings:
    Output1
    Wave: CMOS
    Freq: 1MHz
    Ampl: 3.3V
    
    Instructions
    1. Run script, enable Signal_gen_output1
    2. Check Ch0 is high_10ns, low_10ns, high_20ns
    3. Check signal_gen_output1 edge is ~40ns before Ch0 edge (clocks not locked, jitter expected)
    4. Disable/enable Signal_gen_output1. Check triggering stops/restarts.
    5. Change: Signal_gen_output1 (BNC T piece) -> Scope_ch2
           to: Trigger_out -> Scope_ch_2
    6. Check trig pulse is 10ns, and aligned with Ch1 first pulse (accounting for different cable lengths)

    Pack up
    Turn off Signal_gen_output1
    Remove Trigger_in, trigger out
    '''
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='always', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

def enable(pg):
    '''
    Connections:
    Ch0 -> Scope_ch1
    Signal_gen_output1 (BNC T piece) -> Scope_ch2

    Scope settings:
    Time: 100ns/div
    Scope_ch1: 1V/div
    Scope_ch2: 1V/div
    Trig: Scope_ch1, 1.5V, Normal

    Signal_gen settings:
    Output1
    Wave: CMOS
    Freq: 1MHz
    Ampl: 3.3V
    
    Instructions
    1. Run script
    2. Check Ch0 pulses.
    3. Put 50ohm termininator on enable_input, check pulses stop.
    3. Add connection: Signal_gen_output1 (BNC T piece) -> enable_input
    5. Enable Signal_gen_output1, change scope trig to Scope_ch2
    6. Check Signal_gen_output1 = high -> Ch0 has pulses (~40ns delay).
             Signal_gen_output1 = low  -> Ch0 is constant (high or low, doesn't matter).
    7. Change: Ch0        -> Scope_ch1
           To: Enable_out -> Scope_ch1
    8. Check Enable_out trails Signal_gen_output1 by ~40ns.

    Pack up
    Hit Esc. to stop looping.
    Turn off Signal_gen_output1
    '''
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    pg.write_action(trigger_now=True)
    print('Try dragging the hardware run_enable pin to ground. It will stop the looping process.')
    print('Press Esc. key to stop looping.')
    kb = ndpulsegen.console_read.KBHit()
    while True:
        if kb.kbhit():
            if ord(kb.getch()) == 27:
                break   
    kb.set_normal_term()
    pg.write_action(disable_after_current_run=True)
    print('Looping stopped.')

def powerline_sync(pg):
    '''
    Connections:
    Ch0 -> Scope_ch1
    Alagator_BNC_draped_over_AC_line -> Scope_ch2

    Scope settings:
    Time: 5ms/div
    Scope_ch1: 1V/div
    Scope_ch2: 20mV/div
    Trig: Scope_ch1, 1.5V, Normal
    
    Instructions
    1. Run script
    2. Check scope triggers twise, separated by ~1s.
    3. Check: first trig, Ch0 pulse starts at ~peak of AC sine wave.
              second trig, Ch0 pulse starts at negative going zero crossing of AC sine wave.

    Pack up
    Remove BNC alagator dongle.
    '''
    instr0 =  ndpulsegen.encode_instruction(0, 100000, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 100000, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 200000, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 300000, [0, 0, 0])
    instr4 =  ndpulsegen.encode_instruction(4, 1, [0, 0, 0])
    instructions = [instr0, instr1, instr3, instr2, instr4]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='never', trigger_out_length=255, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    pg.write_powerline_trigger_options(trigger_on_powerline=True, powerline_trigger_delay=0)
    [print(key,':',value) for key, value in pg.get_powerline_state().items()]

    pg.write_action(trigger_now=True)
    time.sleep(1)

    # '''You can also choose at what point in the AC line cycle you want the device to restart'''
    desired_trigger_phase = 90 #desired phase in degrees
    powerline_state = pg.get_powerline_state()
    trigger_delay = desired_trigger_phase/360*powerline_state['powerline_period']

    pg.write_powerline_trigger_options(powerline_trigger_delay=int(trigger_delay))
    pg.write_action(trigger_now=True)

    [print(key,':',value) for key, value in pg.get_powerline_state().items()]

    pg.write_powerline_trigger_options(trigger_on_powerline=False, powerline_trigger_delay=0) #Remember, this is a device setting, so it persists until you change it


def channels_connection_check(pg):
    '''
    Connections:
    Ch0 (will move by hand) -> Scope_ch1

    Scope settings:
    Time: 20ns/div, 115ns offset
    Ch1: 1V/div
    Trig: Ch1, 1.5V, Normal
    Measure: Width (horoz), Vtop (vert)
    
    Instructions
    Look for: smooth insertion in all outputs.
    1. Ch0 should be (in units of 10ns): 1,0,1. Vtop~3.3V
    2. Check Ch1-23. Should have width 10-230ns.

    Pack up
    Hit Esc. to stop generating.
    '''
    states = []
    state = np.ones(24)
    for idx in range(1, 25):
        state[:idx] = 0
        states.append(state.copy())
    states[0][0] = 1
    states[2][0] = 1
    '''
    0: 1, 0, 1, 0...
    1: 1, 0...
    2: 1, 1, 0...
    3: 1, 1, 1, 0...
    ...
    '''
    instructions = []
    for idx, state in enumerate(states):
        instructions.append(ndpulsegen.transcode.encode_instruction(idx, 1, state))
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=23, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)
    kb = ndpulsegen.console_read.KBHit()
    print('Press \'Esc\' to stop.')
    while True:
        if kb.kbhit():
            input_character = kb.getch()
            if input_character.encode() == chr(27).encode():
                break
    pg.write_action(disable_after_current_run=True)
    print(pg.read_all_messages(timeout=0.5))


if __name__ == "__main__":

    pg = ndpulsegen.PulseGenerator()
    print(pg.get_connected_devices())
    pg.connect()

    # ref_clk(pg)
    # trigger(pg)
    # enable(pg)
    # powerline_sync(pg)
    channels_connection_check(pg)
