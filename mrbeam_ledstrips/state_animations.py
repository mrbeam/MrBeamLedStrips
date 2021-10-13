# coding=utf-8
# Library to visualize the Mr Beam Machine States with the SK6812 LEDs
# Author: Teja Philipp (teja@mr-beam.org)
# using https://github.com/jgarff/rpi_ws281x

from __future__ import division, absolute_import

from collections import deque
from enum import Enum
import logging
import os
import signal
import sys
import time
import threading

PY3 = sys.version_info >= (3,0)
if PY3:
	import rpi_ws281x as ws
	from rpi_ws281x import Color
	PixelStrip = ws.PixelStrip
else:
	import _rpi_ws281x as ws
	from neopixel import Color, Adafruit_NeoPixel
	PixelStrip = Adafruit_NeoPixel


# LED strip configuration:
# Serial numbering of LEDs on the Mr Beam modules
# order is top -> down
LEDS_RIGHT_BACK =  list(range(0, 7))
LEDS_RIGHT_FRONT = list(range(7, 7+7))
LEDS_LEFT_FRONT =  list(range(32, 32+7))
LEDS_LEFT_BACK =   list(range(39, 39+7))
# order is right -> left
LEDS_INSIDE =      list(range(14, 14+18))

class Colors(Enum):
	"""RGB Color in 24-bit values"""
	OFF =    Color(0, 0, 0)
	WHITE =  Color(255, 255, 255)
	RED =    Color(255, 0, 0)
	GREEN =  Color(0, 255, 0)
	BLUE =   Color(0, 0, 255)
	YELLOW = Color(255, 200, 0)
	ORANGE = Color(226, 83, 3)
	RED2 =   Color(2, 0, 0)

"""Mapping between command IDs and the expected cli flag(s)"""
COMMANDS = dict(
	UNKNOWN                    = ['unknown'],
	DEBUG_STOP                 = ['DebugStop'],
	ON                         = ['on', 'all_on'],
	OFF                        = ['off', 'all_off'],
	ROLLBACK                   = ['rollback'],
	IGNORE_NEXT_COMMAND        = ['ignore_next_command'],
	IGNORE_STOP                = ['ignore_stop'],


	LISTENING                  = ['listening', 'Listening', '_listening', 'Startup'],
	LISTENING_COLOR            = ['listening_color'],
	LISTENING_NET              = ['listening_net', 'listening_network'],
	LISTENING_AP               = ['listening_ap'],
	LISTENING_AP_AND_NET       = ['listening_ap_and_net', 'listening_net_and_ap'],
	LISTENING_FINDMRBEAM       = ['listening_findmrbeam', 'listening_find', 'listening_findmymrbeam'],

	CLIENT_OPENED              = ['ClientOpened'],
	CLIENT_CLOSED              = ['ClientClosed'],
	ERROR                      = ['Error'],
	SHUTDOWN                   = ['Shutdown'],
	SHUTDOWN_PREPARE           = ['ShutdownPrepare'],
	SHUTDOWN_PREPARE_CANCEL    = ['ShutdownPrepareCancel'],
	PRINT_STARTED              = ['PrintStarted'],
	PRINT_DONE                 = ['PrintDone'],
	PRINT_CANCELLED            = ['PrintCancelled'],
	PRINT_PAUSED               = ['PrintPaused'],
	PRINT_PAUSED_TIMEOUT       = ['PrintPausedTimeout'],
	PRINT_PAUSED_TIMEOUT_BLOCK = ['PrintPausedTimeoutBlock'],
	BUTTON_PRESS_REJECT        = ['ButtonPressReject'],
	PRINT_RESUMED              = ['PrintResumed'],
	PROGRESS                   = ['Progress', 'progress'],
	JOB_FINISHED               = ['JobFinished', 'job_finished'],
	PAUSE                      = ['Pause', 'pause'],
	READY_TO_PRINT             = ['ReadyToPrint'],
	READY_TO_PRINT_CANCEL      = ['ReadyToPrintCancel'],
	SLICING_STARTED            = ['SlicingStarted'],
	SLICING_DONE               = ['SlicingDone'],
	SLICING_CANCELLED          = ['SlicingCancelled'],
	SLICING_FAILED             = ['SlicingFailed'],
	SLICING_PROGRESS           = ['SlicingProgress', 'slicing_progress'],
	SETTINGS_UPDATED           = ['SettingsUpdated'],
	LASER_JOB_DONE             = ['LaserJobDone'],
	LASER_JOB_CANCELLED        = ['LaserJobCancelled'],
	LASER_JOB_FAILED           = ['LaserJobFailed'],
	PNG_ANIMATION              = ['png'],
	
	LENS_CALIBRATION           = ['lens_calibration'],

	WHITE                      = ['white', 'all_white'],
	RED                        = ['red', 'all_red'],
	GREEN                      = ['green', 'all_green'],
	BLUE                       = ['blue', 'all_blue'],
	YELLOW                     = ['yellow', 'all_yellow'],
	ORANGE                     = ['orange', 'all_orange'],

	FLASH_WHITE                = ['flash_white'],
	FLASH_RED                  = ['flash_red'],
	FLASH_GREEN                = ['flash_green'],
	FLASH_BLUE                 = ['flash_blue'],
	FLASH_YELLOW               = ['flash_yellow'],
	FLASH_ORANGE               = ['flash_orange'],
	
	BLINK_WHITE                = ['blink_white'],
	BLINK_RED                  = ['blink_red'],
	BLINK_GREEN                = ['blink_green'],
	BLINK_BLUE                 = ['blink_blue'],
	BLINK_YELLOW               = ['blink_yellow'],
	BLINK_ORANGE               = ['blink_orange'],

	CUSTOM_COLOR               = ['color'],
	FLASH_CUSTOM_COLOR         = ['flash_color'],
	BLINK_CUSTOM_COLOR         = ['blink_color', 'Upload', 'upload'], # yellow blink was the lonng deprected 'upload'
)

"""A list of IDs for commands which require arguments"""
COMMANDS_REQ_ARG = (
    "CUSTOM_COLOR",
    "FLASH_CUSTOM_COLOR",
    "BLINK_CUSTOM_COLOR",
    "PNG_ANIMATION",
    "PROGRESS",
    "LISTENING_COLOR",
    "SLICING_PROGRESS",
    "DEBUG_STOP",
)

# TODO use POSIX flags to set the settings (e.g. --fps --brightness etc...)
"""The mapping between setting IDs and the expected cli flag(s)"""
SETTINGS = dict(
	FPS               = ['fps'],
	SPREAD_SPECTRUM   = ['spread_spectrum'],
	BRIGHTNESS        = ['brightness', 'bright', 'b'],
	INSIDE_BRIGHTNESS = ['inside_brightness', 'ib'],
	EDGE_BRIGHTNESS   = ['edge_brightness', 'eb'],
)

DEFAULT_STATE = COMMANDS['LISTENING'][0]
"""The state to revert to if no other state is applicable."""

MAX_HISTORY = 10
"""The number of previous LED commands to keep track of."""

DEFAULT_FPS = 1.0
"""Default frames per second for the animations (fluidity)
NOTE: This is _very_ slow
"""


class LEDs():
	"""The manager for the LED animations.

	Keeps count of fps, which animation to show, what frame we are at etc...
	The main animation loop is ``loop()``.

	Older versions of the LED strips in the MrBeamII did not follow the CE norms for EM pollution.
	Therefore, a software solution was implemented as a spread spectrum feature to spread
	the EM energy over more frequencies."""
	lock = threading.Lock()

	def __init__(self, config):
		self.config = config
		self.logger = logging.getLogger(__name__)
		self.analytics = self.config.get('enable_analytics', True)
		if self.analytics:
			from . import analytics
			analytics.hook_into_logger(self.logger)

		msg = "LEDs starting up with config: %s" % self.config
		print(msg)
		self.logger.info(msg)

		# Create NeoPixel object with appropriate configuration.
		self._init_strip(self.config['led_freq_hz'],
					self.config['spread_spectrum_enabled'],
					spread_spectrum_random=self.config['spread_spectrum_random'],
					spread_spectrum_bandwidth=self.config['spread_spectrum_bandwidth'],
					spread_spectrum_channel_width=self.config['spread_spectrum_channel_width'],
					spread_spectrum_hopping_delay_ms=self.config['spread_spectrum_hopping_delay_ms'])
		self.logger.info("LEDs strip initialized")
		self.state = DEFAULT_STATE
		self.past_states = deque([], MAX_HISTORY)
		signal.signal(signal.SIGTERM, self.clean_exit)  # switch off the LEDs on exit
		self.job_progress = 0
		self.brightness = self.config['led_brigthness']
		self.inside_brightness = 255
		self.edge_brightness = 255
		self._fps = DEFAULT_FPS
		self.fps = self.config['frames_per_second']
		self.update_required = False
		self._last_interior = None
		self.ignore_next_command = None
		self.running = False
		
		self.png_animations = dict()

	def _init_strip(
		self,
		freq_hz,
		spread_spectrum_enabled,
		spread_spectrum_random=False,
		spread_spectrum_bandwidth=None,
		spread_spectrum_channel_width=None,
		spread_spectrum_hopping_delay_ms=None
	):
		"""Create or resets the ``self.strip`` element.
		It manages the communication and actual colors displayed on each physical LED
		"""
		self.strip = PixelStrip(self.config['led_count'],
									   self.config['gpio_pin'],
									   freq_hz=freq_hz,
									   dma=self.config['led_dma'],
									   invert=self.config['led_invert'],
									   brightness=self.config['led_brigthness'],
									   strip_type=ws.SK6812_STRIP)
		spsp = getattr(self.strip, "set_spread_spectrum_config", None)
		if callable(spsp):
			self.strip.set_spread_spectrum_config(
					 spread_spectrum_enabled=spread_spectrum_enabled,
					 spread_spectrum_random=spread_spectrum_random,
					 spread_spectrum_bandwidth=spread_spectrum_bandwidth,
					 spread_spectrum_channel_width=spread_spectrum_channel_width,
					 spread_spectrum_hopping_delay_ms=spread_spectrum_hopping_delay_ms)
		else:
			self.logger.info('Spread Spectrum not supported. Install Mr Beams custom rpi_ws281x instead of stock version.')
		self.strip.begin()  # Init the LED-strip

	@property
	def fps(self):
	    """Get the frames per second (fluidity)"""
	    return self._fps

	@fps.setter
	def fps(self, value):
	    """Set the frames per second (fluidity)
	    Expects a positive ``value``.
	    If the value is ``None`` or ``0``, the fps will be set to 1 Hz by default
	    """
	    value = value or DEFAULT_FPS
	    # abs() also verifies whether `value` is numerical
	    self._fps = abs(value)

	@property
	def frame_duration(self):
	    """Returns the duration of a single frame. Requires ``self.fps`` to be non-null."""
	    return 1 / self.fps

	def stop(self):
	    """Breaks the `while` in the loop() function to stop the animations."""
	    self.running = False

	def change_state(self, nu_state):
		with self.lock:
			if self.ignore_next_command:
				self.ignore_next_command = None
				print(("state change ignored! keeping: " + str(self.state) + ", ignored: " + str(nu_state)))
				return "IGNORED {state}   # {old} -> {nu}".format(old=self.state, nu=self.state, state=nu_state)

			old_state = self.state
			if self.state != nu_state:
				print(("state change " + str(self.state) + " => " + str(nu_state)))
				self.logger.info("state change " + str(self.state) + " => " + str(nu_state))
				if self.state != nu_state:
					self.past_states.append(self.state)
				self.state = nu_state
				self.frame = 0
			if self.state == nu_state or \
					nu_state in COMMANDS['ROLLBACK'] or \
					nu_state in COMMANDS['IGNORE_NEXT_COMMAND'] or \
					nu_state in COMMANDS['IGNORE_STOP']:
				return "OK {state}   # {old} -> {nu}".format(old=old_state, nu=nu_state, state=self.state)
			else:
				if self.analytics:
					from . import analytics
					analytics.send_log_event(logging.WARNING, "Unknown state: %s", nu_state)
				return "ERROR {state}   # {old} -> {nu}".format(old=old_state, nu=self.state, state=nu_state)

	def clean_exit(self, signal, msg):
		"""Displays a dim red color."""
		self.static_color(Colors.RED2)
		self.logger.info("shutting down, signal was: %s", signal)
		# sys.exit(0)

	def off(self):
		"""Turn all LEDs off."""
		self.static_color(color=Colors.OFF, color_inside=Colors.OFF)

	def load_png(self, filename):
		"""
		Loads a png image as LED animation:
		- each pixel row is one frame, cycling from top to bottom
		- with 7..45 px: first 7 pixels of each line are used for the corner LEDs, inside LEDs are white
		- with >= 46 px: first 46 pixels of each line are copied 1:1 to the LED strip:
		  (right back corner, right front corner, inside, left front corner, left back corner)
		
		state is named "png" with parameter "file.png". => mrbeamledstrips_cli png:breathe.png 
		files are searched in pre-defined folder (default /usr/share/mrbeamledstrips/png/)
		"""
		# as long as cv2 is not absolutely necessary, let's only import it here.
		# we had cases where leds stopped working because of a broken cv2 lib
		# A broken cv2 lib should be loggen in OP/mrbPlugin but LEDs should continue to work.
		import cv2

		# check cache
		if(self.png_animations.get(filename)):
			return self.png_animations[filename]
		
		# load png
		path_to_png = os.path.join(self.config['png_folder'], filename)
		
		# check if exists, is_readable, file_size
		if os.path.isfile(path_to_png) and os.path.getsize(path_to_png) < self.config['max_png_size']: 
			self.logger.info("loading png animation {}".format(filename))
			img_4channel = cv2.imread(path_to_png, cv2.IMREAD_UNCHANGED)
			height, width, channels = img_4channel.shape
			
			# check size
			corner_leds = len(LEDS_RIGHT_BACK)
			if(width < corner_leds):
				self.logger.error("png dimension too small. Should have a minimum width of {} px. aborting... ".format(corner_leds))
				return None # abort if img is too small.
			else:
				# init animation array
				bgr = img_4channel[:,:,:3]
				animation = [None]*height
				for row in range(height):
					line = [None]*self.config['led_count']
					
					if(width < self.config['led_count']): # small png => inside LEDs are white, all corner LEDs equal.
						self.logger.info("small png => corner LEDs only")
						for col in range(corner_leds):
							b,g,r = bgr[row, corner_leds - 1 - col]
							idx_rb = LEDS_RIGHT_BACK[col]
							idx_rf = LEDS_RIGHT_FRONT[col]
							idx_lf = LEDS_LEFT_FRONT[col]
							idx_lb = LEDS_LEFT_BACK[col]
							line[idx_rb] = Color(r,g,b) 
							line[idx_rf] = Color(r,g,b) 
							line[idx_lf] = Color(r,g,b) 
							line[idx_lb] = Color(r,g,b) 
							
						for idx_in in LEDS_INSIDE:	
							line[idx_in] = Colors.WHITE # all inside

					else: # big png => all LEDs are individually controlled
						for col in range(self.config['led_count']):
							b,g,r = bgr[row, self.config['led_count'] - 1 - col]
							line[col] = Color(r,g,b)
					
					animation[row] = line
					
				self.png_animations[filename] = animation
				return animation
		else:
			self.logger.error("png {} not found or file too large (max {} Byte)".format(path_to_png, self.config['max_png_size']))
			return None

	def png(self, png_filename, frame, state_length=1):
		"""Scan a png image and apply the colours line by line onto the LEDs.
		When the animation consumes the whole image, it loops back to the 1st row."""
		animation = self.load_png(png_filename)
		frames = len(animation)
		
		if(animation != None):
			# render frame
			row = int(round(frame / state_length)) % frames

			for led in range(self.config['led_count']):
				color = animation[row][led]
				self._set_color(led, color)

			self._update()


	def fade_off(self, state_length=10/28, follow_state='ClientOpened'):
		"""Turns the side LEDs off progressively."""
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		self.logger.info("fade_off()")
		for b in _mylinspace(self.brightness/255.0, 0, int(state_length * self.fps) ):
			for r in involved_registers:
				for i in range(len(r)):
					self._set_color(r[i], self.dim_color(self.strip.getPixelColor(r[i]), b))
			self._update()
			time.sleep(state_length * self.frame_duration)
		self.change_state(follow_state)

	def error(self, frame):
		"""pulsing red from the center"""
		self.flash(frame, color=Colors.RED, state_length=1)

	def flash(self, frame, color=Colors.RED, state_length=2):
		"""Does a pulsating animation starting from the center of the side LEDs."""
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		frames = [
			[0, 0, 0, 0, 0, 0, 0],
			[0, 0, 0, 1, 0, 0, 0],
			[0, 0, 1, 1, 1, 0, 0],
			[0, 1, 1, 1, 1, 1, 0],
			[1, 1, 1, 1, 1, 1, 1],
			[1, 1, 1, 1, 1, 1, 1],
			[0, 1, 1, 1, 1, 1, 0],
			[0, 0, 1, 1, 1, 0, 0],
			[0, 0, 0, 1, 0, 0, 0]
		]

		f = int(round(frame / state_length)) % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self._set_color(r[i], color)
				else:
					self._set_color(r[i], Colors.OFF)
		self._update()

	def breathing(self, frame, color=Colors.ORANGE, bg_color=Colors.OFF, state_length=2):
		"""Fade in and out with a given color on the side LEDs.
		The bottom of the side LEDs are illuminated with ``color``.
		The top of the LEDs use the background color ``bg_color``."""
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		f_count = state_length * self.fps
		dim = 1 - (abs((frame/state_length % f_count*2) - (f_count-1))/f_count)

		my_color = color
		if isinstance(color, list):
			color_index = int(frame / f_count / 2) % len(color)
			my_color = color[color_index]
		dim_color = self.dim_color(my_color, dim)

		for r in involved_registers:
			for i in range(l):
				if i >= l-(1 if bg_color==Colors.OFF else 2):
					self._set_color(r[i], dim_color)
				else:
					self._set_color(r[i], bg_color)
		self._update()

	def breathing_static(self, frame, color=Colors.ORANGE, dim=0.2, fade_in=True):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		if fade_in:
			state_length = 2
			f_count = state_length * self.fps
			if frame < f_count:
				dim_breath = 1 - (abs((frame / state_length % f_count * 2) - (f_count - 1)) / f_count)
				if dim_breath < dim:
					self.breathing(frame, color=color, state_length=state_length)
					return

		dim_color = self.dim_color(color, dim)
		for r in involved_registers:
			for i in range(l):
				if i == l-1:
					self._set_color(r[i], dim_color)
				else:
					self._set_color(r[i], Colors.OFF)
		self._update()

	def interior_fade_in(self, frame, force=False):
		"""Progressively turn the interior LEDs white."""
		state_length = 2
		f_count = state_length * self.fps
		interior_color = Colors.WHITE
		if frame < f_count:
			if force and self._last_interior == Colors.WHITE and frame == 0:
				interior_color = Colors.OFF
			elif self._last_interior != Colors.WHITE:
				dim_breath = 1 - (abs((frame / state_length % f_count * 2) - (f_count - 1)) / f_count)
				if dim_breath < 1.0:
					interior_color = self.dim_color(Colors.WHITE, dim_breath)
		self.set_interior(interior_color, perform_update=False)

	def all_on(self):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		color = Colors.WHITE
		for r in involved_registers:
			l = len(r)
			for i in range(l):
				self._set_color(r[i], color)
		self.brightness = 255
		self._update()

	# alternating upper and lower yellow
	def blink(self, frame, color=Colors.YELLOW, state_length=8):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		fwd_bwd_range = list(range(l)) + list(range(l-1, -1, -1))

		frames = [
			[1, 1, 1, 0, 0, 0, 0],
			[0, 0, 0, 0, 1, 1, 1]
		]

		f = int(round(frame / state_length)) % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self._set_color(r[i], color)
				else:
					self._set_color(r[i], Colors.OFF)

		self._update()

	def progress(self, value, frame, color_done=Colors.WHITE, color_drip=Colors.BLUE, state_length=2):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		c = int(round(frame / state_length)) % l

		value = parse_int(value)

		for r in involved_registers:
			for i in range(l):

				bottom_up_idx = l-i-1
				threshold = value / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == c:
						self._set_color(r[i], color_drip)
					else:
						self._set_color(r[i], Colors.OFF)

				else:
					self._set_color(r[i], color_done)

		self._update()

	# pauses the progress animation with a pulsing drip
	def progress_pause(self, value, frame, breathing=True, color_done=Colors.WHITE, color_drip=Colors.BLUE, state_length=1.5):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f_count = state_length * self.fps
		dim = abs((frame/state_length % f_count*2) - (f_count-1))/f_count if breathing else 1

		value = parse_int(value)

		for r in involved_registers:
			for i in range(l):
				bottom_up_idx = l-i-1
				threshold = value / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == bottom_up_idx / 2:
						color = self.dim_color(color_drip, dim)
						self._set_color(r[i], color)
					else:
						self._set_color(r[i], Colors.OFF)

				else:
					self._set_color(r[i], color_done)


		self._update()

	def idle(self, frame, color=Colors.WHITE, state_length=1):
		leds = LEDS_RIGHT_BACK + list(reversed(LEDS_RIGHT_FRONT)) + LEDS_LEFT_FRONT + list(reversed(LEDS_LEFT_BACK))
		c = int(round(frame / state_length)) % len(leds)
		for i in range(len(leds)):
			self._set_color(leds[i], color if i == c else Colors.OFF)
		self._update()

	def job_finished(self, frame, state_length=1):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f = int(round(frame / state_length)) % (self.fps + l*2)

		if f < l*2:
			for i in range(int(round(f/2))-1, -1, -1):
				for r in involved_registers:
					self._set_color(r[i], Colors.GREEN)

		else:
			for i in range(l-1, -1, -1):
				for r in involved_registers:
					brightness = 1 - (f - 2*l)/self.fps * 1.0
					col = self.dim_color(Colors.GREEN, brightness)
					self._set_color(r[i], col)

		self._update()

	def dust_extraction(self, frame, state_length=1):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f = int(round(frame / state_length)) % (self.fps + l*2)

		if f < l*2:
			for i in range(int(round(f/2))-1, -1, -1):
				for r in involved_registers:
					self._set_color(r[i], Colors.WHITE)

		else:
			for i in range(l-1, -1, -1):
				for r in involved_registers:
					brightness = 1 - (f - 2*l)/self.fps * 1.0
					col = self.dim_color(Colors.WHITE, brightness)
					self._set_color(r[i], col)

		self._update()

	def shutdown(self, frame):
		self.static_color(Colors.RED)

	def shutdown_prepare(self, frame, duration_seconds=5):
		brightness_start_val = 205
		peak_frame = duration_seconds * self.fps
		on = frame % 10 > 3
		brightness = None
		if on:
			if (frame <= peak_frame):
				brightness = int(brightness_start_val - (brightness_start_val/peak_frame) * frame)
				brightness = brightness if brightness > 0 else 0
				myColor = self.dim_color(Colors.RED, brightness)
			else:
				myColor = Colors.RED
		else:
			myColor = Colors.OFF
		self.static_color(myColor)

	def set_interior(self, color, perform_update=True):
		color = self.dim_color(color, self.inside_brightness/255.0)
		if self._last_interior != color:
			self._last_interior = color
			leds = LEDS_INSIDE
			l = len(leds)
			for i in range(l):
				self._set_color(leds[i], color)
			if perform_update:
				self._update()

	def static_color(self, color=Colors.WHITE, color_inside=None):
		outside_leds = LEDS_RIGHT_FRONT + LEDS_LEFT_FRONT + LEDS_RIGHT_BACK + LEDS_LEFT_BACK
		for i in range(len(outside_leds)):
			self._set_color(outside_leds[i], color)
		if(color_inside != None):
			inside_leds = LEDS_INSIDE
			for i in range(len(inside_leds)):
				self._set_color(inside_leds[i], color_inside)
		self._update()

	def dim_color(self, color, brightness):
		'''
		Change the brightness (only down) of the given color value.
		:param col: the color value you want to change the brightness
		:param brightness: the brightness factor between 0 and 1
		:return: new Color with the chanes brightness
		'''
		if isinstance(color, Colors):
		    color = color.value
		r = (color & 0xFF0000) >> 16
		g = (color & 0x00FF00) >> 8
		b = (color & 0x0000FF)
		return Color(int(r*brightness), int(g*brightness), int(b*brightness))

	def demo_state(self, frame):
		f = frame % 4300
		if f < 1000:
			return "idle"
		elif f < 2000:
			return "progress:" + str((f-1000)/20)
		elif f < 2200:
			return "pause:50"
		elif f < 3200:
			return "progress:" + str((f-1200)/20)
		elif f < 4000:
			return "job_finished"
		else:
			return "warning"

	def set_fps(self, fps):
		fps = int(fps)
		if fps < 1: fps = 1
		self.fps = fps
		self.logger.info("set_fps() Changed animation speed: fps:%d (%s s/frame)" % (self.fps, self.frame_duration))
		return fps

	def spread_spectrum(self, params):
		enabled = params[0]
		if enabled == 'off':
			self._init_strip(self.config['led_freq_hz'], False)
			self.logger.info("spread_spectrum() off, led frequency is: %s", self.config['led_freq_hz'])
			return enabled
		elif enabled == 'on' and len(params) in (4,5):
			try:
				freq = int(params[1])
				bandwidth = int(params[2])
				channel_width = int(params[3])
				hopping_delay = int(params[4])
				random = params[5].startswith('r') if len(params) > 5 else False
				status = "freq=%s, bandwidth=%s, channel_width=%s, hopping_delay=%s, random:%s" % (freq, bandwidth, channel_width, hopping_delay, random)
				self.logger.info("spread_spectrum() on: " + status)
				self._init_strip(freq, True,
					spread_spectrum_random=random,
					spread_spectrum_bandwidth=bandwidth,
					spread_spectrum_channel_width=channel_width,
					spread_spectrum_hopping_delay_ms=hopping_delay)
				return status
			except:
				self.logger.exception("spread_spectrum() Exception while executing command %s", self.state)
		else:
			self.logger.info("spread_spectrum() invalid command or params. Usage: spread_spectrum:<on|off>:<center_frequency>:<bandwidth>:<channel_width>:<hopping_delay> eg: 'spread_spectrum:on:800000:180000:9000:1'")

	def rollback(self, steps=1):
		self._last_interior = None
		prev_state = self.state
		if len(self.past_states) >= steps:
			for x in range(steps):
				old_state = self.past_states.pop()
			self.state = old_state
		elif len(self.past_states) > 0:
			self.logger.warn("Rollback: limited to %d steps instead of %d", len(self.past_states), steps)
			self.state = self.past_states[0]
			self.past_states.clear()
		else:
			self.state = DEFAULT_STATE
			self.logger.warn("Rollback: no history, fallback to %s", self.state)
		self.logger.info("Rollback from '%s' to '%s'", prev_state, self.state)
			
	def rollback_after_frames(self, frame, max_frames=0, steps=1):
		try:
			max_frames = int(max_frames)
		except:
			pass
		if max_frames <= 0:
			return
		if frame > max_frames:
			self.rollback(steps=steps)

	@staticmethod
	def parse_input(data):
		state_string = data or COMMANDS['OFF'][0]
		# split params from state string
		params = state_string.split(':')
		my_state = params.pop(0)
		return my_state, params


	def handle(self, state, args):
		# Do not set the interior LED lights by default
		interior = None
		if state in [comm for key in COMMANDS_REQ_ARG for comm in COMMANDS[key]] and not args:
		    raise ValueError("command {!r} requires arguments.".format(state))


		# Daemon listening
		if state in COMMANDS['LISTENING'] or state in COMMANDS['UNKNOWN']:
			interior = None # skip interior
			self.interior_fade_in(self.frame)
			self.breathing_static(self.frame, color=Colors.WHITE, dim=0.05)
		elif state in COMMANDS['LISTENING_NET']:
			self.breathing(self.frame, color=Colors.WHITE)
		elif state in COMMANDS['LISTENING_AP']:
			self.breathing(self.frame, color=Color(150, 255, 0))
		elif state in COMMANDS['LISTENING_AP_AND_NET']:
			self.breathing(self.frame, color=[Color(150, 255, 0), Colors.WHITE])
		elif state in COMMANDS['LISTENING_FINDMRBEAM']:
			self.breathing(self.frame, color=Colors.ORANGE)
		elif state in COMMANDS['LISTENING_COLOR']:
			color = Color(*(int(a) for a in args[:3]))
			if len(args) >= 6:
				bg_color = Color(*(int(a) for a in args[3:6]))
			else:
				bg_color = Colors.OFF
			self.breathing(self.frame, color=color, state_length=2, bg_color=bg_color)

		# test purposes
		elif state in COMMANDS['ON']:
			self.all_on()

		elif state in COMMANDS['ROLLBACK']:
			self.rollback(2)

		# Server
		elif state in COMMANDS['CLIENT_OPENED']:
			self.idle(self.frame)
		elif state in COMMANDS['CLIENT_CLOSED']:
			self.breathing(self.frame)

		# Machine
		elif state in COMMANDS['ERROR']:
			self.error(self.frame)
		elif state in COMMANDS['SHUTDOWN_PREPARE']:
			self.shutdown_prepare(self.frame)
		elif state in COMMANDS['SHUTDOWN']:
			self.shutdown(self.frame)
		elif state in COMMANDS['SHUTDOWN_PREPARE_CANCEL']:
			self.rollback(2)

		# Laser Job
		elif state in COMMANDS['PRINT_STARTED']:
			self.progress(0, self.frame)
		elif state in COMMANDS['PRINT_DONE']:
			self.job_progress = 0
			self.dust_extraction(self.frame)
		elif state in COMMANDS['PRINT_CANCELLED']:
			self.job_progress = 0
			self.dust_extraction(self.frame)

		elif state in COMMANDS['LASER_JOB_DONE']:
			self.job_progress = 0
			self.job_finished(self.frame)
		elif state in COMMANDS['LASER_JOB_CANCELLED']:
			self.job_progress = 0
			self.fade_off()
		elif state in COMMANDS['LASER_JOB_FAILED']:
			self.fade_off()

		elif state in COMMANDS['PRINT_PAUSED']:
			self.progress_pause(self.job_progress, self.frame)
		elif state in COMMANDS['PRINT_PAUSED_TIMEOUT']:
			self.progress_pause(self.job_progress, self.frame, False)
		elif state in COMMANDS['PRINT_PAUSED_TIMEOUT_BLOCK']:
			# Only show for 1 second
			if self.frame > self.fps:
				self.change_state(COMMANDS['PRINT_PAUSED_TIMEOUT'][0])
			else:
				self.progress_pause(self.job_progress, self.frame, False, color_drip=Colors.RED)
		elif state in COMMANDS['PRINT_RESUMED']:
			self.progress(self.job_progress, self.frame)
		elif state in COMMANDS['PROGRESS']:
			self.job_progress = args.pop(0)
			self.progress(self.job_progress, self.frame)
		elif state in COMMANDS['JOB_FINISHED']:
			self.job_finished(self.frame)
		elif state in COMMANDS['PAUSE']:
			self.progress_pause(self.job_progress, self.frame)
		elif state in COMMANDS['READY_TO_PRINT']:
			self.flash(self.frame, color=Colors.BLUE, state_length=2)
		elif state in COMMANDS['READY_TO_PRINT_CANCEL']:
			self.idle(self.frame)
		elif state in COMMANDS['BUTTON_PRESS_REJECT']:
			# Only show for 1 second
			if self.frame > self.fps:
				self.rollback()
			else:
				self.progress_pause(self.job_progress, self.frame, False, color_drip=Colors.RED)

		# Slicing
		elif state in COMMANDS['SLICING_STARTED']:
			self.progress(0, self.frame, color_done=Colors.BLUE, color_drip=Colors.WHITE, state_length=3)
		elif state in COMMANDS['SLICING_DONE']:
			self.progress(100, self.frame, color_done=Colors.BLUE, color_drip=Colors.WHITE, state_length=3)
		elif state in COMMANDS['SLICING_CANCELLED']:
			self.idle(self.frame)
		elif state in COMMANDS['SLICING_FAILED']:
			self.fade_off()
		elif state in COMMANDS['SLICING_PROGRESS']:
			self.progress(args.pop(0), self.frame, color_done=Colors.BLUE, color_drip=Colors.WHITE, state_length=3)

		# Settings
		elif state in COMMANDS['SETTINGS_UPDATED']:
			if self.frame > 50:
				self.rollback()
			else:
				self.flash(self.frame, color=Colors.WHITE, state_length=1)

		# Lens calibration
		elif state in COMMANDS['LENS_CALIBRATION']:
			self.static_color(color=Colors.BLUE, color_inside=Colors.WHITE)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)

		# other
		elif state in COMMANDS['PNG_ANIMATION']: # mrbeamledstrips_cli png:test.png
			filename = args.pop(0)
			self.png(filename, self.frame, state_length=1)
		elif state in COMMANDS['OFF']:
			self.off()
			interior = Colors.OFF

		# colors
		elif state in COMMANDS['WHITE']:
			self.static_color(Colors.WHITE)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args)>0 else 0)
		elif state in COMMANDS['RED']:
			self.static_color(Colors.RED)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args)>0 else 0)
		elif state in COMMANDS['GREEN']:
			self.static_color(Colors.GREEN)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args)>0 else 0)
		elif state in COMMANDS['BLUE']:
			self.static_color(Colors.BLUE)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['YELLOW']:
			self.static_color(Colors.YELLOW)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['ORANGE']:
			self.static_color(Colors.ORANGE)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['CUSTOM_COLOR']:
			r, g, b = (int(args[i]) for i in range(3))
			self.static_color(Color(r, g, b))
			self.rollback_after_frames(self.frame, args.pop(0) if len(args)>0 else 0)

		elif state in COMMANDS['FLASH_WHITE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.WHITE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_RED']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.RED, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_GREEN']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.GREEN, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_BLUE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.BLUE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_YELLOW']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.YELLOW, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_ORANGE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 1
			self.flash(self.frame, color=Colors.ORANGE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['FLASH_CUSTOM_COLOR']:
			r, g, b = (int(args[i]) for i in range(3))
			state_length = int(args[3]) if len(args) > 3 else 1
			self.flash(self.frame, color=Color(r, g, b), state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_WHITE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.WHITE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_RED']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.RED, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_GREEN']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.GREEN, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_BLUE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.BLUE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_YELLOW']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.YELLOW, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_ORANGE']:
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=Colors.ORANGE, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)
		elif state in COMMANDS['BLINK_CUSTOM_COLOR']:
			my_color = Colors.YELLOW
			try:
				r = int(args.pop(0))
				g = int(args.pop(0))
				b = int(args.pop(0))
				my_color = Color(r, g, b)
			except:
				pass
			state_length = int(args.pop(0)) if len(args) > 0 else 8
			self.blink(self.frame, color=my_color, state_length=state_length)
			self.rollback_after_frames(self.frame, args.pop(0) if len(args) > 0 else 0)


		# stuff
		elif state in COMMANDS['IGNORE_NEXT_COMMAND']:
			self.ignore_next_command = state
			self.rollback()
		elif state in COMMANDS['IGNORE_STOP']:
			self.ignore_next_command = None
			self.rollback()
		elif state in COMMANDS['DEBUG_STOP']:
			sleept_time = float(args.pop(0))
			self.logger.info('DebugStop: going to sleep for %ss. Thread: %s', sleept_time, threading.current_thread())
			time.sleep(sleept_time)
			self.logger.info('DebugStop: Woke up!!!. Thread: %s', threading.current_thread())
			self.rollback()
		else:
			self.logger.warn("Don't know about command: {}".format(state))
			self.set_state_unknown()
			self.idle(self.frame, color=Color(20, 20, 20), state_length=2)

		# set interior at the end
		if interior is not None:
			self.set_interior(interior)

		self.frame += 1
		if self.frame < 0:
			# int overflow
			self.frame = 0
		time.sleep(self.frame_duration)

	def loop(self):
		self.running = True
		try:
			self.frame = 0
			while self.running:

				data = self.state

				my_state, params = self.parse_input(data)
				self.handle(my_state, params)

		except KeyboardInterrupt:
			self.logger.exception("KeyboardInterrupt Exception in animation loop:")
			self.clean_exit(signal.SIGINT, None)
		except Exception:
			self.logger.exception("Some Exception in animation loop:")
			print("Some Exception in animation loop:")

	def set_state_unknown(self):
		self.state = COMMANDS['UNKNOWN'][0]

	def set_setting(self, setting, params):
		val = None
		try:
			self.logger.info('set_setting: setting %s, params %s', setting, params)
			if setting in SETTINGS['BRIGHTNESS']:
				val = self.set_brightness(params[0])
			elif setting in SETTINGS['INSIDE_BRIGHTNESS']:
				val = self.set_inside_brightness(params[0])
			elif setting in SETTINGS['EDGE_BRIGHTNESS']:
				val = self.set_edge_brightness(params[0])
			elif setting in SETTINGS['FPS']:
				val = self.set_fps(params[0])
			elif setting in SETTINGS['SPREAD_SPECTRUM']:
				val = self.spread_spectrum(params)
		except ValueError:
			return "ERROR, could not parse the setting or parameters {}:{}".format(setting, params)
		if val is None:
			return "ERROR setting {}".format(setting)
		else:
			return "OK setting {} -> {}".format(setting, val)

	def set_brightness(self, bright):
		self.brightness = _parse8bit(bright)
		return self.brightness

	def set_inside_brightness(self, bright):
		self.inside_brightness = _parse8bit(bright)
		self.update_required = True
		return self.inside_brightness

	def set_edge_brightness(self, bright):
		self.edge_brightness = _parse8bit(bright)
		self.update_required = True
		return self.edge_brightness

	def _set_color(self, i, color):
		if isinstance(color, Colors):
		    color = color.value
		c = self.strip.getPixelColor(i)
		if(i in LEDS_INSIDE):
			color = self.dim_color(color, self.inside_brightness/255.0)
			#self.logger.info('change_inside_brightness: %i, %i', i, color)
		else:
			color = self.dim_color(color, self.edge_brightness/255.0)
		if(c != color):
			self.strip.setPixelColor(i, color)
			self.update_required = True
			# self.logger.info("colors did not match update %i : %i" % (color,c))
		else:
			# self.logger.debug("skipped color update of led %i" % i)
			pass

	def _update(self):
		if(self.update_required):
			self.strip.setBrightness(self.brightness)
			self.strip.show()
			self.update_required = False
			# self.logger.info("state: %s |    flush  !!!", self.state)
		else:
			# self.logger.info("state: %s | no flush   - ", self.state)
			pass

def parse_int(value):
	try:
		return int(float(value))
	except ValueError:
		raise ValueError("Cannot convert value {!r} to int.".format(value))


def _mylinspace(start, stop, count):
	"""A pseudo clone of ``numpy.linspace()``
	Returns an iterator of evenly spaced points between ``start`` and ``stop``, excluding ``stop``.
	Their number is ``count``.

	The ``start`` and ``stop`` can be anything as long as they implement __sub__() between each other,
	and __div__() / __truediv__() with regard to ``count`` (non-null int)
	``count`` is expected to be an ``int`` type.

	Example:

		>>> list(_mylinspace(1, 4, 2))
		[1.0, 4.0]
		>>> list(_mylinspace(1.7, 32, 1))
		[1.7]
		>>> list(_mylinspace(8, -2, 10))
		[8., 7., 6., 5., 4., 3., 2., 1., 0., -1.]
	"""
	step = (stop - start) / count
	i = start
	for _ in range(count):
		yield i
		i += step

def _parse8bit(self, val):
	"""Returns the truncated 32bit representation of an ``int``.

	Example:

	"""
	try:
		return int(val) & 0xff
	except ValueError:
		raise ValueError("Could not parse {} as an 8 bit integer".format(repr(val)))
