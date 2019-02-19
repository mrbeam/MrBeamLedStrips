# coding=utf-8

import threading
import time
import logging
import json
import subprocess
import os
import pwd
import sys
import pkg_resources
from inspect import getframeinfo, stack

COMPONENT_NAME = 'mrbeam_ledstrips'

TYPE_LOGEVENT = 'log_event'

RETRIES_WAIT_TIMES = [1.0, 2.0, 5.0, 10.0]

_logger = logging.getLogger(__name__)


def send_log_event(level, msg, *args, **kwargs):
	msg = msg % args if args and msg else msg

	caller = None
	caller_myself = getframeinfo(stack()[0][0])
	i = 1
	while caller is None or caller.filename == caller_myself.filename:
		caller = getframeinfo(stack()[i][0])
		i += 1

	data=dict(
		level = logging._levelNames[level] if level in logging._levelNames else level,
		msg = msg,
		caller = caller
	)
	_send_analytics(TYPE_LOGEVENT, data)



def _send_analytics(type, data):
	package = dict(
		component=COMPONENT_NAME,
		component_version=_get_version_string(),
		type=type,
		data=json.dumps(data, sort_keys=False)
		# TODO: test critical chars in JSON liek \n quotes, spaces parentheses etc...
		# data=json.dumps(data, sort_keys=False).replace("'", '"')
	)
	thread = threading.Thread(target=_send_analytics_threaded, kwargs=dict(package=package, retries=len(RETRIES_WAIT_TIMES)), name='send_analytics')
	thread.daemon = True
	thread.start()


def _send_analytics_threaded(package, retries):
	try:
		cmd = ['/home/pi/oprint/bin/octoprint', 'plugins', 'mrbeam:analytics',
		       '"{}"'.format(package['component']),
		       '"{}"'.format(package['component_version']),
		       '"{}"'.format(package['type']),
		       "{}".format(package['data']),
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




