import numpy as np
import time

# This allows the examples to be run from the examples folder, or from the root folder
import sys
from pathlib import Path
current_file_path = Path(__file__).resolve()
sys.path.insert(0, str(current_file_path.parent.parent / 'src'))

import ndpulsegen



def software_trig(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.transcode.encode_instruction(0, 1, np.ones(24))
    instr1 =  ndpulsegen.encode_instruction(1, 1, 0b000000000000000010101010)
    instr2 =  pg.encode_instruction(2, 2, 8388623)
    
    '''
    Note that because encode_instruction is called so often, it can be accessed several different ways:
    1. As a function of the ndpulsegen.transcode module. ie. ndpulsegen.transcode.encode_instruction(...)
    2. As a function of the ndpulsegen package. ie. ndpulsegen.encode_instruction(...) 
    3. As a method of a PulseGenerator object (named pg in this example). ie. pg.encode_instruction(...)
   '''


    #Instructions can be geneated by specifying the states as an integer (binary represetation representing output states)
    #Or they can be specified in a list/tuple/array
    # All the methods below are different ways to write the same state
    states = 0b11000

    states = np.zeros(24)
    states[[3, 4]]=1 #If an list/tuple/array is used, outputs are indexed by position. eg, output 0 is states[0]

    states = [0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    states = [0,0,0,1,1] # if fewer than 24 outputs are specified, trailing values are assumed to be zero
    states = (False, False, False, True, True) 
    instr3 =  ndpulsegen.encode_instruction(3, 1, states)

    # Instructions can be written to the device one at a time... or
    pg.write_instructions(instr0)
    pg.write_instructions(instr1)
    pg.write_instructions(instr2)
    pg.write_instructions(instr3)

    # Or they can be written all at once, which is usually much faster
    instructions = [instr0, instr1, instr3, instr2] #Note that the instructions don't need to be loaded in order, since you specify a RAM address explicitly.
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)
 
    print(pg.read_all_messages(timeout=0.1))

def hardware_trig(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='always', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)


def run_mode_continuous(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    time.sleep(3)
    pg.write_action(disable_after_current_run=True)

def abort_run(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0], goto_address=0,  goto_counter=1000000000)
    instructions = [instr0, instr1]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=1, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    time.sleep(5)
    pg.write_action(reset_run=True)


def run_enable_software(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=3, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    
    pg.write_action(trigger_now=True)
    time.sleep(1)
    pg.write_device_options(software_run_enable=False)
    time.sleep(1)
    pg.write_device_options(software_run_enable=True)    
    time.sleep(3)
    pg.write_action(disable_after_current_run=True)

def run_enable_hardware(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
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


def get_state(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 20000000, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 20000000, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    # state = pg.get_state()
    # print(state)
    # time.sleep(1)
    # powerline_state = pg.get_powerline_state()
    # print(powerline_state)
    [print(key,':',value) for key, value in pg.get_state().items()]
    [print(key,':',value) for key, value in pg.get_powerline_state().items()]
    [print(key,':',value) for key, value in pg.get_state_extras().items()]

def set_static_state(pg):
    # outputs are set by 24 bits of an integer. Rightmost bit is output 0.
    pg.write_static_state(np.ones(24))
    time.sleep(1)
    pg.write_static_state([0, 0, 1])
    time.sleep(1)
    pg.write_static_state(0b101)
    time.sleep(1)
    pg.write_static_state(np.zeros(24))

def notify_when_finished(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 300000000, [0, 0, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    #Note. Last instruction is 3 seconds, and even though the loop mode is continuous, the run will only run once because we will send a disable_after_current_run=True before the end of the first run
    pg.write_device_options(notify_when_run_finished=True)

    pg.write_action(trigger_now=True)
    pg.write_action(disable_after_current_run=True)

    print(pg.return_on_notification(finished=True, timeout=5))
    # pg.return_on_notification(finished=True, timeout=5)

def notify_on_specific_instructions(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 100000, [1, 1, 1], notify_computer=True)
    instr1 =  ndpulsegen.encode_instruction(1, 200000000, [0, 1, 0], notify_computer=True) 
    instr2 =  ndpulsegen.encode_instruction(2, 200000000, [1, 1, 0]) 
    instr3 =  ndpulsegen.encode_instruction(3, 300000000, [0, 0, 0], notify_computer=True) 
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    print(pg.return_on_notification(address=1, timeout=1))
    print(pg.return_on_notification(address=3, timeout=6))
    '''Notice that instruction 0 is tagged to notify the computer, which happens, but the return_on_noticication
    fucntion ignores it, because it is looking for address=1'''

    
def trigger_delay_and_duration_and_notify_on_main_trigger(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 2, [0, 1, 0]) 
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0]) 
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0]) 
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)
    
    #See that notify_on_main_trig_out=True, AND we are delaying the trigger by 2cycles, AND we have made the hardware trigger out stay high for 3cycles
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=3, trigger_out_delay=2, notify_on_main_trig_out=True, notify_when_run_finished=False, software_run_enable=True)

    pg.write_action(trigger_now=True)
    print('Run started...')
    print(pg.return_on_notification(triggered=True, timeout=7))

def trig_out_on_specific_instructions(pg):
    '''Demonstrates how to make instructions also emit a hardware trig pulse. Note that if any trigger pulses overlap,
    the resulting behavious is undefined (it is deterministic, but complicated. Just avoid doing it if this worries you).
    Note that I made the trigger delay larger than the the total run time, so the main trigger never activates.'''
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0], hardware_trig_out=True)    #Note that this instruction will now make the hardware trigout activeate
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0], hardware_trig_out=True)    #This one will too.
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=80, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

def stop_and_wait_on_specific_instructions(pg):
    '''This demonstrates how to use the stop_and_wait tags. Note that I am also using notify tags because it is convenient for the demonstration
    but they are not necessary.'''
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0], stop_and_wait=True, notify_computer=True)    # "stop_and_wait" tag here. This instruction DOES get executed, then the timer stops AFTER this instruction is finished.
    instr2 =  ndpulsegen.encode_instruction(2, 1, [1, 1, 0])                                              #Instruction 2 is loaded but its state IS NOT OUTPUT. The timer starts on the next trig, and this instruction is IMMEDIATELY EXECUTED.
    instr3 =  ndpulsegen.encode_instruction(3, 1, [0, 0, 0], stop_and_wait=True, notify_computer=True)    #Again, this is tagged as "stop_and_wait", so it runs, and then pauses on the last cycle.
    instr4 =  ndpulsegen.encode_instruction(4, 1, [0, 0, 0])                                              #Again, 4 is loaded but not executed, but will be upon the next trigger.
    instructions = [instr0, instr1, instr2, instr3, instr4]
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)
    pg.write_action(trigger_now=True)

    print(pg.return_on_notification(address=1, timeout=5))
    print('Instruction 1 exectued and contained a stop_and_wait tag. Python will now sleep for 1 second before sending another trigger.')
    time.sleep(1)
    pg.write_action(trigger_now=True)

    print(pg.return_on_notification(address=3, timeout=5))
    print('Instruction 3 exectued and contained a stop_and_wait tag. Python will now sleep for 1.5 second before sending another trigger.')
    time.sleep(1.5)
    pg.write_action(trigger_now=True)
    pg.return_on_notification(finished=True, timeout=5)

def using_loops_normally(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1 ,[1, 1, 1], notify_computer=True)
    instr1 =  ndpulsegen.encode_instruction(1, 2, [0, 1, 0], notify_computer=True)
    instr2 =  ndpulsegen.encode_instruction(2, 3, [1, 1, 0], goto_address=1, goto_counter=2, notify_computer=True) #from here to 1, twice.
    instr3 =  ndpulsegen.encode_instruction(3, 4, [0, 0, 0], goto_address=0, goto_counter=1, notify_computer=True) #from here to 0, once. So final sequence will be 0,1,2, 1,2, 1,2,3, 0,1,2, 1,2, 1,2,3 
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    pg.write_action(trigger_now=True)
    print(pg.read_all_messages(timeout=0.1))
    '''Notice here that all messages will be printed as they are received, but it wont return until it receives a "finished" notification'''


def using_loops_advanced(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1], goto_address=2, goto_counter=1 ,notify_computer=True)    #skip forward to 2 the first time it is executed.
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0], notify_computer=True)
    instr2 =  ndpulsegen.encode_instruction(2, 1, [1, 1, 0], goto_address=0, goto_counter=1, notify_computer=True)    #regular loop back to 0
    instr3 =  ndpulsegen.encode_instruction(3, 1, [0, 0, 0], goto_address=5946, goto_counter=1, notify_computer=True) #Jump to a completely different part of ram (beyound the final address)

    instr_a =  ndpulsegen.encode_instruction(5946, 1, [1, 1, 1], notify_computer=True)
    instr_b =  ndpulsegen.encode_instruction(5947, 1, [0, 1, 0], notify_computer=True)
    instr_c =  ndpulsegen.encode_instruction(5948, 1, [1, 1, 0], notify_computer=True)
    instr_d =  ndpulsegen.encode_instruction(5949, 1, [0, 0, 0], goto_address=3, goto_counter=1, notify_computer=True) #Jump back to 3
    '''An example use of this might be to have multiple large pulse sequences pre loaded into different parts of ram, and then to choose beteen any given pulse
    sequence only requires loading a single new instruction, which could be benificial if short loading times are desired between runs.'''

    #The final sequence is 0,2, 0,1,2,3 5946,5947,5948,5949, 3
    instructions = [instr0, instr1, instr2, instr3, instr_a, instr_b, instr_c, instr_d]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    pg.write_action(trigger_now=True)
    print(pg.read_all_messages(timeout=0.1))


# def powerline_test_global_setting(pg):
#     '''Note that the device only syncs with the AC line when a trigger is sent. So if this wun was set to continuous, subsequent loops would not re-sync with the AC line.'''
#     # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
#     instr0 =  ndpulsegen.encode_instruction(0, 100000, [1, 1, 1])
#     instr1 =  ndpulsegen.encode_instruction(1, 100000, [0, 1, 0])
#     instr2 =  ndpulsegen.encode_instruction(2, 200000, [1, 1, 0])
#     instr3 =  ndpulsegen.encode_instruction(3, 300000, [0, 0, 0])
#     instr4 =  ndpulsegen.encode_instruction(4, 1, [0, 0, 0])
#     instructions = [instr0, instr1, instr3, instr2, instr4]
#     pg.write_instructions(instructions)

#     pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='never', trigger_out_length=255, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

#     pg.write_powerline_trigger_options(trigger_on_powerline=True, powerline_trigger_delay=0)
#     # [print(key,':',value) for key, value in pg.get_powerline_state().items()]

#     pg.write_action(trigger_now=True)
#     time.sleep(2)

#     '''You can also choose at what point in the AC line cycle you want the device to restart'''
#     desired_trigger_phase = 90 #desired phase in degrees
#     powerline_state = pg.get_powerline_state()
#     trigger_delay = desired_trigger_phase/360*powerline_state['powerline_period']

#     pg.write_powerline_trigger_options(powerline_trigger_delay=int(trigger_delay))
#     pg.write_action(trigger_now=True)

#     # [print(key,':',value) for key, value in pg.get_powerline_state().items()]

#     pg.write_powerline_trigger_options(trigger_on_powerline=False) #Remember, this is a device setting, so it persists until you change it

def powerline_test_global_setting(pg):
    '''Note that the device only syncs with the AC line when a trigger is sent. So if this wun was set to continuous, subsequent loops would not re-sync with the AC line.'''
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
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


def powerline_sync_instruction_single_run(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 100000, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 100000, [0, 1, 0], stop_and_wait=True)
    instr2 =  ndpulsegen.encode_instruction(2, 200000, [1, 1, 0], powerline_sync=True)
    instr3 =  ndpulsegen.encode_instruction(3, 300000, [0, 0, 0])
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=255, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    pg.write_powerline_trigger_options(trigger_on_powerline=False, powerline_trigger_delay=0)

    pg.write_action(trigger_now=True)

def powerline_sync_instruction_continuous_run(pg):
    '''
    Instruction 0 cannot contain powerline_sync=True. If it did, the run would start automatically on the first AC line
    rise after that instruction was loaded, even if the remainging instructions were not in place.
    If you want a run to loop continuously, but sync with the powerline at the start of every run, the best option is to do
    the following:
        Make a "dummy instruction" at address=0, with stop_and_wait=True.
        Copy the state of the final instruction into instruction 0, and set the duration to a single clock cycle.
        In this way, instruction at address=0 behaves like part of the final instruction, and the instruction at
        address=1 effectively becomes the "first" instruction.
         '''
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    clone_instr3 =  ndpulsegen.encode_instruction(0, 1, [0, 0, 0], stop_and_wait=True)
    instr0 =  ndpulsegen.encode_instruction(1, 100000, [1, 1, 1], powerline_sync=True)
    instr1 =  ndpulsegen.encode_instruction(2, 100000, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(3, 200000, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(4, 300000, [0, 0, 0])
    instructions = [clone_instr3, instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=4, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=255, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_powerline_trigger_options(trigger_on_powerline=False, powerline_trigger_delay=0)

    pg.write_action(trigger_now=True)
    time.sleep(5)
    pg.write_action(disable_after_current_run=True)

def put_into_and_recover_from_erroneous_state(pg):
    '''This example needs to be re-done. Execution of an unset instruction now leads to an error and automatic reset.
    HOWEVER. If an instruction has is already present from a previous run, you migh have unintentended instructions executed
    which could last a long time. So you still may wish to use reset run. make the example reflect this case.'''
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False\
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1], notify_computer=True)
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0], notify_computer=True)
    instr2 =  ndpulsegen.encode_instruction(2, 300000000, [1, 1, 0], notify_computer=True)            #This instruction is executing for 3 seconds
    instr3 =  ndpulsegen.encode_instruction(3, 100, [0, 0, 0], notify_computer=True) 
    instr_hang =  ndpulsegen.encode_instruction(4999, int(2**48-1), [0, 0, 0], notify_computer=True)  #This is standing in for a possible old instruction that is sitting in memory (see explanation).
    instructions = [instr0, instr1, instr2, instr3, instr_hang]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    pg.write_action(trigger_now=True)
    '''Up to this point, everything is fine and normal. The device will execute instructions 0, 1, 2 in ~200microseconds, and then
    and then wait 3 seconds to execute instruction 3 (ram address 3)'''

    time.sleep(1) 
    '''This sleep just ensures that the device is outputting instruction at address 2, after which instruction 3 will execute.'''

    pg.write_device_options(final_address=1)
    '''But now, we have changed the 'final_address' to 1, so when instruction 3 is executed, the current address won't 
    equal the 'final_address', so the device will happily load instruction 4. Instruction 4 is unknown (will be all zeros unless
    we have previously written to it), so it will execute and then continue to instruction 5 and so on.... Eventually the address counter
    should loop back to 0 (it is only 16 bits, so will happen in ~65 microseconds if the instructions are all zeros, but could be the
    age of the universe if there are old instructions sitting in memory). When it does loop back to address 0, it will run immediately
    and when it gets to the new 'final_address', it will work properly and reset to the desired state (may run or not depending on 
    run_mode) '''
    print(pg.return_on_notification(finished=True, timeout=5)) 
    '''This will return a None, since it didn't get the finished notification'''

    #how to fix this if it does happen, and it seems like you are just not outputting what you should be
    pg.write_action(reset_run=True)
    '''Done. This immediately resets the part of the device that is reading instructions (the output_coordinator). It will now start as 
    required on the next trigger'''

    pg.write_action(trigger_now=True)
    print(pg.return_on_notification(finished=True, timeout=5)) 

    #How to avoid this coming up in the first place.
    '''All settings/instructions CAN be updated at any time (even when a run is in progress), but you should be careful. To avoid this
    particular error, it is reccommended that you wait until the end of a run using:
    pg.write_device_options(notify_when_run_finished=True)
    pg.write_action(disable_after_current_run=True)
    pg.return_on_notification(finished=True)

    and then change the final ram address. If you don't want to wait, then you can tag some of the instructions to send a software signal
    when they are executed, so at least you will know which instruction you are up to, and you can judge for youself if it is safe to
    update and given setting/instruction.
    '''


def quick_test(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 =  ndpulsegen.encode_instruction(0, 1, [1, 1, 1])
    instr1 =  ndpulsegen.encode_instruction(1, 1, [0, 1, 0])
    instr2 =  ndpulsegen.encode_instruction(2, 2, [1, 1, 0])
    instr3 =  ndpulsegen.encode_instruction(3, 3, [0, 0, 0])
    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    [print(key,':',value) for key, value in pg.get_state().items()]

#Make program run now...
if __name__ == "__main__":
    pg = ndpulsegen.PulseGenerator()
    print(pg.get_connected_devices())
    # pg.connect(serial_number=12582914)
    pg.connect()
    '''These give an introduction on how to program the device, and what capabilities it has'''

    # quick_test(pg)

    # software_trig(pg)
    # hardware_trig(pg)
    # run_mode_continuous(pg)
    # abort_run(pg) 
    # run_enable_software(pg)
    # run_enable_hardware(pg)
    # get_state(pg)
    # set_static_state(pg)
    # notify_when_finished(pg)
    # notify_on_specific_instructions(pg)
    # trigger_delay_and_duration_and_notify_on_main_trigger(pg)
    # trig_out_on_specific_instructions(pg)
    # stop_and_wait_on_specific_instructions(pg)
    # using_loops_normally(pg)
    # using_loops_advanced(pg)
    powerline_test_global_setting(pg)
    # powerline_sync_instruction_single_run(pg)
    # powerline_sync_instruction_continuous_run(pg)
    # put_into_and_recover_from_erroneous_state(pg)  


'''
Possible examples to do:
    show reprogramming on the fly (while running).
'''




