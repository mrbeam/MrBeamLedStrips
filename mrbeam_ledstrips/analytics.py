# coding=utf-8

import threading
import time
import logging
import json
import subprocess
import os
import pwd
import sys
import types
import pkg_resources
import traceback
from inspect import getframeinfo, stack


"""
How to integrate this mrb analytics module:

- adjust constant COMPONENT_NAME in this file
- add __package_path__ to __builtin__ by copytin this: 
	import os, __builtin__
	__builtin__.__package_path__ = os.path.dirname(__file__)
- in any relevant file:
- - import analytics file as analytics
- - Hook into exception method of your logger: analytics.hook_into_exception_function(self.logger)
- to send a mesage to analytics, call analytics.send_log_event(level, msg, params)

"""

COMPONENT_NAME = 'mrbeam_ledstrips'


TYPE_LOGEVENT = 'log_event'

RETRIES_WAIT_TIMES = [1.0, 2.0, 5.0, 10.0]

_logger = logging.getLogger(__name__)


def send_log_event(level, msg, *args, **kwargs):
	msg = msg % args if args and msg else msg

	exception_str = None
	stacktrace = None
	if kwargs.get('exc_info', 0):
		exctype, value, tb = sys.exc_info()
		exception_str = "{}: '{}'".format(exctype.__name__ if exctype is not None else None, value)
		stacktrace = traceback.format_tb(tb)

	data=dict(
		level = logging._levelNames[level] if level in logging._levelNames else level,
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
		filename = caller.filename.replace(__package_path__ + '/', '')
		data.update({
			'hash': hash('{}{}{}'.format(filename, caller.lineno, _get_version_string())),
			'file': filename,
			'line': caller.lineno,
			'function': caller.function,
		})

	_send_analytics(TYPE_LOGEVENT, data)


def hook_into_exception_function(logger):
	try: __package_path__
	except NameError:
		_logger.error("__package_path__ must be defined in package's __init__.py like this: import os, __builtin__; __builtin__.__package_path__ = os.path.dirname(__file__)")
	logger.exception = types.MethodType(_exception_overwirte, logger)


def _exception_overwirte(self, msg, *args, **kwargs):
	# id = self.name
	kwargs['exc_info'] = 1
	send_log_event(logging.ERROR, msg, *args, **kwargs)
	self.error(msg, *args, **kwargs)


def _send_analytics(type, data):
	package = dict(
		component=COMPONENT_NAME,
		component_version=_get_version_string(),
		type=type,
		data=json.dumps(data, sort_keys=False)
	)
	thread = threading.Thread(target=_send_analytics_threaded, kwargs=dict(package=package, retries=len(RETRIES_WAIT_TIMES)), name='send_analytics')
	thread.daemon = True
	thread.start()


def _send_analytics_threaded(package, retries):
	try:
		cmd = ['/home/pi/oprint/bin/octoprint', 'plugins', 'mrbeam:analytics',
		       '{}'.format(package['component']),
		       '{}'.format(package['component_version']),
		       '{}'.format(package['type']),
		       '{}'.format(package['data']),
		       ]

		res = _exec_as_user(cmd_list=cmd, user_name='pi')

		if not res and retries > 0:
			sleep_time = RETRIES_WAIT_TIMES[retries * -1]
			time.sleep(sleep_time)
			retries -= 1
			_send_analytics_threaded(package, retries)
	except:
		_logger.exception("Exception in _send_analytics_threaded(): ")


def _get_version_string():
	try:
		return pkg_resources.get_distribution(COMPONENT_NAME).version
	except:
		return None


def _exec_as_user(cmd_list, user_name):
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
    process = subprocess.Popen(
	    cmd_list, preexec_fn=_demote(user_uid, user_gid), cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    returncode = process.returncode

    logging.info("exec_as_user() ran as user '%s' (uid:%s, gid:%s) returncode: %s, cmd: %s, cwd: %s, env: %s", user_name, user_uid, user_gid, returncode, cmd_list, cwd, env)
    if returncode != 0:
        logging.warn("exec_as_user() ran as user '%s' (uid:%s, gid:%s) returncode: %s, stdout: %s", user_name, user_uid, user_gid, returncode, stdout)

    return returncode == 0


def _demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result




