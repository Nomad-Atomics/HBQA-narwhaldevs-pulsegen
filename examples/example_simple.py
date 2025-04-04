# This allows the examples to be run from the examples folder, or from the root folder
# Uncomment the following lines if you want to run the example from the examples folder
# import sys
# from pathlib import Path
# current_file_path = Path(__file__).resolve()
# sys.path.insert(0, str(current_file_path.parent.parent / 'src'))

import ndpulsegen
import numpy as np

# Initialise the pulse generator object and connect to the hardware
pg = ndpulsegen.PulseGenerator()
pg.connect()


# Create the "timing instructions" you want to use. 
'''The simplest instructions just have an address, the duration (the number of cycles
to output that instruction for), and the state for each of the 24 output channels (high or low).
'''
instr0 = pg.encode_instruction(address = 0, duration = 1, state = np.ones(24))
instr1 = pg.encode_instruction(address = 1, duration = 5, state = np.zeros(24))
instr2 = pg.encode_instruction(address = 2, duration = 2, state = [1, 0, 1, 0, 1, 0]) # Note, if you specify fewer than 24 channels, the unspecified channels are assumed to be zero.
instr3 = pg.encode_instruction(address = 3, duration = 10, state = np.zeros(24))

# Put the instructions in a list, and write them to the hardware
instructions = [instr0, instr1, instr2, instr3] 
pg.write_instructions(instructions)

# Adjust all the setting options of the hardware to match what you want. Only some options are shown here.
pg.write_device_options(final_address=3, run_mode='single', accept_hardware_trigger='never')

# Trigger the device in software to start it running
pg.write_action(trigger_now=True)

