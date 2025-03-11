from .transcode import encode_instruction

class Compiler:
    def __init__(self):
        self.updates = {}
        self.sequence_duration = None
        self.starting_state = {i: False for i in range(24)}
        self.instructions = []

    def clear_updates(self):
        self.updates = {}
        self.sequence_duration = None

    def add_update(self,
                    time_clockcycles: int,
                    state_dict: dict = None,
                    goto_address: int = None,
                    goto_counter: int = None,
                    stop_and_wait: bool = None,
                    hardware_trig_out: bool = None,
                    notify_computer: bool = None,
                    powerline_sync: bool = None) -> None:
        '''
        Add or update a transition at a specified clock cycle.

        Parameters:
            time_clockcycles (int): The clock cycle when the transition will occur.
            state_dict (dict, optional): A dictionary of states in the form {channel_number: bool, ...}.
                Only include the channels you want to change; you may include channels even if the value
                is not actually changing.
            goto_address (int, optional): Address for the goto operation.
            goto_counter (int, optional): Counter value for the goto operation.
            stop_and_wait (bool, optional): Flag to enable stop-and-wait behavior.
            hardware_trig_out (bool, optional): Flag to trigger hardware output.
            notify_computer (bool, optional): Flag to notify the computer.
            powerline_sync (bool, optional): Flag for powerline synchronization.

        Behavior:
            If an entry for the specified time_clockcycles already exists in self.updates, this function
            will update the existing states and flags. If a state or flag is provided that already exists,
            its value will be updated. Otherwise, new states or flags will be added to the transition.
        '''
        if time_clockcycles not in self.updates:
            self.updates[time_clockcycles] = {'states': {}, 'flags': {}}
        
        if state_dict is not None:
            self.updates[time_clockcycles]['states'].update(state_dict)

        # Build a dictionary of flags, filtering out None values
        flags = {key: value for key, value in {
            "goto_address": goto_address,
            "goto_counter": goto_counter,
            "stop_and_wait": stop_and_wait,
            "hardware_trig_out": hardware_trig_out,
            "notify_computer": notify_computer,
            "powerline_sync": powerline_sync
        }.items() if value is not None}
        
        self.updates[time_clockcycles]['flags'].update(flags)

    def compile(self):
        '''
        Uses the updates to generate encoded instructions ready for writing to a PulseGenerator
        '''
        self.instructions = []
        if len(self.updates) == 0:
            return
        
        # Sort transitions by clock cycle time. sorted_updates is now a list of the form [(time_clockcycles, {'states':{}, 'flags':{}}), ...]
        sorted_updates = sorted(self.updates.items())
        
        current_state = self.starting_state.copy()

        if sorted_updates[0][0] != 0:
            # The instruction at t=0 was not specified.
            # The PulseGenerator always executes the first instruction immeadiately upon initial triggering (either software or hardware triggering), so this must be specified.
            sorted_updates.insert(0, (0, {'states':current_state.copy(), 'flags':{}}))

        # The last update needs to be given a duration. Either it is inferred from self.sequence_duration or it is set to 1
        final_update_time = sorted_updates[-1][0]
        if self.sequence_duration is None:
            final_update_duration = 1
        else:
            final_update_duration = self.sequence_duration - final_update_time
            assert final_update_duration >= 1
        # appending a dummy update is the easy way to make the next bit work
        sorted_updates.append((final_update_time + final_update_duration, {'states':{}, 'flags':{}}))

        for address, (current_update, next_update) in enumerate(zip(sorted_updates, sorted_updates[1:])):
            current_duration = next_update[0] - current_update[0]
            current_state.update(current_update[1]['states'])
            state = [current_state[i] for i in range(24)]

            self.instructions.append(encode_instruction(address, current_duration, state, **current_update[1]['flags']))

    def upload_instructions(self, pulsegenerator_obj):
        '''An extremely thin wrapper around some PulseGenerator methods to upload the instructions and final address in one call'''
        pulsegenerator_obj.write_instructions(self.instructions)
        pulsegenerator_obj.write_device_options(final_address=len(self.instructions) - 1)
