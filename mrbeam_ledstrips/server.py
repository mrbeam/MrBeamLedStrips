# coding=utf-8
from __future__ import absolute_import
from __future__ import print_function
import argparse
import logging
import sys
import threading
import signal
import code
import traceback
import yaml
import os
import pkg_resources
from .state_animations import LEDs, COMMANDS

SOCK_BUF_SIZE = 4 * 1024

def merge_config(default, config):
    # See octoprint.util.dict_merge
    result = dict()
    for k, v in default.items():
        result[k] = v
        if isinstance(v, dict):
            result[k] = merge_config(v, config[k] if k in config else dict())
        else:
            if k in config:
                result[k] = config[k]

    return result


def get_config(path):

    default_config = dict(
        socket='/var/run/mrbeam_ledstrips.sock',
        led_count = 46,          # Number of LED pixels.
        gpio_pin = 18,           # SPI:10, PWM: 18
        led_freq_hz = 800000,    # LED signal frequency in Hz (usually 800kHz)
        # led_freq_hz = 1200000, # for spreading on SPI pin....
        led_dma = 10,            # DMA channel to use for generating signal. This produced a problem after changing to a
        				# newer kernerl version (https://github.com/jgarff/rpi_ws281x/issues/208). Changing it from
        				# the previous 5 to channel 10 solved it.
        led_brigthness = 255,    # 0..255 / Dim if too much power is used.
        led_invert = False,      # True to invert the signal (when using NPN transistor level shift)

        # spread spectrum settings (only effective if gpio_pin is set to 10 (SPI))
        spread_spectrum_enabled          = True,
        spread_spectrum_random           = True,
        spread_spectrum_bandwidth        = 200000,
        spread_spectrum_channel_width    = 9000,
        spread_spectrum_hopping_delay_ms = 50,

        # default frames per second
        frames_per_second = 28,

        # max png file size 30 kB
        max_png_size = 30 * 1024
    )

    import os
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                file_config = yaml.safe_load(f)
        except:
            logging.get_logger(__name__).warning("error loading config file")
            return default_config
        else:
            return merge_config(default_config, file_config)
    else:
            return default_config


class Server(object):
	def __init__(self, server_address, led_config):
		self.logger = logging.getLogger(__name__)
		self.analytics = led_config.get('enable_analytics', False)
		if self.analytics:
			from . import analytics
			analytics.hook_into_logger(self.logger)

		def exception_logger(exc_type, exc_value, exc_tb):
			self.logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

		sys.excepthook = exception_logger
		self.listen()

		self.server_address = server_address

		# we need to make sure that client messages and link events are never handled concurrently, so we synchronize via
		# this mutex
		self.mutex = threading.RLock()
		self.leds = LEDs(led_config)
		print("initialized")
		signal.signal(signal.SIGTERM, self.leds.clean_exit)  # switch off the LEDs on exit

	# https://stackoverflow.com/a/133384/2631798
	def debug(self, sig, frame):
		"""Interrupt running process, and provide a python prompt for
		interactive debugging."""
		self.logger.info('debug() frame: %s', traceback.extract_stack())

		# this doesn't work for me so far....
		d = {'_frame': frame}  # Allow access to frame object.
		d.update(frame.f_globals)  # Unless shadowed by global
		d.update(frame.f_locals)

		i = code.InteractiveConsole(d)
		message = "Signal received : entering python shell.\nTraceback:\n"
		message += ''.join(traceback.format_stack(frame))
		i.interact(message)

	def listen(self):
		signal.signal(signal.SIGUSR1, self.debug)  # Register handler

	def _socket_monitor(self, server_address, callback):

		import socket
		import os
		try:
			os.unlink(server_address)
		except OSError:
			if os.path.exists(server_address):
				raise

		self.logger.info('Starting up socket monitor on %s...' % server_address)

		sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		sock.bind(server_address)
		os.chmod(server_address, 438)

		sock.listen(1)

		try:
			while True:
				self.logger.info('Waiting for connection on socket...')
				connection, client_address = sock.accept()
				self.logger.info('Client connected...')

				# with self.mutex:
				try:
					with connection:
						data = str(connection.recv(SOCK_BUF_SIZE), "utf8").strip()

						self.logger.info('Command: %s' % data)
						response = str(callback(data))

						self.logger.info('Send: %s' % response)
						connection.sendall(bytes(response, "utf8"))

				except Exception:
					self.logger.exception('Got an error while processing message from client, aborting')

					try:
						connection.sendall(str(ErrorResponse("error while processing message from client")) + '\x00')
					except:
						pass
		except (KeyboardInterrupt, SystemExit):
			pass
		except Exception:
			self.logger.exception("Exception in socket monitor: ")
		finally:
			sock.close()
			os.unlink(server_address)
			self.leds.clean_exit(signal.SIGTERM, None)

	def start(self):
		self.logger.info("### Starting up ledstrip server v%s...", get_version_string())
		self.animation = threading.Thread(target=self.leds.loop, kwargs=dict())
		self.animation.daemon = True
		self.animation.name = "StateAnimations"
		self.animation.start()
		self._socket_monitor(self.server_address, callback=self.on_state_change)

	def on_state_change(self, state):
		response = "ERRROR"
		if (state in ('info', '?')):
			info = self.get_info()
			self.logger.info(info)
			response = info
		else:
			response = self.leds.change_state(state)
		return response

	def get_info(self):
		info = ["INFO: "]

		info.append("version: {}".format(get_version_string()))
		info.append(
			"LEDS: state:{state}, frame:{frame}, fps:{fps}, frame_duration:{frame_duration}, job_progress:{job_progress}, brightness:{brightness}, edge_brightness:{edge_brightness}, inside_brightness:{inside_brightness}".format(
				state=self.leds.state,
				frame=self.leds.frame,
				fps=self.leds.fps,
				frame_duration=self.leds.frame_duration,
				job_progress=self.leds.job_progress,
				brightness=self.leds.brightness, 
				edge_brightness=self.leds.edge_brightness, 
				inside_brightness=self.leds.inside_brightness, 
				))

		info.append("LEDS config: {}".format(self.leds.config))

		thr = threading.enumerate()
		info.append("THREADS: ({num}) {threads}".format(num=len(thr), threads=thr))

		my_commands = []
		for c in COMMANDS:
			my_commands.append(COMMANDS[c][0])
		my_commands.sort()
		info.append("COMMANDS: {}".format(' '.join(my_commands)))
		info.append('')

		return "\n".join(info)


def get_version_string():
	try:
		return pkg_resources.get_distribution("mrbeam_ledstrips").version
	except:
		return '-'


def start_server(config):
	s = Server(config["socket"], config)
	s.start()


def server():
	parser = argparse.ArgumentParser(parents=[])

	parser.add_argument("-c", "--config", default="/etc/mrbeam_ledstrips.yaml", help="Config file location")
	parser.add_argument("-f", "--foreground", action="store_true", help="Run in foreground instead of as daemon")
	parser.add_argument("-p", "--pid", default="/var/run/mrbeam_ledstrips.pid",
	                    help="Pidfile to use for demonizing, defaults to /var/run/ledstrips.pid")
	parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
	parser.add_argument("-q", "--quiet", action="store_true", help="Disable console output")
	parser.add_argument("-v", "--version", action="store_true", help="Display version information and exit")
	parser.add_argument("--logfile", default="/var/log/mrbeam_ledstrips.log",
	                    help="Location of logfile, defaults to /var/log/ledstrips.log")
	parser.add_argument("--daemon", choices=["stop", "status"],
	                    help="Control the ledstrips daemon, supported arguments are 'stop' and 'status'.")

	args = parser.parse_args()

	if args.version:
		import sys
		print("Version: %s" % 0.1)
		sys.exit(0)

	if args.daemon:
		import os
		import sys
		from .daemon import Daemon

		if args.daemon == "stop":
			# stop the daemon
			daemon = Daemon(pidfile=args.pid)
			daemon.stop()
			sys.exit(0)
		elif args.daemon == "status":
			# report the status of the daemon
			if os.path.exists(args.pid):
				with open(args.pid, "r") as f:
					pid = f.readline().strip()

				if pid:
					if os.path.exists(os.path.join("/proc", pid)):
						print("Running (Pid %s)" % pid)
					sys.exit(0)
			print("Not running")
			sys.exit(0)

	# configure logging
	logging_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
	logging.basicConfig(format=logging_format, filename=args.logfile,
	                    level=logging.DEBUG if args.debug else logging.INFO)
	if not args.quiet:
		console_handler = logging.StreamHandler()
		console_handler.formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		console_handler.level = logging.DEBUG if args.debug else logging.INFO
		logging.getLogger('').addHandler(console_handler)

	config = get_config(args.config)

	if args.foreground:
		# start directly instead of as daemon
		start_server(config)

	else:
		# start as daemon
		from .daemon import Daemon

		class ServerDaemon(Daemon):
			def run(self):
				start_server(config)

		daemon = ServerDaemon(pidfile=args.pid, umask=0o02)
		name = "Server"
		daemon.start()


if __name__ == '__main__':
	server()


class InvalidConfig(Exception):
	pass
