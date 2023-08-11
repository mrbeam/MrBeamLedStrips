# coding=utf-8
from __future__ import absolute_import

import threading
import time
import logging
import json
import subprocess
import os
import pwd
import sys
import types
import traceback
from inspect import getframeinfo, stack
from . import __version__


"""
How to integrate this mrb analytics module:

- adjust constant COMPONENT_NAME in this file
- in any relevant file:
- - import analytics file as analytics
- - Hook into exception method of your logger: analytics.hook_into_logger(self.logger)
- to send a mesage to analytics, call analytics.send_log_event(level, msg, params)

"""

COMPONENT_NAME = 'mrbeam_ledstrips'


TYPE_LOGEVENT = 'log_event'

RETRIES_WAIT_TIMES = [1.0, 2.0, 5.0, 10.0]

ANALYTICS_THREAD_NAME = 'send_analytics'

_logger = logging.getLogger(__name__)
_analytics_queue = []
_analytics_thread = None


def send_log_event(level, msg, *args, **kwargs):
	"""
	Sends an analytics log_event to octoprint
	:param level:
	:param msg:
	:param args:
	:param kwargs:
	"""
	msg = msg % args if args and msg else msg

	exception_str = None
	stacktrace = None
	if kwargs.get('exc_info', 0):
		exctype, value, tb = sys.exc_info()
		exception_str = "{}: '{}'".format(exctype.__name__ if exctype is not None else None, value)
		stacktrace = traceback.format_tb(tb)

	data=dict(
		level = logging.getLevelName(level),
		msg = msg,
		exception_str=exception_str,
		stacktrace=stacktrace,
	)

	caller = None
	caller_myself = getframeinfo(stack()[0][0])
	i = 1
	while caller is None or caller.filename == caller_myself.filename:
		caller = getframeinfo(stack()[i][0])
		i += 1
	if caller is not None:
		filename = caller.filename
		data.update({
			'hash': hash('{}{}{}'.format(filename, caller.lineno, __version__)),
			'file': filename,
			'line': caller.lineno,
			'function': caller.function,
		})

	_send_analytics(TYPE_LOGEVENT, data)


def hook_into_logger(logger):
	"""
	hooks into .exception an .error methods of the given logger.
	:param logger:
	"""
	logger.exception = types.MethodType(_exception_overwrite, logger)
	logger.error = types.MethodType(_error_overwrite, logger)


def _exception_overwrite(self, msg, *args, **kwargs):
	kwargs['exc_info'] = 1
	self.log(logging.ERROR, msg, *args, **kwargs)
	send_log_event(logging.ERROR, msg, *args, **kwargs)

def _error_overwrite(self, msg, *args, **kwargs):
	analytics = kwargs.pop('analytics', True)
	self.log(logging.ERROR, msg, *args, **kwargs)
	if analytics:
		send_log_event(logging.ERROR, msg, *args, **kwargs)


def _send_analytics(type, data):
	global _logger, _analytics_thread, _analytics_queue
	_logger.debug("Sending analytics data: %s %s", type, data)
	package = dict(
		component=COMPONENT_NAME,
		component_version=___version__,
		type=type,
		data=json.dumps(data, sort_keys=False)
	)

	# a dedicated sending thread prevents the system from beeing flooded with too many analytics data
	_analytics_queue.append(package)

	if not _analytics_thread:
		_analytics_thread = threading.Thread(target=_send_thread, name=ANALYTICS_THREAD_NAME)
		_analytics_thread.daemon = True
		_analytics_thread.start()


def _send_thread():
	global _logger, _analytics_thread, _analytics_queue
	try:
		while _analytics_queue:
			package = _analytics_queue.pop(0)
			retries = len(RETRIES_WAIT_TIMES)
			cmd = ['/home/pi/oprint/bin/octoprint', 'plugins', 'mrbeam:analytics',
			       '{}'.format(package['component']),
			       '{}'.format(package['component_version']),
			       '{}'.format(package['type']),
			       '{}'.format(package['data']),
			       ]

			while retries >= 0:
				res = _exec_as_user(cmd_list=cmd, user_name='pi')
				if res:
					break
				sleep_time = RETRIES_WAIT_TIMES[retries * -1]
				time.sleep(sleep_time)
				retries -= 1
		_analytics_thread = None
		return
	except:
		_logger.log(logging.ERROR, "Exception in _send_thread() ", exc_info=True)


def _exec_as_user(cmd_list, user_name):
	global _logger
	pw_record = pwd.getpwnam(user_name)
	user_name      = pw_record.pw_name
	user_home_dir  = pw_record.pw_dir
	cwd            = pw_record.pw_dir
	user_uid       = pw_record.pw_uid
	user_gid       = pw_record.pw_gid
	env = os.environ.copy()
	env[ 'HOME'     ]  = user_home_dir
	env[ 'LOGNAME'  ]  = user_name
	env[ 'PWD'      ]  = cwd
	env[ 'USER'     ]  = user_name
	process = subprocess.Popen(cmd_list, preexec_fn=_demote(user_uid, user_gid), cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = process.communicate()
	returncode = process.returncode

	if returncode != 0:
		_logger.warn("exec_as_user() ran as user '%s' (uid:%s, gid:%s) returncode: %s, stdout: %s", user_name, user_uid, user_gid, returncode, stdout)

	return returncode == 0


def _demote(user_uid, user_gid):
	def result():
		os.setgid(user_gid)
		os.setuid(user_uid)
	return result




