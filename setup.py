# coding=utf-8
# !/usr/bin/env python

from setuptools import setup, Command
import sys
import versioneer

DESCRIPTION = "A daemon for controlling the LEDs of Mr Beam II"
LONG_DESCRIPTION = """mrbeam_ledstrips is a small Python daemon for reading
the machine state of Mr Beam II over a unix domain socket.
"""

EXTRAS_FOLDERS = [
    ('/etc/mrbeam_ledstrips.conf.d', 0o755),
    ('/usr/share/mrbeam_ledstrips/png', 0o755)
]

EXTRAS_FILES = [
    ('/etc/', [('extras/mrbeam_ledstrips.yaml', 'mrbeam_ledstrips.yaml', 0o600)]),
    ('/usr/share/mrbeam_ledstrips/png/', [('extras/png', 0o644)]),
    ('/etc/logrotate.d/', [('extras/mrbeam_ledstrips.logrotate', 'mrbeam_ledstrips', 0o644)]),
    ('/lib/systemd/system/', [('extras/mrbeam_ledstrips.unit', 'mrbeam_ledstrips.service', 0o644)])
]


def get_extra_tuple(entry):
    import os

    if isinstance(entry, (tuple, list)):
        if len(entry) == 2:
            path, mode = entry
            filename = os.path.basename(path)
        elif len(entry) == 3:
            path, filename, mode = entry
        elif len(entry) == 1:
            path = entry[0]
            filename = os.path.basename(path)
            mode = None
        else:
            return None

    else:
        path = entry
        filename = os.path.basename(path)
        mode = None

    return path, filename, mode


class InstallExtrasCommand(Command):
    description = "install extras like init scripts and config files"
    user_options = [("force", "F", "force overwriting files if they already exist")]

    def initialize_options(self):
        self.force = None

    def finalize_options(self):
        if self.force is None:
            self.force = False

    def run(self):
        global EXTRAS_FILES, EXTRAS_FOLDERS
        import shutil
        import os

        # TODO enable service by running "sudo systemctl enable mrbeam_ledstrips.service" or symlinking

        for folder, mode in EXTRAS_FOLDERS:
            try:
                if os.path.exists(folder):
                    os.chmod(folder, mode)
                else:
                    os.mkdir(folder, mode)
            except Exception as e:
                print(("Error while creating %s (%s), aborting" % (folder, e.message)))
                sys.exit(-1)

        for target, files in EXTRAS_FILES:
            for entry in files:
                extra_tuple = get_extra_tuple(entry)
                if extra_tuple is None:
                    print(("Can't parse entry for target %s, skipping it: %r" % (target, entry)))
                    continue

                path, filename, mode = extra_tuple
                target_path = os.path.join(target, filename)

                path_exists = os.path.exists(target_path)
                if path_exists and not self.force:
                    print(("Skipping copying %s to %s as it already exists, use --force to overwrite" % (
                        path, target_path)))
                    continue

                try:
                    shutil.copy(path, target_path)
                    if mode:
                        os.chmod(target_path, mode)
                        print(("Copied %s to %s and changed mode to %o" % (path, target_path, mode)))
                    else:
                        print(("Copied %s to %s" % (path, target_path)))
                except Exception as e:
                    if not path_exists and os.path.exists(target_path):
                        # we'll try to clean up again
                        try:
                            os.remove(target_path)
                        except:
                            pass

                    print(("Error while copying %s to %s (%s), aborting" % (path, target_path, e.message)))
                    sys.exit(-1)


class UninstallExtrasCommand(Command):
    description = "uninstall extras like init scripts and config files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        global EXTRAS_FILES, EXTRAS_FOLDERS
        import os

        for target, files in EXTRAS_FILES:
            for entry in files:
                extra_tuple = get_extra_tuple(entry)
                if extra_tuple is None:
                    print(("Can't parse entry for target %s, skipping it: %r" % (target, entry)))

                path, filename, mode = extra_tuple
                target_path = os.path.join(target, filename)
                try:
                    os.remove(target_path)
                    print(("Removed %s" % target_path))
                except Exception as e:
                    print(("Error while deleting %s from %s (%s), please remove manually" % (
                        filename, target, e.message)))

        for folder, mode in EXTRAS_FOLDERS[::-1]:
            try:
                os.rmdir(folder)
            except Exception as e:
                print(("Error while removing %s (%s), please remove manually" % (folder, e.message)))


def get_cmdclass():
    """
    get the versioneer cmd class and extra commands

    Returns:
        cmdclass
    """
    cmdclass = versioneer.get_cmdclass()
    cmdclass.update({
        'install_extras': InstallExtrasCommand,
        'uninstall_extras': UninstallExtrasCommand
    })
    return cmdclass


install_requires = ["PyYaml", ]
if sys.version_info >= (3, 0):
    install_requires += ["rpi-ws281x; platform_machine=='armv7l'", ]
setup(
    name="mrbeam_ledstrips",
    version=versioneer.get_version(),
    cmdclass=get_cmdclass(),
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author="Teja Philipp",
    author_email="teja@mr-beam.org",
    url="http://github.com/mrbeam/mrbeam_ledstrips",
    license="GPLV3",
    packages=["mrbeam_ledstrips"],
    zip_safe=False,
    dependency_links=[],
    install_requires=install_requires,
    entry_points={
        "console_scripts": {
            "mrbeam_ledstrips = mrbeam_ledstrips:server",
            "mrbeam_ledstrips_cli = mrbeam_ledstrips:client"
        }
    },
)
