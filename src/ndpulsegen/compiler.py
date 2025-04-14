from .transcode import encode_instruction
from .comms import PulseGenerator

class Compiler:
    def __init__(self):
        self.updates = {}  # Dictionary keyed by absolute time; each entry is {'states': {}, 'flags': {}}
        self.starting_state = {i: False for i in range(24)}
        self.instructions = []
        self.channels = {}  # Cache for Channel objects
        self.sequence_duration = None  # Optional overall sequence duration

    def set_starting_state(self, state_dict: dict):
        """Update the starting state for multiple channels."""
        self.starting_state.update(state_dict)

    # def add_update(self, t: int, state_dict: dict = None, **flags):
    #     """
    #     Schedule an update at time 't'. This method requires an absolute time.
    #     """
    #     if t not in self.updates:
    #         self.updates[t] = {'states': {}, 'flags': {}}
    #     if state_dict:
    #         self.updates[t]['states'].update(state_dict)
    #     if flags:
    #         self.updates[t]['flags'].update(flags)

    def add_update(self, t: int, state_dict: dict = None, **flags):
        """
        Schedule an update at time 't'. This method requires an absolute time.
        """
        if t not in self.updates:
            self.updates[t] = {'states': {}, 'goto': {}, 'flags': {}}
        if state_dict:
            self.updates[t]['states'].update(state_dict)
        if flags:
            self.updates[t]['flags'].update(flags)

    def add_goto(self, t_from: int, t_to: int, goto_counter: int, **flags):
        """
        Schedule a goto instruction at time 't_from' to jump to 't_to'.
        Since the goto happens at the end of the clock cycle, it is scheduled to an instruction at
        clock cycle t_from - 1.
        
        I now have empty states and flags, I think this is ok.
        """
        if t_from - 1 not in self.updates:
            self.updates[t_from - 1] = {'states': {}, 'goto': {'t_to':t_to, 'counter':goto_counter}, 'flags': {}}
        else:
            self.updates[t_from - 1]['goto'].update({'t_to':t_to, 'counter':goto_counter})

        # I have to ensure there is some update at the t_to time, so that the compiler can ensure there 
        # will be an instruction there to jump to. But I don't need to add anything to it.
        if t_to not in self.updates:
            self.updates[t_to] = {'states': {}, 'goto': {}, 'flags': {}}

    def channel(self, channel_number: int):
        """
        Retrieve or create a Channel object for the given channel.
        """
        if channel_number not in self.channels:
            self.channels[channel_number] = Channel(channel_number, self)
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
            sorted_updates.insert(0, (0, {'states': current_state.copy(), 'flags': {}}))

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
        time_to_address = {}
        for address, update in enumerate(sorted_updates):
            time_to_address[update[0]] = address

        # Generate instructions for each time interval
        for address, (current_update, next_update) in enumerate(zip(sorted_updates, sorted_updates[1:])):
            duration = next_update[0] - current_update[0]
            current_state.update(current_update[1]['states'])
            # Create a boolean list representing channels 0 through 23
            state = [current_state[i] for i in range(24)]
            t_to = current_update[1]['goto'].get('t_to', 0)
            print(address, duration, time_to_address[t_to], current_update[1]['goto'].get('counter', 0), **current_update[1]['flags'])
            self.instructions.append(
                encode_instruction(address, duration, state, time_to_address[t_to], current_update[1]['goto'].get('counter', 0), **current_update[1]['flags'])
            )

    # def compile(self):
    #     """
    #     Process the scheduled updates to generate encoded instructions.
    #     """
    #     self.instructions = []
    #     if not self.updates:
    #         return

    #     # Sort updates by absolute time
    #     sorted_updates = sorted(self.updates.items())
    #     current_state = self.starting_state.copy()

    #     # Ensure an update exists at time 0
    #     if sorted_updates[0][0] != 0:
    #         sorted_updates.insert(0, (0, {'states': current_state.copy(), 'flags': {}}))

    #     # Calculate duration for the final update
    #     final_update_time = sorted_updates[-1][0]
    #     if self.sequence_duration is None:
    #         final_update_duration = 1
    #     else:
    #         final_update_duration = self.sequence_duration - final_update_time
    #         assert final_update_duration >= 1, "Sequence duration must extend beyond the last update"
        
    #     # Append a dummy update to determine the duration of the last segment
    #     sorted_updates.append((final_update_time + final_update_duration, {'states': {}, 'flags': {}}))

    #     # Generate instructions for each time interval
    #     for address, (current_update, next_update) in enumerate(zip(sorted_updates, sorted_updates[1:])):
    #         duration = next_update[0] - current_update[0]
    #         current_state.update(current_update[1]['states'])
    #         # Create a boolean list representing channels 0 through 23
    #         state = [current_state[i] for i in range(24)]
    #         print(current_update)
    #         self.instructions.append(
    #             encode_instruction(address, duration, state, **current_update[1]['flags'])
    #         )

    def upload_instructions(self, pulse_generator: PulseGenerator) -> None:
        """
        Upload the compiled instructions to the hardware.
        This is a convenience function. You can also just pass the compiled instructions 
        to your own pulse_generator instance manually.
        """
        pulse_generator.write_instructions(self.instructions)
        pulse_generator.write_device_options(final_address=len(self.instructions))


class Channel:
    def __init__(self, channel_number: int, compiler: Compiler):
        self.channel = channel_number
        self.compiler = compiler

    def high(self, t: int, **flags):
        """
        Schedule the channel to go high at the specified absolute time.
        """
        self.compiler.add_update(t=t, state_dict={self.channel: True}, **flags)

    def low(self, t: int, **flags):
        """
        Schedule the channel to go low at the specified absolute time.
        """
        self.compiler.add_update(t=t, state_dict={self.channel: False}, **flags)

    def pulse_high(self, t: int, duration_high: int, duration_low: int = 0, N: int = 1, flags_mode: str = "start", **flags) -> int:
        """
        Schedule a series of high pulses on the channel.
        
        flags_mode: start, evey, end. 
            start: The flags are activated at the start of the first clock cycle of the first pulse
            every: The flags are activated at the start of the first clock cycle of the every pulse
            end: The flags are activated at the start of the last clock cycle of the last pulse

        Returns:
          The total duration consumed by the scheduled pulse sequence.
        """
        if N < 1:
            return 0 # Does not do anything and the duration is 0
        if N > 1 and duration_low <= 0:
            raise ValueError("For N > 1, duration_low must be greater than 0.")

        if flags_mode == 'start':
            pulse_start = t
            self.compiler.add_update(t=pulse_start, state_dict={self.channel: True}, **flags)
            self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: False})
            pulse_start += (duration_high + duration_low)
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: True})
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: False})
                pulse_start += (duration_high + duration_low)
        elif flags_mode == 'every':
            pulse_start = t
            for i in range(N):
                # Runs if N >= 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: True}, **flags)
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: False})
                pulse_start += (duration_high + duration_low)
        elif flags_mode == 'end':
            pulse_start = t
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: True})
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: False})
                pulse_start += (duration_high + duration_low)
            self.compiler.add_update(t=pulse_start, state_dict={self.channel: True})
            self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: False}, **flags)
        else:
            raise ValueError("Invalid value for flags_mode. Valid entries are \"start\", \"evey\", \"end\"")
        
        if N == 1:
            total_duration = duration_high
        else:
            total_duration = (N - 1) * (duration_high + duration_low) + duration_high  
        return total_duration

    def pulse_low(self, t: int, duration_high: int, duration_low: int = 0, N: int = 1, flags_mode: str = "start", **flags) -> int:
        """
        Schedule a series of low pulses on the channel.
        
        flags_mode: start, evey, end. 
            start: The flags are activated at the start of the first clock cycle of the first pulse
            every: The flags are activated at the start of the first clock cycle of the every pulse
            end: The flags are activated at the start of the last clock cycle of the last pulse

        Returns:
          The total duration consumed by the scheduled pulse sequence.
        """
        if N < 1:
            return 0 # Does not do anything and the duration is 0
        if N > 1 and duration_low <= 0:
            raise ValueError("For N > 1, duration_low must be greater than 0.")

        if flags_mode == 'start':
            pulse_start = t
            self.compiler.add_update(t=pulse_start, state_dict={self.channel: False}, **flags)
            self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: True})
            pulse_start += (duration_high + duration_low)
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: False})
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: True})
                pulse_start += (duration_high + duration_low)
        elif flags_mode == 'every':
            pulse_start = t
            for i in range(N):
                # Runs if N >= 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: False}, **flags)
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: True})
                pulse_start += (duration_high + duration_low)
        elif flags_mode == 'end':
            pulse_start = t
            for i in range(N - 1):
                # Only runs if N > 1
                self.compiler.add_update(t=pulse_start, state_dict={self.channel: False})
                self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: True})
                pulse_start += (duration_high + duration_low)
            self.compiler.add_update(t=pulse_start, state_dict={self.channel: False})
            self.compiler.add_update(t=pulse_start + duration_high, state_dict={self.channel: True}, **flags)
        else:
            raise ValueError("Invalid value for flags_mode. Valid entries are \"start\", \"evey\", \"end\"")
        
        if N == 1:
            total_duration = duration_high
        else:
            total_duration = (N - 1) * (duration_high + duration_low) + duration_high  
        return total_duration