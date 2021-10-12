#!/usr/bin/env python
from __future__ import absolute_import
import time
from mrbeam_ledstrips.state_animations import COMMANDS, COMMANDS_REQ_ARG, MAX_HISTORY, DEFAULT_STATE

from . import LEDLoopTester

class TestRollback(LEDLoopTester):
    """Test the robustness of the rollback feature."""

    # Setting up a fresh LED server for every method.
    # This guarantees that they have a virgin state history.
    setup_method = LEDLoopTester.setup_leds
    teardown_method = LEDLoopTester.teardown_leds

    def _add_unique_led_states(self, num=1):
        added_states = []
        for i, (comm, comm_options) in enumerate(COMMANDS.items()):
            # Send a list of unique states to the LEDs
            if i >= 10:
                break
            elif comm in COMMANDS_REQ_ARG or comm == "ROLLBACK":
                # Skipping because comm requires extra arguments
                # or it's the rollback we want to test
                continue
            opt = comm_options[0]
            self.leds.change_state(opt)
            added_states.append(opt)
        return added_states

    def test_rollback(self):
        """Test rollback in a 'normal' situation where there is already some history"""
        my_states = self._add_unique_led_states(MAX_HISTORY)

        self.leds.rollback()
        # We should now be back 1 state
        assert self.leds.state == my_states[-2]

        self.leds.rollback(steps=MAX_HISTORY-2)
        # We should now be back to the 1st state
        assert self.leds.state == my_states[0]

    def test_empty_rollback(self):
        """Test rollabck when there is nothing to roll back from"""

        self.leds.rollback()
        assert self.leds.state == DEFAULT_STATE

    def test_starved_rollback(self):

        self._add_unique_led_states(MAX_HISTORY)

        self.leds.rollback(MAX_HISTORY + 4)
        assert self.leds.state == DEFAULT_STATE
