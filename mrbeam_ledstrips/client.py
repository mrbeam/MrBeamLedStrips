# coding=utf-8
# cli to write to socket

import socket
import sys
from . import __version__

CLIENT_TIMEOUT = 5 # in seconds

def client():

	if len(sys.argv) <= 1:
		print("MrBeam LED Strips v{}".format(__version__))
		sys.exit(0)


	state = sys.argv[1]

	socket_file = "/var/run/mrbeam_ledstrips.sock"
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	s.settimeout(CLIENT_TIMEOUT)
	try:
		s.connect(socket_file)
	except socket.error as msg:
		print("socket error: %s " % msg)
		print("Unable to connect to: %s. Daemon running?" % socket_file)
		sys.exit(1)

	try:
		print("> " + state)
		s.sendall(bytes(state, "utf8"))
		data = s.recv(4*1024)
		print("< " + str(data, "utf8"))

	finally:
		s.close()

if __name__ == "__main__":
	client()
