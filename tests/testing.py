import numpy as np
import struct
import time

import sys
import os
from pathlib import Path
current_file_path = Path(__file__).resolve()
sys.path.insert(0, str(current_file_path.parent.parent / 'src'))
import ndpulsegen


def echo_terminal_characters(pg):
    print('Echoing terminal. Press \'Esc\' to stop.')
    kb = ndpulsegen.console_read.KBHit()
    while True:
        if kb.kbhit():
            input_character = kb.getch()
            if input_character.encode() == chr(27).encode():
                break
            pg.write_echo(input_character.encode())
        all_messages = pg.read_all_messages()
        if all_messages:
            for message in all_messages: 
                print(message['echoed_byte'].decode(errors='replace'))
        time.sleep(0.01)
    kb.set_normal_term()

def cause_invalid_receive(pg):
    '''This function deliberatly sends a message with an invalid message identifier
    to test that the FPGA is dealing with the error correctly'''
    message_identifier = struct.pack('B', 15)
    pg.write_command(message_identifier)
    print(pg.read_all_messages(timeout=0.5))

def cause_timeout_on_receive(pg):
    '''This function deliberatly sends a message that is incomplete'''
    message_identifier = struct.pack('B', 153)
    pg.write_command(message_identifier)
    pg.write_command(struct.pack('B', 1))
    pg.write_command(struct.pack('B', 2))
    print(pg.read_all_messages(timeout=0.5))

def cause_timeout_on_message_forward(pg):
    '''This demonstrates a limitation of the instruction loading process on the FPGA. If a run is actually running,
    and that run contains ONLY instructions that last a SINGLE cycle, then there is never a 'gap' in the updating of
    old instructions to load a new instruction in there. This is unlikely to happen in practise, but it came up once.'''
    #address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 = ndpulsegen.transcode.encode_instruction(0, 1, 0b11111111)
    instr1 = ndpulsegen.transcode.encode_instruction(1, 1, 0b10101010)
    instructions = [instr0, instr1]
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=1, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)

    pg.write_instructions(instructions)
    print(pg.read_all_messages(timeout=0.5))
    time.sleep(1)
    pg.write_action(disable_after_current_run=True)



def fully_load_ram_test(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instructions = []
    for address in range(0, 8192, 2):
        instructions.append(ndpulsegen.transcode.encode_instruction(address, 1, [1, 1, 1]))
        instructions.append(ndpulsegen.transcode.encode_instruction(address+1, 1, [0, 0, 0]))

    tstart = time.time()
    pg.write_instructions(instructions)
    tend = time.time()

    time_total = tend-tstart
    print('Time required to load the RAM FULL of instructions = {:.2f} ms \nWhich is {:.2f} instructions/ms \nOr {:.2f} μs/instruction '.format(time_total*1E3, (address+1)/(time_total*1E3), (time_total*1E6)/(address+1)))

    pg.write_device_options(final_address=address+1, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_action(trigger_now=True)
    print(pg.read_all_messages(timeout=1))



def test_notifications(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    # address, state, countdown, loopto_address, loops, stop_and_wait_tag, hard_trig_out_tag, notify_computer_tag
    # pg.write_action(reset_output_coordinator=True)
    instructions = []
    instruction_number = 512
    # instruction_number = 5

    for address in range(0, instruction_number):
        instructions.append(ndpulsegen.transcode.encode_instruction(address, 2, [1, 1, 1], notify_computer=True))
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=instruction_number-1, run_mode='single', accept_hardware_trigger='never', trigger_out_length=255, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    pg.write_action(trigger_now=True)
    [print(msg) for msg in pg.read_all_messages(timeout=0.1)]


def pcb_connection_check(pg):
     #address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
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
        # print(state)
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


def print_bytes(bytemessage):
    print('Message:')
    for letter in bytemessage[::-1]:
        print('{:08b}'.format(letter), end =" ")
    print('')


def current_address_problem(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 = ndpulsegen.transcode.encode_instruction(0, 1, [0, 0, 0])
    instr1 = ndpulsegen.transcode.encode_instruction(1, 1, [0, 1, 0])
    instr2 = ndpulsegen.transcode.encode_instruction(2, 2, [1, 0, 0])
    instr3 = ndpulsegen.transcode.encode_instruction(3, 2, [1, 1, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)

    pg.write_device_options(final_address=3, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    

    '''Testing the get state notification'''
    pg.write_action(trigger_now=True)
    [print(key,':',value) for key, value in pg.get_state().items() if key in ['current_address', 'state']]
    pg.write_action(disable_after_current_run=True)
    # pg.write_action(reset_run=True)

'''Ok, so this is the behaviour on the whole.

current next    result
1       1       correct
1       2       correct
2       1       correct or "current_address" ahead by one (dependent on request arrival time)
2       2       correct or "current_address" ahead by one (dependent on request arrival time)

Bottom line: it seems like it should be easy to sync up the output state, with the address that state is from. 
            But actually, it is a very hard problem. It is not worth it at the moment. 
            Just don't highlight its existance.

'''

def quick_check(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    # instr0 = ndpulsegen.transcode.encode_instruction(0, 1, [1, 1, 1])
    # instr1 = ndpulsegen.transcode.encode_instruction(1, 1, [0, 1, 0])
    # instr2 = ndpulsegen.transcode.encode_instruction(2, 2, [1, 1, 0])
    # instr3 = ndpulsegen.transcode.encode_instruction(3, 2, [0, 0, 0])

    # instructions = [instr0, instr1, instr2, instr3]
    # pg.write_instructions(instructions)

    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='always', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    
    pg.write_echo(b'y')
    [print(msg) for msg in pg.read_all_messages(timeout=0.1)]
    # '''Testing the get state notification'''
    # pg.write_action(trigger_now=True)
    # [print(key,':',value) for key, value in pg.get_state().items() if key in ['current_address', 'state']]
    # pg.write_action(disable_after_current_run=True)


def quick_count(pg):
    
    instructions = []
    for counter in range(2**10):
        bit0 = (counter & 2**0) >> 0
        bit1 = (counter & 2**1) >> 1
        bit2 = (counter & 2**2) >> 2
        bit3 = (counter & 2**3) >> 3
        bit4 = (counter & 2**4) >> 4
        bit5 = (counter & 2**5) >> 5
        bit6 = (counter & 2**6) >> 6
        bit7 = (counter & 2**7) >> 7
        bit8 = (counter & 2**8) >> 8
        bit9 = (counter & 2**9) >> 9
        instructions.append(ndpulsegen.transcode.encode_instruction(counter, 1, [bit0, bit1, bit2, bit3, bit4, bit5, bit6, bit7, bit8, bit9]))
        # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
        print(bit0, bit1, bit2, bit3, bit4)
    instructions.append(ndpulsegen.transcode.encode_instruction(2**10, 5, [0,0,0,0,0]))

    # instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [0,0,0,0,0]))

    # pg.write_action(reset_run=True)
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=2**10, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    pg.write_action(trigger_now=True)

def specific_count(pg):
    # pg.write_action(reset_run=True)
    pg.write_action(disable_after_current_run=True)
    instructions = []
    # instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, 1, [1,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(3, 1, [1,1,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, 1, [1,1,1,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(5, 1, [1,1,1,1,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(6, 1, [1,1,1,1,1,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(7, 1, [1,1,1,1,1,1,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(8, 1, [1,1,1,1,1,1,1,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(9, 1, [1,1,1,1,1,1,1,1,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(10, 1, [1,1,1,1,1,1,1,1,1,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(11, 1, [1,1,1,1,1,1,1,1,1,1]))



    instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1,0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, 1, [1,0,0,0,0,0,0,0,0,0]))
    instructions.append(ndpulsegen.transcode.encode_instruction(1, 100, [0,0,0,0,0,0,0,0,0,0]))

    # instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(3, 1, [0,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, 1, [1,0,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(5, 1, [1,1,0,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(6, 1, [1,1,1,0,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(7, 1, [1,1,1,1,0,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(8, 1, [1,1,1,1,1,0,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(9, 1, [1,1,1,1,1,1,0,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(10, 1, [1,1,1,1,1,1,1,0,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(11, 1, [1,1,1,1,1,1,1,1,0,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(12, 1,[1,1,1,1,1,1,1,1,1,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(13, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(14, 100, [0,0,0,0,0,0,0,0,0,0]))

    # instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1,1,1,1,1,1,1,1,1,1]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, 1, [1,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(3, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, 1, [1,1,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(5, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(6, 1, [1,1,1,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(7, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(8, 1, [1,1,1,1,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(9, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(10, 1, [1,1,1,1,1,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(11, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(12, 1, [1,1,1,1,1,1,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(13, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(14, 1, [1,1,1,1,1,1,1,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(15, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(16, 1, [1,1,1,1,1,1,1,1,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(17, 1, [0,0,0,0,0,0,0,0,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(18, 1, [1,1,1,1,1,1,1,1,0,0]))
    # instructions.append(ndpulsegen.transcode.encode_instruction(19, 1, [0,0,0,0,0,0,0,0,0,0]))
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=len(instructions)-1, run_mode='continuous', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    pg.write_action(trigger_now=True)


def hardware_trig_acceptance(pg):
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instr0 = ndpulsegen.transcode.encode_instruction(0, 1, [1, 1, 1])
    instr1 = ndpulsegen.transcode.encode_instruction(1, 2, [0, 1, 0], stop_and_wait=True)
    instr2 = ndpulsegen.transcode.encode_instruction(2, 2, [1, 1, 0])
    instr3 = ndpulsegen.transcode.encode_instruction(3, 2, [0, 0, 0])

    instructions = [instr0, instr1, instr2, instr3]
    pg.write_instructions(instructions)


    # pg.write_action(reset_run=True)
    [print(key,':',value) for key, value in pg.get_state().items() if key in ('current_address', 'accept_hardware_trigger')]

    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='always', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='once', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    ## It all seems to be working.
    
    # pg.write_action(trigger_now=True)
    # time.sleep(1)
    # pg.write_action(trigger_now=True)
    [print(key,':',value) for key, value in pg.get_state().items() if key in ('current_address', 'accept_hardware_trigger')]
    # [print(key,':',value) for key, value in pg.get_state().items()]
    

    # last_address = -1
    # while True:
    #     current_address = pg.get_state()['current_address']
    #     if current_address != last_address:
    #         print(f'current_address: {current_address}')
    #         last_address = current_address


def wait_monitor_development(pg):
    instructions = []
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [1, 1, 1], notify_computer=False, stop_and_wait=False))
    instructions.append(ndpulsegen.transcode.encode_instruction(1, 1, [0, 1, 0], notify_computer=False, stop_and_wait=True))
    instructions.append(ndpulsegen.transcode.encode_instruction(2, 2, [1, 1, 0], notify_computer=False, stop_and_wait=False))
    instructions.append(ndpulsegen.transcode.encode_instruction(3, 1, [0, 0, 0], notify_computer=False, stop_and_wait=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, 2, [1, 0, 0], notify_computer=True, stop_and_wait=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(5, 2, [0, 0, 0], notify_computer=True, stop_and_wait=False))
    pg.write_instructions(instructions)

    # pg.write_device_options(final_address=len(instructions)-1, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='always', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)
    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='once', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    # pg.write_action(trigger_now=True)
    # pg.write_action(reset_run=True)
    time.sleep(1)
    pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    [print(msg) for msg in pg.read_all_messages(timeout=0.1)]
    [print(key,':',value) for key, value in pg.get_state().items()]
    [print(key,':',value) for key, value in pg.get_state_extras().items()]

def powerline_check(pg):
    instructions = []
    # address, duration, state, goto_address=0, goto_counter=0, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False
    # instructions.append(ndpulsegen.transcode.encode_instruction(0, int(1E6), [1], notify_computer=False, stop_and_wait=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, int(2E5), [0], notify_computer=False, stop_and_wait=True))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, 5, [0], notify_computer=False, stop_and_wait=False, powerline_sync=True))
    # instructions.append(ndpulsegen.transcode.encode_instruction(3, int(3E6), [1], notify_computer=False, stop_and_wait=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, 10, [0], notify_computer=False, stop_and_wait=False))
    # pg.write_instructions(instructions)

    # pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)

    # pg.write_action(trigger_now=True)
    # pg.write_action(reset_run=True)

    # bugger. So check if this is happening:
    # If a stop and wait instruction is active, where the next instruction is a powerline sync instruction, the "powerline" can become triggered while the stop and wait is active!
    # which means the powerline sync instruction happens straight away.
    # NOPE
    # instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [0], stop_and_wait=True, powerline_sync=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(1, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=True))
    # instructions.append(ndpulsegen.transcode.encode_instruction(2, int(1E-3/10E-9), [0], stop_and_wait=True, powerline_sync=False))
    # instructions.append(ndpulsegen.transcode.encode_instruction(3, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=True))
    # instructions.append(ndpulsegen.transcode.encode_instruction(4, int(105E-3/10E-9), [0], stop_and_wait=False, powerline_sync=False))
    # pg.write_instructions(instructions)

    # pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_action(trigger_now=True)


    instructions.append(ndpulsegen.transcode.encode_instruction(0, 1, [0], stop_and_wait=False, powerline_sync=False))
    instructions.append(ndpulsegen.transcode.encode_instruction(1, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=False))
    instructions.append(ndpulsegen.transcode.encode_instruction(2, int(1.0E-3/10E-9), [0], stop_and_wait=True, powerline_sync=False, notify_computer=True))
    instructions.append(ndpulsegen.transcode.encode_instruction(3, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=True, notify_computer=True))
    instructions.append(ndpulsegen.transcode.encode_instruction(4, int(0.1E-3/10E-9), [0], stop_and_wait=False, powerline_sync=False))
    pg.write_instructions(instructions)
    pg.write_powerline_trigger_options(trigger_on_powerline=False, powerline_trigger_delay=0)
    # pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='single_run', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=False, software_run_enable=True)
    # pg.write_action(trigger_now=True)
    fails = 0
    loops = 0
    N = 100
    for a in range(N):
        loops += 1
        pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)
        time.sleep(np.random.random(1)[0]*100E-3)
        pg.write_action(trigger_now=True)
        # time.sleep(0.012)
        # pg.write_action(trigger_now=True)

        a2 = pg.return_on_notification(address=2, timeout=1)
        a3 = pg.return_on_notification(address=3, timeout=1)
        a2t = a2['run_time']
        a3t = a3['run_time']

        if (a3t - a2t) < (int(1E-3/10E-9) + 11): # +2 seems to be the limit, but the chances don't increase in proportion to this extra time.
            fails += 1                             # nope, it also fails sometimes at +1, just much more rarely. -> ~1% instaead of ~7-10%
            # break
        print(loops, fails)
        pg.return_on_notification(finished=True, timeout=1)

# OK, probably need to go and actually think about the FPGA code. damnit.

    print(f'{fails/loops*100}%')

    # happens both with 'once' and 'single_run'. But it is much more common with single_run hardware triggers.

def software_retrigger_check(pg):
    # pg.write_action(reset_run=True)
    instructions = []
    instructions.append(ndpulsegen.encode_instruction(0, 1, [0], stop_and_wait=False, powerline_sync=False))
    instructions.append(ndpulsegen.encode_instruction(1, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=False))
    instructions.append(ndpulsegen.encode_instruction(2, int(1.0E-3/10E-9), [0], stop_and_wait=True, powerline_sync=False, notify_computer=True))
    instructions.append(ndpulsegen.encode_instruction(3, int(10E-3/10E-9), [1], stop_and_wait=False, powerline_sync=True, notify_computer=True))
    instructions.append(ndpulsegen.encode_instruction(4, int(0.1E-3/10E-9), [0], stop_and_wait=False, powerline_sync=False))
    pg.write_instructions(instructions)

    pg.write_powerline_trigger_options(trigger_on_powerline=False, powerline_trigger_delay=0)
    pg.write_device_options(final_address=4, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    pg.write_action(trigger_now=True)
    time.sleep(0.1)
    pg.write_action(trigger_now=True)
    [print(msg) for msg in pg.read_all_messages(timeout=0.1)]

def run_timer_test(pg):
    instructions = []
    instructions.append(pg.encode_instruction(address = 0, duration = 1, state = np.ones(24)))
    instructions.append(pg.encode_instruction(address = 1, duration = int(1/10E-9), state = np.zeros(24), notify_computer=True))
    # instructions.append(pg.encode_instruction(address = 1, duration = 1, state = np.zeros(24)))
    pg.write_instructions(instructions)
    pg.write_device_options(final_address=len(instructions)-1, run_mode='single', accept_hardware_trigger='never', trigger_out_length=1, trigger_out_delay=0, notify_on_main_trig_out=False, notify_when_run_finished=True, software_run_enable=True)

    # Trigger the device in software to start it running
    pg.write_action(trigger_now=True)
    [print(msg) for msg in pg.read_all_messages(timeout=1.1)]

    # [print(key,':',value) for key, value in pg.get_state().items()]
    # [print(key,':',value) for key, value in pg.get_powerline_state().items()]
    [print(key,':',value) for key, value in pg.get_state_extras().items()]
    pg.write_action(reset_run=True)
    [print(key,':',value) for key, value in pg.get_state_extras().items()]

if __name__ == "__main__":

    pg = ndpulsegen.PulseGenerator()
    print(pg.get_connected_devices())
    # pg.connect(serial_number=12582915)
    pg.connect(serial_number=12582917)
    # pg2 = ndpulsegen.PulseGenerator()
    # # print(pg.get_connected_devices())
    # pg2.connect(serial_number=12582917)

    run_timer_test(pg)

    # quick_check(pg2) 
    # quick_check(pg)
    # quick_count(pg)
    # specific_count(pg)

    # echo_terminal_characters(pg)
    # cause_invalid_receive(pg)
    # cause_timeout_on_receive(pg)
    # cause_timeout_on_message_forward(pg)
    # fully_load_ram_test(pg)                  
    # test_notifications(pg)
    # pcb_connection_check(pg)
    # current_address_problem(pg)
    # wait_monitor_development(pg)
    # hardware_trig_acceptance(pg)
    # powerline_check(pg)
    # software_retrigger_check(pg)

    # instruction = ndpulsegen.transcode.encode_instruction(address=1234, duration=5678, state=[0, 1, 0, 1], goto_address=69, goto_counter=13, stop_and_wait=False, hardware_trig_out=False, notify_computer=False, powerline_sync=False)
    # print_bytes(instruction)


'''
Possible bugs/less than ideal behaviour
    Get state: the current_address is not the address being output, but the next address to be output. See current_address_problem



Things to implement:
    Serial number. 
        Give each board a serial number, or have it get it directly frim the xilinx chip
        Actually. Put this info in the Flash chip. That way I don't have to touch the FPGA design.

    Breakout Flash chip
        Save and recover static state form chip.
        Recover serial number on turn on.
'''