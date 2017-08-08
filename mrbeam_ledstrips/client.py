# cli to write to socket

import socket
import sys
import pkg_resources


def client():

	if len(sys.argv) <= 1:
		print "MrBeam LED Strips v{}".format(get_version_string())
		sys.exit(0)


	state = sys.argv[1]

	socket_file = "/var/run/mrbeam_ledstrips.sock"
	s = None  # socket object

	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	s.settimeout(2)
	try:
		s.connect(socket_file)
	except socket.error as msg:
		print "socket error: %s " % msg
		print "Unable to connect to: %s. Daemon running?" % socket_file
		sys.exit(1)

	try:
		s.send(state+'\x00')
		print "> " + state
		data = s.recv(5000)
		print "< " + data
		s.close()		
	finally:
		s.close()


def get_version_string():
	try:
		return pkg_resources.get_distribution("mrbeam_ledstrips").version
	except:
		return '-'

if __name__ == "__main__":
	client()
