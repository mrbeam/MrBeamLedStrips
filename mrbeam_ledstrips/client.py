# cli to write to socket

import socket
import sys

def client():
	state = sys.argv[1]

	socket_file = "/var/run/mrbeam_ledstrips.sock"
	s = None # socket object

	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		s.connect(socket_file)
	except socket.error as msg:
		print "socket error: %s " % msg
		print "Unable to connect to: %s. Daemon running?" % socket_file
		sys.exit(1)

	try:
		s.send(state+'\x00')
		print "sent state " + state
		data = s.recv(1024)
		print "recv: " + data
		s.close()		
	finally:
		s.close()


if __name__ == "__main__":
    client()