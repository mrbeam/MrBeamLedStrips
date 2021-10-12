#!/usr/bin/env python
from threading import Thread
from mrbeam_ledstrips.state_animations import LEDs
from mrbeam_ledstrips.server import get_config

class LEDLoopTester:
    """A class that sets up an LED thread for pytest classes that need it."""

    def setup_leds(self):
        # Load an empty config (uses default settings)
        config = get_config("")
        self.leds = LEDs(config)
        self.led_thread = Thread(target=self.leds.loop)
        self.led_thread.start()

    def teardown_leds(self):
        self.leds.stop()
        self.led_thread.join(timeout=1)
