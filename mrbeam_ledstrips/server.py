from __future__ import absolute_import
from __future__ import print_function
import argparse
import logging
import sys
import threading
import signal
import yaml
import os
from .state_animations import LEDs, COMMANDS, get_default_config


class Server(object):
	def __init__(self, server_address, led_config):
		self.logger = logging.getLogger(__name__)

		def exception_logger(exc_type, exc_value, exc_tb):
			self.logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

		sys.excepthook = exception_logger

		self.server_address = server_address

		# we need to make sure that client messages and link events are never handled concurrently, so we synchronize via
		# this mutex
		self.mutex = threading.RLock()
		self.leds = LEDs(led_config)
		print("initialized")
		signal.signal(signal.SIGTERM, self.leds.clean_exit)  # switch off the LEDs on exit

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

				# with self.mutex:
				try:
					buffer = []
					while True:
						chunk = connection.recv(16)
						if chunk:
							# self.logger.info('Recv: %r' % chunk)
							buffer.append(chunk)
							if chunk.endswith('\x00') or chunk.endswith("\n"):
								break

					data = ''.join(buffer).strip()[:-1]

					ret = False
					result = 'unknown event'

					self.logger.info('Command: %s' % data)
					response = callback(data)

					self.logger.info('Send: %s' % str(response))
					connection.sendall(str(response) + '\x00')

				except:
					self.logger.exception('Got an error while processing message from client, aborting')

					try:
						connection.sendall(str(ErrorResponse("error while processing message from client")) + '\x00')
					except:
						pass
		except KeyboardInterrupt:
			sock.close()
			os.unlink(server_address)
			self.leds.clean_exit(signal.SIGTERM, None)

	def start(self):
		self.logger.info("### Starting up ledstrip server...")
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

		info.append(
			"LEDS: state:{state}, frame:{frame}, fps:{fps}, frame_duration:{frame_duration}, job_progress:{job_progress}, brightness:{brightness}".format(
				state=self.leds.state,
				frame=self.leds.frame,
				fps=self.leds.fps,
				frame_duration=self.leds.frame_duration,
				job_progress=self.leds.job_progress,
				brightness=self.leds.brightness))

		info.append("LEDS config: {}".format(self.leds.config))

		thr = threading.enumerate()
		info.append("THREADS: ({num}) {threads}".format(num=len(thr), threads=thr))

		my_commands = []
		for c in COMMANDS:
			my_commands.append(COMMANDS[c][0])
		info.append("COMMANDS: {}".format(' '.join(my_commands)))

		return "\n".join(info)


def parse_configfile(configfile):
	if not os.path.exists(configfile):
		return None

	mandatory = ("socket")

	default_config = get_default_config()
	default_config['socket'] = "/var/run/mrbeam_ledstrips.sock"

	try:
		with open(configfile, "r") as f:
			config = yaml.safe_load(f)
	except:
		raise InvalidConfig("error loading config file")

	def merge_config(default, config, mandatory, prefix=None):
		result = dict()
		for k, v in default.items():
			result[k] = v

			prefixed_key = "%s.%s" % (prefix, k) if prefix else k
			if isinstance(v, dict):
				result[k] = merge_config(v, config[k] if k in config else dict(), mandatory, prefixed_key)
			else:
				if k in config:
					result[k] = config[k]

			if result[k] is None and prefixed_key in mandatory:
				raise InvalidConfig("mandatory key %s is missing" % k)
		return result

	return merge_config(default_config, config, mandatory)


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

	default_config = dict(socket='/var/run/mrbeam_ledstrips.sock')
	import copy
	config = copy.deepcopy(default_config)

	configfile = args.config
	if not configfile:
		configfile = "/etc/mrbeam_ledstrips.yaml"

	import os
	if os.path.exists(configfile):
		try:
			config = parse_configfile(configfile)
		except InvalidConfig as e:
			parser.error("Invalid configuration file: " + e.message)

	# validate command line
	if not config["socket"]:
		parser.info("Using Socket default address, overwrite with config file")
	# config["socket"] = ""

	if args.foreground:
		# start directly instead of as daemon
		start_server(config)

	else:
		# start as daemon
		from .daemon import Daemon

		class ServerDaemon(Daemon):
			def run(self):
				start_server(config)

		daemon = ServerDaemon(pidfile=args.pid, umask=002)
		name = "Server"
		daemon.start()


if __name__ == '__main__':
	server()


class InvalidConfig(Exception):
	pass
