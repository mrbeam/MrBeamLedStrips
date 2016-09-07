# Library to visualize the Mr Beam Machine States with the SK6812 LEDs
# Author: Teja Philipp (teja@mr-beam.org)
# based on https://github.com/jgarff/rpi_ws281x

import time
import signal
import sys
from neopixel import *

import socket
import os, os.path
import time

# LED strip configuration:
LED_COUNT      = 36      # Number of LED pixels.
GPIO_PIN        = 18      # Pin #12 on the RPi. GPIO pin must support PWM
LED_FREQ_HZ    = 800000  # LED signal frequency in Hz (usually 800kHz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # 0..255 / Dim if too much power is used.
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0
LED_STRIP      = ws.SK6812_STRIP # alternatives: ws.SK6812_STRIP_RGBW, ws.SK6812W_STRIP

SOCKET = "/var/run/mrbeam_state.sock"

# Serial numbering of LEDs on the Mr Beam modules
# order is top -> down
LEDS_RIGHT_BACK = [0,1,2,3,4,5,6]
LEDS_RIGHT_FRONT = [7,8,9,10,11,12,13]
LEDS_LEFT_FRONT = [22,23,24,25,26,27,28]
LEDS_LEFT_BACK = [29,30,31,32,33,34,35]

# order is right -> left
LEDS_IN_RIGHT = [14,15,16,17]
LEDS_IN_LEFT = [18,19,20,21]

# color definitions
OFF = Color(0,0,0)
WHITE = Color(255,255,255)
RED = Color(255,0,0)
GREEN = Color(0,255,0)
BLUE = Color(0,0,255)
YELLOW = Color(255,200,0)
 
def clean_exit(signal, frame):
	print 'shutting down'
	for i in range(strip.numPixels()):
		strip.setPixelColor(i, OFF)
		strip.show()
	sys.exit(0)
 
def off():
	for i in range(256,0,-16):
		strip.setBrightness(i-1);
		#strip.show()
		time.sleep(20/1000.0)
		
	for i in range(strip.numPixels()):
		strip.setPixelColor(i, OFF)
		strip.show()

 

# pulsing red from the center
def warning(frame):
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	fwd_bwd_range = range(l) + range(l-1,-1,-1)
	
	frames = [
		[0,0,0,0,0,0,0],
		[0,0,0,1,0,0,0],
		[0,0,1,1,1,0,0],
		[0,1,1,1,1,1,0],
		[1,1,1,1,1,1,1],
		[1,1,1,1,1,1,1],
		[0,1,1,1,1,1,0],
		[0,0,1,1,1,0,0],
		[0,0,0,1,0,0,0]
	]
	
	f = frame % len(frames)
	
	for r in involved_registers:
		for i in range(l):
			if(frames[f][i] >= 1):
				strip.setPixelColor(r[i], RED)
			else:
				strip.setPixelColor(r[i], OFF)
	strip.show()


# alternating upper and lower yellow 
def pause(frame):
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	fwd_bwd_range = range(l) + range(l-1,-1,-1)
	
	frames = [
		[1,1,1,0,0,0,0],
		[0,0,0,0,1,1,1]
	]
	
	f = frame/40 % len(frames)
	
	for r in involved_registers:
		for i in range(l):
			if(frames[f][i] >= 1):
				strip.setPixelColor(r[i], YELLOW)
			else:
				strip.setPixelColor(r[i], OFF)
	strip.show()



def progress(value, frame, color_done=WHITE, color_drip=BLUE):
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	c = frame/5 % l
	illuminate()

	for r in involved_registers:
		for i in range(l):
			
			bottom_up_idx = l-i-1
			threshold = value / 100.0 * (l-1)
			if threshold < bottom_up_idx: 
				if i == c:
					strip.setPixelColor(r[i], color_drip)
				else:
					strip.setPixelColor(r[i], OFF)
					
			else:
				strip.setPixelColor(r[i], color_done)

	strip.show()



# pauses the progress animation with a pulsing drip
def progress_pause(value, frame, color_done=WHITE, color_drip=BLUE):
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	f_count = 64.0
	dim = abs((frame % f_count*2) - (f_count-1))/f_count 
	illuminate()

	for r in involved_registers:
		for i in range(l):
			
			bottom_up_idx = l-i-1
			threshold = value / 100.0 * (l-1)
			if threshold < bottom_up_idx: 
				if i == bottom_up_idx / 2:
					color = dim_color(color_drip, dim)
					strip.setPixelColor(r[i], color)
				else:
					strip.setPixelColor(r[i], OFF)
					
			else:
				strip.setPixelColor(r[i], color_done)

	strip.show()


def drip(counter, color=BLUE):
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	c = counter % l

	for r in involved_registers:
		for i in range(l):
			if i == c:
				strip.setPixelColor(r[i], color)
			else:
				strip.setPixelColor(r[i], OFF)

	strip.show()


def idle(frame, color=WHITE):
	leds = LEDS_RIGHT_BACK + list(reversed(LEDS_RIGHT_FRONT)) + LEDS_IN_RIGHT + LEDS_IN_LEFT + LEDS_LEFT_FRONT + list(reversed(LEDS_LEFT_BACK));
	c = frame % len(leds)
	for i in range(len(leds)):
		if(i == c):
			strip.setPixelColor(leds[i], color)
		else:
			strip.setPixelColor(leds[i], OFF)
	strip.show()

def job_finished(frame):
	illuminate()
	involved_registers = [LEDS_RIGHT_FRONT,LEDS_LEFT_FRONT,LEDS_RIGHT_BACK,LEDS_LEFT_BACK];
	l = len(LEDS_RIGHT_BACK)
	
	f = frame % (100 + l*2)	
		
	if(f < l*2):
		for i in range(f/2-1,-1,-1):
			for r in involved_registers:
				strip.setPixelColor(r[i], GREEN)
		
	else:
		for i in range(l-1,-1,-1):
			for r in involved_registers:
				brightness = 1 - (f - 2*l)/100.0
				col = dim_color(GREEN, brightness)
				strip.setPixelColor(r[i], col)
		
			
	strip.show()


def illuminate(color = WHITE):
	leds = LEDS_IN_RIGHT + LEDS_IN_LEFT
	l = len(leds)
	for i in range(l):
		strip.setPixelColor(leds[i], color)		
	strip.show()

def dim_color(col, brightness):
	r = (col & 0xFF0000) >> 16;
	g = (col & 0x00FF00) >> 8;
	b = (col & 0x0000FF);
	return Color(int(r*brightness), int(g*brightness), int(b*brightness))


def demo_state(frame):
	f = frame % 4300
	if(f < 1000):
		return "idle"
	elif(f < 2000):
		return "progress:" + str((f-1000)/20)
	elif(f < 2200):
		return "pause:50"
	elif(f < 3200):
		return "progress:"+ str((f-1200)/20)
	elif(f < 4000):
		return "job_finished"
	else:
		return "warning"
		
# Main program logic follows:
if __name__ == '__main__':
	# Create NeoPixel object with appropriate configuration.
	strip = Adafruit_NeoPixel(LED_COUNT, GPIO_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, LED_STRIP)
	strip.begin() # Init the LED-strip
	signal.signal(signal.SIGTERM, clean_exit) # switch off the LEDs on exit



	if os.path.exists( SOCKET ):
	  os.remove( SOCKET )

	print "Opening socket..."

	server = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
	server.bind(SOCKET)
	server.listen(5)

	print "Listening..."
	print ('Press Ctrl-C to quit.')
	try:
		frame = 0
		pause(frame)
		while True:
			conn, addr = server.accept()
		print 'accepted connection'

		while True:
			# read state
			data = conn.recv( 1024 )
			
			if not data:
				state_string = demo_state(frame)
			else:
				state_string = data
			
			s = state_string.split(':')
			state = s[0]
			param = int(s[1]) if len(s) > 1 else 0
			
			if(state == "warning"):
				warning(frame);
			elif(state == "progress"):
				progress(param, frame)
			elif(state == "job_finished"):
				job_finished(frame)
			elif(state == "pause"):
				progress_pause(param, frame)
			elif(state == "off"):
				off()
			elif(state == "quit"):
				break
			else:
				idle(frame)
				
			frame += 1
			time.sleep(20/1000.0)
			
	except KeyboardInterrupt:
		clean_exit(signal.SIGTERM, None)
		server.close()
		os.remove( SOCKET )

		print "Good bye"

