import numpy as np

# class Compiler():
#     def __init__(self):
#         self.transitions = {}
#         self.starting_state = np.zeros(24)

#     def add_transition(self, clock_cycles, vals):
#         """
#         clock_cycles is when the transition will happen (measured in clock cycles)
#         vals is a dictionary of the form {channel_number: digital_value, channel_number: digital_value, ..., stop_and_wait: True/False, other_flags}
#         Ultimately we will make instructions from this information.
#         If clock_cycles has been added before, the new channels should just be added.
#         If a channel for this clock cycle has already been added, it will be overwritten.
#         """

#         if clock_cycles in self.transitions:
#             self.transitions[clock_cycles].update(vals)
#         else:
#             self.transitions[clock_cycles] = vals.copy()

#             '''NOTe TO SELF.
#             IN THE FIRMWARE, THERE IS 1.002 AND 1.002a 
#             The a version have the zero duration error detection. 
#             I don't know why I kept the 1.002 version around. But I should probably get rid of it, because it is confusing.'''

#     def compile(self):
#         """
#         Compiles the transitions into a list of instructions.
        
#         For each transition (specified by clock_cycles), an instruction is created with:
#         - an 'address' that starts at 0 and increments for each instruction,
#         - a 'duration' that is computed as the difference in clock cycles between the current transition and the next one.
        
#         The instructions are returned as a list of dictionaries. Each dictionary has the keys:
#         - "address": the sequential address for the instruction,
#         - "duration": the number of clock cycles until the next transition (0 for the last instruction),
#         - "vals": the dictionary of channel values associated with the transition.
#         """
#         # Sort the transitions by their clock cycle keys.
#         sorted_transitions = sorted(self.transitions.items())
        
#         instructions = []
#         state = self.starting_state
        
#         # Iterate over the sorted transitions to create instructions.
#         for i, (clock, vals) in enumerate(sorted_transitions):
#             # Calculate duration: if there's a next transition, subtract current clock cycle from the next one.
#             # For the last instruction, we set the duration to 1.
#             if i < len(sorted_transitions) - 1:
#                 next_clock = sorted_transitions[i + 1][0]
#                 duration = next_clock - clock
#             else:
#                 duration = 1 # minimum duration is 1
            
#             instruction = {
#                 "address": i,
#                 "duration": duration,
#                 "vals": vals
#             }
#             instructions.append(instruction)
        
#         return instructions
    


class Compiler:
    def __init__(self):
        self.transitions = {}
        self.starting_state = np.zeros(24)

    def add_transition(self, clock_cycles, vals):
        """
        clock_cycles is when the transition will happen (measured in clock cycles)
        vals is a dictionary of the form {channel_number or flag_key: value, ...}
        If clock_cycles has been added before, the new channels/flags are added.
        If a key for this clock cycle has already been added, it will be overwritten.
        """
        if clock_cycles in self.transitions:
            self.transitions[clock_cycles].update(vals)
        else:
            self.transitions[clock_cycles] = vals.copy()

    def compile(self):
        """
        Compiles the transitions into a list of instructions that include a full set
        of parameters required by the `encode_instruction` function. The compile process
        accumulates changes over time, using default values for each parameter that isn’t
        updated at a given transition.
        """
        current_state = self.starting_state
        current_instr = {}
        # add the digital state
        for channel_idx, val in current_state:
            current_instr[channel_idx] = val
        
        default_flags = {
            'stop_and_wait': False,
            'hardware_trig_out': False,
            'notify_computer': False,
            'powerline_sync': False,
        }
        current_instr.update{default_flags}

        # Sort transitions by clock cycle time
        sorted_transitions = sorted(self.transitions.items())
        
        instructions = []
        
        # for i, (time, changes) in enumerate(sorted_transitions):
        for time, changes in sorted_transitions:
            # Determine the duration for the previous instruction.
            duration = time - prev_time
            # Create the complete instruction using the current state.
            current_instr.update(changes)

            # now I want to turn the channel state into a list or array
            for channel in range(24):
                current_state[channel] = current_instr[channel]

            instruction = {
                "address": len(instructions),
                "duration": duration,
                # Include all other parameters from current_instr.
                "state": current_state,
                "stop_and_wait": current_instr['stop_and_wait'],
                "hardware_trig_out": current_instr['hardware_trig_out'],
                "notify_computer": current_instr['notify_computer'],
                "powerline_sync": current_instr['powerline_sync']
            }
            instructions.append(instruction)
            
            # Update the current instruction with changes from this transition.
            for key, value in changes.items():
                if isinstance(key, int):
                    # Assume an integer key refers to a channel number.
                    # Update the corresponding bit in the state bitfield.
                    if value:
                        # Set the bit corresponding to channel 'key'
                        current_instr['state'] |= (1 << key)
                    else:
                        # Clear the bit corresponding to channel 'key'
                        current_instr['state'] &= ~(1 << key)
                else:
                    # For non-integer keys, assume they refer to instruction flags
                    current_instr[key] = value
            prev_time = time

        # Add the final instruction; duration can be set to 0 (or another sentinel value)
        instructions.append({
            "address": len(instructions),
            "duration": 0,
            "state": current_instr['state'],
            "goto_address": current_instr['goto_address'],
            "goto_counter": current_instr['goto_counter'],
            "stop_and_wait": current_instr['stop_and_wait'],
            "hardware_trig_out": current_instr['hardware_trig_out'],
            "notify_computer": current_instr['notify_computer'],
            "powerline_sync": current_instr['powerline_sync'],
        })
        
        return instructions
