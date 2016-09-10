# cli to write to socket

import socket
import sys

def client():
	state = sys.argv[1]

	socket_file = "/var/run/mrbeam_state.sock"
	s = None # socket object

	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	s.connect(socket_file)

	try:
		s.send(state+'\x00')
		print "sent state " + state
		data = s.recv(1024)
		print "recv: " + data
		s.close()
	finally:
		sock.close()


if __name__ == "__main__":
    client()