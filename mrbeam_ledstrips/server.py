from __future__ import absolute_import
from __future__ import print_function
import argparse
import logging
import sys
import threading
import signal
from state_animations import LEDs



class Server(object):

	def __init__(self, server_address=None):
		

		self.logger = logging.getLogger(__name__)
		def exception_logger(exc_type, exc_value, exc_tb):
			self.logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
		sys.excepthook = exception_logger

		self.server_address = server_address

		# we need to make sure that client messages and link events are never handled concurrently, so we synchronize via
		# this mutex
		self.mutex = threading.RLock()
		self.leds = LEDs()
		print("initialized")
		signal.signal(signal.SIGTERM, self.leds.clean_exit) # switch off the LEDs on exit


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

				#with self.mutex:
					try:
						buffer = []
						while True:
							chunk = connection.recv(16)
							if chunk:
								self.logger.info('Recv: %r' % chunk)
								buffer.append(chunk)
								if chunk.endswith('\x00') or chunk.endswith("\n"):
									break

						data = ''.join(buffer).strip()[:-1]

						ret = False
						result = 'unknown event'

						self.logger.info('data: %s' % data)
						message = data
						ret, result = callback(message)

						if ret:
							response = "OK"
						else:
							response = "Error:"+result

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
		self.animation.start()
		self._socket_monitor(self.server_address, callback=self.on_state_change)
		
	def on_state_change(self, state):
		print("new State: "+state)
		self.leds.change_state(state)
		return True, None



def start_server(config):
	kwargs = dict(
				  server_address=config["socket"],
				  )
	s = Server( ** kwargs)
	s.start()


def server():
	parser = argparse.ArgumentParser(parents=[])


	parser.add_argument("-c", "--config", default="/etc/ledstrips.yaml", help="Config file location")
	parser.add_argument("-f", "--foreground", action="store_true", help="Run in foreground instead of as daemon")
	parser.add_argument("-p", "--pid", default="/var/run/ledstrips.pid", help="Pidfile to use for demonizing, defaults to /var/run/ledstrips.pid")
	parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
	parser.add_argument("-q", "--quiet", action="store_true", help="Disable console output")
	parser.add_argument("-v", "--version", action="store_true", help="Display version information and exit")
	parser.add_argument("--logfile", default="/var/log/ledstrips.log", help="Location of logfile, defaults to /var/log/ledstrips.log")
	parser.add_argument("--daemon", choices=["stop", "status"], help="Control the ledstrips daemon, supported arguments are 'stop' and 'status'.")

	args = parser.parse_args()

	if args.version:
		import sys
		print("Version: %s" % 0.1)
		sys.exit(0)

	if args.daemon:
		import os
		import sys
		from daemon import Daemon

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
			print ("Not running")
			sys.exit(0)

	# configure logging
	logging_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
	logging.basicConfig(format=logging_format, filename=args.logfile, level=logging.DEBUG if args.debug else logging.INFO)
	if not args.quiet:
		console_handler = logging.StreamHandler()
		console_handler.formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		console_handler.level = logging.DEBUG if args.debug else logging.INFO
		logging.getLogger('').addHandler(console_handler)

	default_config = dict(socket='/var/run/mrbeam_state.sock')
	import copy
	config = copy.deepcopy(default_config)

	configfile = args.config
	if not configfile:
		configfile = "/etc/ledstrips.yaml"

	import os
	if os.path.exists(configfile):
		try:
			config = parse_configfile(configfile)
		except InvalidConfig as e:
			parser.error("Invalid configuration file: " + e.message)

	# validate command line
	if not config["socket"]:
		parser.info("Using Socket default address, overwrite with config file")
		#config["socket"] = ""

	if args.foreground:
		# start directly instead of as daemon
		start_server(config)

	else:
		# start as daemon
		from daemon import Daemon

		class ServerDaemon(Daemon):
			def run(self):
				start_server(config)

		daemon = ServerDaemon(pidfile=args.pid, umask=002)
		daemon.start()


if __name__ == '__main__':
	server()

