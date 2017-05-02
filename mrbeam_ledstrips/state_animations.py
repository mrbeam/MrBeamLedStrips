# Library to visualize the Mr Beam Machine States with the SK6812 LEDs
# Author: Teja Philipp (teja@mr-beam.org)
# using https://github.com/jgarff/rpi_ws281x

import signal
from neopixel import *
import time
import sys
import logging

LED_COUNT = 46        # Number of LED pixels.
GPIO_PIN = 18         # Pin #12 on the RPi. GPIO pin must support PWM
LED_FREQ_HZ = 800000  # LED signal frequency in Hz (usually 800kHz)
LED_DMA = 5           # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255  # 0..255 / Dim if too much power is used.
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)

# LED strip configuration:
# Serial numbering of LEDs on the Mr Beam modules
# order is top -> down
LEDS_RIGHT_BACK = [0, 1, 2, 3, 4, 5, 6]
LEDS_RIGHT_FRONT = [7, 8, 9, 10, 11, 12, 13]
LEDS_LEFT_FRONT = [32, 33, 34, 35, 36, 37, 38]
LEDS_LEFT_BACK = [39, 40, 41, 42, 43, 44, 45]

# order is right -> left
LEDS_INSIDE = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]

# color definitions
OFF = Color(0, 0, 0)
WHITE = Color(255, 255, 255)
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
BLUE = Color(0, 0, 255)
YELLOW = Color(255, 200, 0)
ORANGE = Color(226, 83, 3)


class LEDs():
	def __init__(self):
		self.logger = logging.getLogger(__name__)
		# Create NeoPixel object with appropriate configuration.
		self.strip = Adafruit_NeoPixel(LED_COUNT, GPIO_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)
		self.strip.begin()  # Init the LED-strip
		self.state = "_listening"
		self.past_states = []
		signal.signal(signal.SIGTERM, self.clean_exit)  # switch off the LEDs on exit
		self.job_progress = 0
		self.brightness = 255

	def change_state(self, state):
		print("state change " + str(self.state) + " => " + str(state))
		self.logger.info("state change " + str(self.state) + " => " + str(state))
		if self.state != state:
			self.past_states.append(self.state)
			while len(self.past_states) > 10:
				self.past_states.pop(0)
		self.state = state
		self.frame = 0

	def clean_exit(self, signal, msg):
		print 'shutting down, signal was: %s' % signal
		self.logger.info("shutting down, signal was: %s", signal)
		self.off()
		sys.exit(0)

	def off(self):
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, OFF)
		self.strip.show()

	def fade_off(self, fps=50):
		for i in range(self.brightness, -1, -1):
			self.strip.setBrightness(i)
			self.strip.show()
			time.sleep(1.0/fps)

		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, OFF)
			self.strip.show()

	# pulsing red from the center
	def error(self, frame):
		self.flash(frame)

	def flash(self, frame, color=RED, fps=50):
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

		div = 100/fps
		f = frame/div % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self.strip.setPixelColor(r[i], color)
				else:
					self.strip.setPixelColor(r[i], OFF)
		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def listening(self, frame, fps=50):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		div = 100/fps
		f_count = 64.0
		dim = abs((frame/div % f_count*2) - (f_count-1))/f_count

		color = self.dim_color(ORANGE, dim)
		for r in involved_registers:
			for i in range(l):
				if i == l-1:
					self.strip.setPixelColor(r[i], color)
				else:
					self.strip.setPixelColor(r[i], OFF)
		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def all_on(self):
		involved_registers = [LEDS_INSIDE, LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]

		color = WHITE
		for r in involved_registers:
			l = len(r)
			for i in range(l):
				self.strip.setPixelColor(r[i], color)
		self.strip.setBrightness(255)
		self.strip.show()

	# alternating upper and lower yellow
	def warning(self, frame, fps=2):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		fwd_bwd_range = range(l) + range(l-1, -1, -1)

		frames = [
			[1, 1, 1, 0, 0, 0, 0],
			[0, 0, 0, 0, 1, 1, 1]
		]

		div = 100/fps
		f = frame/div % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self.strip.setPixelColor(r[i], YELLOW)
				else:
					self.strip.setPixelColor(r[i], OFF)
		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def progress(self, value, frame, color_done=WHITE, color_drip=BLUE, fps=20):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		div = 100/fps
		c = frame/div % l

		self.illuminate()

		for r in involved_registers:
			for i in range(l):

				bottom_up_idx = l-i-1
				threshold = value / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == c:
						self.strip.setPixelColor(r[i], color_drip)
					else:
						self.strip.setPixelColor(r[i], OFF)

				else:
					self.strip.setPixelColor(r[i], color_done)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	# pauses the progress animation with a pulsing drip
	def progress_pause(self, value, frame, breathing=True, color_done=WHITE, color_drip=BLUE, fps=50):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f_count = 64.0
		div = 100/fps
		dim = abs((frame/div % f_count*2) - (f_count-1))/f_count if breathing else 1
		self.illuminate()

		for r in involved_registers:
			for i in range(l):
				bottom_up_idx = l-i-1
				threshold = value / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == bottom_up_idx / 2:
						color = self.dim_color(color_drip, dim)
						self.strip.setPixelColor(r[i], color)
					else:
						self.strip.setPixelColor(r[i], OFF)

				else:
					self.strip.setPixelColor(r[i], color_done)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def drip(self, frame, color=BLUE, fps=50):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		div = 100/fps
		c = frame/div % l

		for r in involved_registers:
			for i in range(l):
				if i == c:
					self.strip.setPixelColor(r[i], color)
				else:
					self.strip.setPixelColor(r[i], OFF)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def idle(self, frame, color=WHITE, fps=50):
		leds = LEDS_RIGHT_BACK + list(reversed(LEDS_RIGHT_FRONT)) + LEDS_INSIDE + LEDS_LEFT_FRONT + list(reversed(LEDS_LEFT_BACK))
		div = 100/fps
		c = frame/div % len(leds)
		for i in range(len(leds)):
			if i == c:
				self.strip.setPixelColor(leds[i], color)
			else:
				self.strip.setPixelColor(leds[i], OFF)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def job_finished(self, frame, fps=50):
		self.illuminate()
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		div = 100/fps
		f = frame/div % (100 + l*2)

		if f < l*2:
			for i in range(f/2-1, -1, -1):
				for r in involved_registers:
					self.strip.setPixelColor(r[i], GREEN)

		else:
			for i in range(l-1, -1, -1):
				for r in involved_registers:
					brightness = 1 - (f - 2*l)/100.0
					col = self.dim_color(GREEN, brightness)
					self.strip.setPixelColor(r[i], col)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def shutdown(self, frame):
		self.static_color(RED)

	def shutdown_prepare(self, frame):
		f = frame
		on = f % 20 > 5
		if on:
			if (frame < 500):
				brightness = int(255 - (f / 2))
				myColor = self.dim_color(RED, brightness)
			else:
				myColor = RED
		else:
			myColor = OFF
		self.static_color(myColor)

	def illuminate(self, color=WHITE):
		leds = LEDS_INSIDE
		l = len(leds)
		for i in range(l):
			self.strip.setPixelColor(leds[i], color)

		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def static_color(self, color=WHITE):
		leds = LEDS_INSIDE + LEDS_RIGHT_FRONT + LEDS_LEFT_FRONT + LEDS_RIGHT_BACK + LEDS_LEFT_BACK
		for i in range(len(leds)):
			self.strip.setPixelColor(leds[i], color)
		self.strip.setBrightness(self.brightness)
		self.strip.show()

	def dim_color(self, col, brightness):
		r = (col & 0xFF0000) >> 16
		g = (col & 0x00FF00) >> 8
		b = (col & 0x0000FF)
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


	def rollback(self, steps=1):
		if len(self.past_states) >= steps:
			for x in range(0, steps):
				old_state = self.past_states.pop()
				self.logger.info("Rolleback step %s/%s: rolling back from '%s' to '%s'", x, steps, self.state, old_state)
				self.state = old_state
		else:
			self.logger.warn("Rolleback: Can't rollback %s steps, max steps: %s", steps, len(self.past_states))
			if len(self.past_states) >= 1:
				self.state = self.past_states.pop()
			else:
				self.state = "_listening"
			self.logger.warn("Rolleback: fallback to %s", self.state)

	def loop(self):
		try:
			self.frame = 0
			while True:
				data = self.state
				if not data:
					state_string = "off"  # self.demo_state(self.frame)
				else:
					state_string = data

				# split params from state string
				s = state_string.split(':')
				state = s[0]
				param = int(s[1]) if len(s) > 1 else 0

				# Daemon listening
				if state == "_listening":
					self.listening(self.frame)

				# test purposes
				elif state == "all_on":
					self.all_on()

				elif state == "rollback":
					self.rollback(2)

				# Server
				elif state == "Startup":
					self.idle(self.frame, color=Color(20, 20, 20), fps=10)
				elif state == "ClientOpened":
					self.idle(self.frame, fps=40)
				elif state == "ClientClosed":
					self.idle(self.frame, color=Color(20, 20, 20), fps=10)

				# Machine
				elif state == "Connected":
					self.idle(self.frame)
				elif state == "Disconnected":
					self.idle(self.frame, fps=10)
				elif state == "Error":
					self.error(self.frame)
				elif state == "ShutdownPrepare":
					self.shutdown_prepare(self.frame)
				elif state == "Shutdown":
					self.shutdown(self.frame)
				elif state == "ShutdownPrepareCancel":
					self.rollback(2)

				# File Handling
				elif state == "Upload":
					self.warning(self.frame)

				# Laser Job
				elif state == "PrintStarted":
					self.progress(0, self.frame)
				elif state == "PrintDone":
					self.job_progress = 0
					self.job_finished(self.frame)
				elif state == "PrintCancelled":
					self.job_progress = 0
					self.fade_off()
				elif state == "PrintPaused":
					self.progress_pause(self.job_progress, self.frame)
				elif state == "PrintPausedTimeout":
					self.progress_pause(self.job_progress, self.frame, False)
				elif state == "PrintPausedTimeoutBlock":
					if self.frame > 50:
						self.change_state("PrintPausedWaiting")
					else:
						self.progress_pause(self.job_progress, self.frame, False, color_drip=RED)
				elif state == "PrintResumed":
					self.progress(self.job_progress, self.frame)
				elif state == "progress":
					self.job_progress = param
					self.progress(param, self.frame)
				elif state == "job_finished":
					self.job_finished(self.frame)
				elif state == "pause":
					self.progress_pause(param, self.frame)
				elif state == "ReadyToPrint":
					self.flash(self.frame, color=BLUE, fps=20)
				elif state == "ReadyToPrintCancel":
					self.idle(self.frame)

				# Slicing
				elif state == "SlicingStarted":
					self.progress(param, self.frame, color_done=BLUE, color_drip=WHITE)
				elif state == "SlicingDone":
					self.progress(param, self.frame, color_done=BLUE, color_drip=WHITE)
				elif state == "SlicingCancelled":
					self.idle(self.frame)
				elif state == "SlicingFailed":
					self.fade_off()
				elif state == "SlicingProgress":
					self.progress(param, self.frame, color_done=BLUE, color_drip=WHITE)

				# Settings
				elif state == "SettingsUpdated":
					if self.frame > 50:
						self.rollback()
					else:
						self.flash(self.frame, color=WHITE)

				# other
				elif state == "off":
					self.off()
				elif state == "brightness":
					if param > 255:
						param = 255
					elif param < 0:
						param = 0
					self.brightness = param
				elif state == "all_red":
					self.static_color(RED)
				elif state == "all_green":
					self.static_color(GREEN)
				elif state == "all_blue":
					self.static_color(BLUE)
				else:
					self.idle(self.frame, color=Color(20, 20, 20), fps=10)

				self.frame += 1
				time.sleep(0.01)
				# time.sleep(10/1000.0)

		except KeyboardInterrupt:
			self.logger.exception("KeyboardInterrupt Exception in animation loop:")
			self.clean_exit(signal.SIGTERM, None)
		except:
			self.logger.exception("Some Exception in animation loop:")
			print("Some Exception in animation loop:")