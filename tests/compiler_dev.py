import numpy as np
import time

import sys
from pathlib import Path
current_file_path = Path(__file__).resolve()
sys.path.insert(0, str(current_file_path.parent.parent / 'src'))
import ndpulsegen

def basic_compiler_test():

    cplr = ndpulsegen.Compiler()

    cplr.starting_state[3] = False
    cplr.add_transition(0, {0: True, 2:True})
    cplr.add_transition(1, {0: False})
    cplr.add_transition(7, {'notify_computer':True})

    print(cplr.transitions)
    print(cplr.compile())


if __name__ == "__main__":

    # pg = ndpulsegen.PulseGenerator()
    # print(pg.get_connected_devices())
    # pg.connect()

    basic_compiler_test()

