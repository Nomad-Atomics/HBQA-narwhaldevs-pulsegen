from .transcode import encode_instruction
from .comms import PulseGenerator

class Compiler:
    CLOCK_PERIOD = 10e-9

    def __init__(self):
        self.updates = {}  # Dictionary keyed by absolute time; each entry is {'states': {}, 'goto': {}, 'flags': {}}
        self.starting_state = {i: False for i in range(24)}
        self.instructions = []
        self.channels = {}  # Cache for Channel objects
        self.sequence_duration = None  # Optional overall sequence duration
        self.final_address = None

    def set_starting_state(self, state_dict: dict):
        """Update the starting state for multiple channels."""
        self.starting_state.update(state_dict)

    def set_sequence_duration(self, sequence_duration, time_unit='seconds'):
        if time_unit == 'seconds':
            self.sequence_duration = int(round(sequence_duration/Compiler.CLOCK_PERIOD))
        else:
            self.sequence_duration = int(sequence_duration)

    def get_final_address(self):
        return self.final_address
    
    def get_instructions(self):
        return self.instructions

    def add_update(self, t: float,
                state_dict: dict = None,
                stop_and_wait=None,
                hardware_trig_out=None,
                notify_computer=None,
                powerline_sync=None,
                time_unit='seconds'):
        """
        Schedule an update at time 't'. This method requires an absolute time.
        
        Parameters:
            t (float or int): The time at which to schedule the update.
            state_dict (dict, optional): Dictionary to update 'states'.
            stop_and_wait (optional): Value for the 'stop_and_wait' flag.
            hardware_trig_out (optional): Value for the 'hardware_trig_out' flag.
            notify_computer (optional): Value for the 'notify_computer' flag.
            powerline_sync (optional): Value for the 'powerline_sync' flag.
        """
        # convert time to clock cycles if not already done so
        if time_unit == 'seconds':
            t = int(round(t/Compiler.CLOCK_PERIOD))
        else:
            t = int(t)

        # Create the update structure if it doesn't exist
        if t not in self.updates:
            self.updates[t] = {'states': {}, 'goto': {}, 'flags': {}}

        # Update the 'states' section if a state_dict is provided
        if state_dict:
            self.updates[t]['states'].update(state_dict)

        # Update the flags dict only for non None values
        flags_update = {'stop_and_wait':stop_and_wait, 'hardware_trig_out':hardware_trig_out, 'notify_computer':notify_computer, 'powerline_sync':powerline_sync}
        flags = {key: value for key, value in flags_update.items() if value is not None}
        if flags:
            self.updates[t]['flags'].update(flags)

    def add_goto(self, t_from: float, t_to: float, goto_counter: int, time_unit='seconds'):
        """
        Schedule a goto instruction at time 't_from' to jump to 't_to'.
        Since the goto happens at the end of the clock cycle, it is scheduled to an instruction at
        clock cycle t_from - 1.
        
        I now have empty states and flags, I think this is ok.
        """
        if time_unit == 'seconds':
            t_from = int(round(t_from/Compiler.CLOCK_PERIOD))
            t_to = int(round(t_to/Compiler.CLOCK_PERIOD))
        else:
            t_from = int(t_from)
            t_to = int(t_to)
        
        if t_from - 1 not in self.updates:
            self.updates[t_from - 1] = {'states': {}, 'goto': {'t_to':t_to, 'counter':goto_counter}, 'flags': {}}
        else:
            self.updates[t_from - 1]['goto'].update({'t_to':t_to, 'counter':goto_counter})

        # I have to ensure there is some update at the t_to time, so that the compiler can ensure there 
        # will be an instruction there to jump to. But I don't need to add anything to it.
        if t_to not in self.updates:
            self.updates[t_to] = {'states': {}, 'goto': {}, 'flags': {}}

    def channel(self, channel_number: int, starting_state = None):
        """
        Retrieve or create a Channel object for the given channel.
        starting_state: None, True, False. Allows you to specify what the channel will be set to on the
        first instruction executed (at t=0).
        """
        if channel_number not in self.channels:
            self.channels[channel_number] = Channel(channel_number, self)

        if starting_state is not None:
            self.starting_state[channel_number] = bool(starting_state)
        return self.channels[channel_number]

    def compile(self):
        """
        Process the scheduled updates to generate encoded instructions.
        This version also handels goto's
        """
        self.instructions = []
        if not self.updates:
            return

        # Sort updates by absolute time
        sorted_updates = sorted(self.updates.items())
        current_state = self.starting_state.copy()

        # Ensure an update exists at time 0
        if sorted_updates[0][0] != 0:
            sorted_updates.insert(0, (0, {'states': current_state.copy(), 'goto': {}, 'flags': {}}))

        # Calculate duration for the final update
        final_update_time = sorted_updates[-1][0]
        if self.sequence_duration is None:
            final_update_duration = 1
        else:
            final_update_duration = self.sequence_duration - final_update_time
            assert final_update_duration >= 1, "Sequence duration must extend beyond the last update"
        
        # Append a dummy update to determine the duration of the last segment
        sorted_updates.append((final_update_time + final_update_duration, {'states': {}, 'goto': {}, 'flags': {}}))

        # generate a mapping from time to address, so that I can quickly look up the address for a given t_to
        time_to_address_lookup = {time: idx for idx, (time, _) in enumerate(sorted_updates)}

        # Generate instructions for each time interval
        for address, (current_update, next_update) in enumerate(zip(sorted_updates, sorted_updates[1:])):
            duration = next_update[0] - current_update[0]
            current_state.update(current_update[1]['states'])
            # Create a boolean list representing channels 0 through 23
            state = [current_state[i] for i in range(24)]
            # Get the goto_time is it exists. Otherwise make it 0.
            # print(current_update)
            t_to = current_update[1]['goto'].get('t_to', 0)
            # Encode the instruction. 
            # Use the address of the instruction at time t_to instruction. And use the goto counter if it exists, otherwise 0.
            self.instructions.append(
                encode_instruction(address, duration, state, time_to_address_lookup[t_to], current_update[1]['goto'].get('counter', 0), **current_update[1]['flags'])
            )
        self.final_address = len(self.instructions) - 1
        return self.instructions

    def upload_instructions(self, pulse_generator: PulseGenerator) -> None:
        """
        Upload the compiled instructions to the hardware.
        This is a convenience function. You can also just pass the compiled instructions 
        to your own pulse_generator instance manually.
        """
        pulse_generator.write_instructions(self.instructions)
        pulse_generator.write_device_options(final_address=self.final_address)


class Channel:
    def __init__(self, channel_number: int, compiler: Compiler):
        self.channel = channel_number
        self.compiler = compiler

    def high(self, t: float, stop_and_wait=None, hardware_trig_out=None, notify_computer=None, powerline_sync=None, time_unit='seconds'):
        """
        Schedule the channel to go high at the specified absolute time.
        """
        self.compiler.add_update(t, {self.channel: True}, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit)

    def low(self, t: float, stop_and_wait=None, hardware_trig_out=None, notify_computer=None, powerline_sync=None, time_unit='seconds'):
        """
        Schedule the channel to go low at the specified absolute time.
        """
        self.compiler.add_update(t, {self.channel: False}, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit)

    def pulse_high(self, t: float, duration_high: int, duration_low: int = 0, N: int = 1, flags_mode: str = "start", stop_and_wait=None, hardware_trig_out=None, notify_computer=None, powerline_sync=None, time_unit='seconds') -> float:
        """
        Schedule a series of high pulses on the channel.
        
        flags_mode: start, evey, end. 
            start: The flags are activated at the start of the first clock cycle of the first pulse
            every: The flags are activated at the start of the first clock cycle of the every pulse
            end: The flags are activated at the start of the last clock cycle of the last pulse

        Returns:
          The total duration consumed by the scheduled pulse sequence.
        """
        return self._pulse(True, t, duration_high, duration_low, N, flags_mode, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit)

    def pulse_low(self, t: float, duration_low: int, duration_high: int = 0, N: int = 1, flags_mode: str = "start", stop_and_wait=None, hardware_trig_out=None, notify_computer=None, powerline_sync=None, time_unit='seconds') -> float:
        """
        Schedule a series of low pulses on the channel.
        
        flags_mode: start, evey, end. 
            start: The flags are activated at the start of the first clock cycle of the first pulse
            every: The flags are activated at the start of the first clock cycle of the every pulse
            end: The flags are activated at the start of the last clock cycle of the last pulse

        Returns:
          The total duration consumed by the scheduled pulse sequence.
        """
        return self._pulse(False, t, duration_low, duration_high, N, flags_mode, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit)

    def _pulse(self, first_segment_high: bool, t: float, duration_first_segment: float, duration_second_segment: float = 0, N: int = 1, flags_mode: str = "start", stop_and_wait=None, hardware_trig_out=None, notify_computer=None, powerline_sync=None, time_unit='seconds'):
        """
        Schedule a series of high pulses on the channel.
        
        flags_mode: start, evey, end. 
            start: The flags are activated at the start of the first clock cycle of the first pulse
            every: The flags are activated at the start of the first clock cycle of the every pulse
            end: The flags are activated at the start of the last clock cycle of the last pulse

        Returns:
          The total duration consumed by the scheduled pulse sequence.
        """

        # Do the conversion to clock_cycles here so it only has to be done once. Not evey call to add_update.
        time_unit_returned = time_unit
        if time_unit == 'seconds':
            t = int(round(t/Compiler.CLOCK_PERIOD))
            duration_first_segment = int(round(duration_first_segment/Compiler.CLOCK_PERIOD))
            duration_second_segment = int(round(duration_second_segment/Compiler.CLOCK_PERIOD))
        else:
            t = int(t)
            duration_first_segment = int(duration_first_segment)
            duration_second_segment = int(duration_second_segment)

        if first_segment_high:
            first_segment_level = True
            second_segment_level = False
        else:
            first_segment_level = False
            second_segment_level = True
    
        if N < 1:
            return 0 # Does not do anything and the duration is 0
        if N > 1 and duration_second_segment <= 0:
            raise ValueError("For N > 1, duration_low must be greater than 0.")

        if flags_mode == 'start':
            pulse_start = t
            self.compiler.add_update(pulse_start, {self.channel: first_segment_level}, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit='clock_cycles')
            self.compiler.add_update(pulse_start + duration_first_segment, {self.channel: second_segment_level}, time_unit='clock_cycles')
            pulse_start += (duration_first_segment + duration_second_segment)
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(pulse_start, {self.channel: first_segment_level}, time_unit='clock_cycles')
                self.compiler.add_update(pulse_start + duration_first_segment, {self.channel: second_segment_level}, time_unit='clock_cycles')
                pulse_start += (duration_first_segment + duration_second_segment)
        elif flags_mode == 'every':
            pulse_start = t
            for i in range(N):
                # Runs if N >= 1
                self.compiler.add_update(pulse_start, {self.channel: first_segment_level}, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit='clock_cycles')
                self.compiler.add_update(pulse_start + duration_first_segment, {self.channel: second_segment_level}, time_unit='clock_cycles')
                pulse_start += (duration_first_segment + duration_second_segment)
        elif flags_mode == 'end':
            pulse_start = t
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(pulse_start, {self.channel: first_segment_level}, time_unit='clock_cycles')
                self.compiler.add_update(pulse_start + duration_first_segment, {self.channel: second_segment_level}, time_unit='clock_cycles')
                pulse_start += (duration_first_segment + duration_second_segment)
            self.compiler.add_update(pulse_start, {self.channel: first_segment_level})
            self.compiler.add_update(pulse_start + duration_first_segment, {self.channel: second_segment_level}, stop_and_wait, hardware_trig_out, notify_computer, powerline_sync, time_unit='clock_cycles')
        else:
            raise ValueError("Invalid value for flags_mode. Valid entries are \"start\", \"evey\", \"end\"")
        
        if N == 1:
            total_duration = duration_first_segment
        else:
            total_duration = (N - 1) * (duration_first_segment + duration_second_segment) + duration_first_segment  
        
        if time_unit_returned == 'seconds':
            total_duration *= Compiler.CLOCK_PERIOD
        return total_duration

