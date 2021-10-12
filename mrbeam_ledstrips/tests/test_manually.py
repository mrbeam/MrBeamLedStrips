from __future__ import absolute_import
import pytest
from itertools import chain
import os.path
import random
from six.moves import input
from time import sleep

from mrbeam_ledstrips.state_animations import LEDs, Colors, COMMANDS, COMMANDS_REQ_ARG
from mrbeam_ledstrips.server import get_config

from . import LEDLoopTester

ANIMATION_TIME_IN_SEC = .5
"""Duration for which to test the animations"""

tests_dir_path = os.path.dirname(os.path.realpath(__file__))
PNG_DIR = os.path.join(tests_dir_path, "../..", "extras", "png")

def user_accept(prompt):
    user_in = input(prompt + " [Y/n]").strip().lower()
    while user_in and not user_in[0] in ["y", "n"]:
        user_in = input(" Please choose 'y' or 'n'").strip().lower()
    user_in = user_in or "y"
    return user_in == "y"


class TestSolidLights:
    """Tests that switch the LEDS to a certain color and keeps that color."""

    def setup_class(self):
        # Load an empty config (uses default settings)
        config = get_config("")
        self.leds = LEDs(config)

    def test_all_white(self):
        """Should turn all of the LEDs white"""
        self.leds.all_on()
        assert user_accept("Are all the LEDs white?")

    def test_colors(self):
        """Test if all the colors can be seen. Perhaps a broken LED?"""
        for c in Colors.RED, Colors.GREEN, Colors.BLUE:
            self.leds.static_color(c)
            sleep(ANIMATION_TIME_IN_SEC)

        assert user_accept("Did you see R, G then B lights?")


    # def test_rollback(self):

class TestCommands(LEDLoopTester):
    """Test the animation loop with the animation methods."""

    setup_class = LEDLoopTester.setup_leds
    teardown_class = LEDLoopTester.teardown_leds

    def test_all_commands(self):
        for comm, comm_options in COMMANDS.items():
            if comm in COMMANDS_REQ_ARG:
                print("Skipping {} because it requires arguments".format(comm))
                continue
            print("Testing command %s" % comm)
            self.leds.change_state(comm_options[0])
            sleep(ANIMATION_TIME_IN_SEC)
            # The thread will die if an exception is raised
            # Error logs will be shown in pytest
            assert self.led_thread.is_alive()

    def test_missing_args(self):
        comm = COMMANDS_REQ_ARG[0]
        with pytest.raises(ValueError):
            self.leds.handle(COMMANDS[comm][0], [])

    def test_custom_color(self):
        my_color = tuple(str(random.randint(0, 255)) for _ in range(3))

        for comm in "CUSTOM_COLOR", "FLASH_CUSTOM_COLOR", "BLINK_CUSTOM_COLOR":
            self.leds.change_state(":".join(chain([COMMANDS[comm][0]], my_color)))
            sleep(ANIMATION_TIME_IN_SEC)
            assert self.led_thread.is_alive()

    @pytest.mark.datafiles(os.path.join(PNG_DIR, "colordots.png"))
    def test_png(self, datafiles):
        # my_color = tuple(str(random.randint(0, 255)) for _ in range(3))
        self.leds.config['png_folder'] = str(datafiles)
        self.leds.change_state(":".join(["png", "colordots.png"]))
        sleep(3) #ANIMATION_TIME_IN_SEC)
        assert self.led_thread.is_alive()
