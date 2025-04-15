import numpy as np
import time

import sys
from pathlib import Path
current_file_path = Path(__file__).resolve()
sys.path.insert(0, str(current_file_path.parent.parent / 'src'))
import ndpulsegen

def basic_compiler_test():

    compiler = ndpulsegen.Compiler()

    aom = compiler.channel(9)

    compiler.starting_state[3] = False
    # compiler.add_update(0, {0: True, 2:True})
    # compiler.add_update(7, {0: False})
    compiler.add_update(3, notify_computer=True, powerline_sync=True)

    aom.high(7, hardware_trig_out=True)
    # aom.low(8)
    # pulse_duration = aom.pulse_high(t=10, duration_high=2, duration_low = 3, N = 2, flags_mode = 'start', hardware_trig_out=True)
    # pulse_duration = aom.pulse_low(t=10, duration_low=2, duration_high = 3, N = 2, flags_mode = 'start', hardware_trig_out=True)
    pulse_duration = aom.pulse_low(10, 5)

    # print(pulse_duration)
    # print(cplr.updates)
    compiler.compile()

def goto_compiler_test():

    compiler = ndpulsegen.Compiler()

    compiler.starting_state[3] = False
    compiler.add_update(0, {0: True, 2:True})
    compiler.add_update(3, {0: True, 2:True})
    compiler.add_update(10, {0: True, 2:True})
    compiler.add_update(15, {0: False})
 
    # compiler.add_goto(t_from=7, t_to=4, goto_counter=7)
    compiler.add_goto(t_from=2, t_to=6, goto_counter=9)


    # compiler.compile()


if __name__ == "__main__":

    # pg = ndpulsegen.PulseGenerator()
    # print(pg.get_connected_devices())
    # pg.connect()

    basic_compiler_test()
    # goto_compiler_test()

    # for a in range(-1):
    #     print(a)

