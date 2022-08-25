# MrBeamLedStrips

MrBeamLedStrips is a standalone component that handles Mr Beam II's LED strips.

## Usage
#### Socket Connection
There is a socket: `/var/run/mrbeam_ledstrips.sock`

Currently MrBeamPlugin does not use the socket connection. 
Still this needs to be done for performance! Some day...

#### Command Line Interface (CLI)
Or use the command line interface:
* `mrbeam_ledstrips_cli [command]`  Commands:

    * `` (no command) Prints version of MrBeamLedStrips. (Does not connect to daemon.)
    * `?` Prints version, list of possible commands and debug information
    * `unknown`
    * `DebugStop`  # breaks -> SW-1733
    * `on`, `all_on`
    * `off`, `all_off`
    * `brightness` # Error
    * `rollback`
    * `fps` # Error
    * `spread_spectrum` # Error
    * `ignore_next_command`
    * `ignore_stop`
    * `Listening`, `_listening`, `listening`
    * `Startup`
    * `ClientOpened`
    * `ClientClosed`
    * `Error`
    * `Shutdown`
    * `ShutdownPrepare`
    * `ShutdownPrepareCancel`
    * `Upload`
    * `PrintStarted`
    * `PrintDone`
    * `PrintCancelled`
    * `PrintPaused`
    * `PrintPausedTimeout`
    * `PrintPausedTimeoutBlock`
    * `ButtonPressReject`
    * `PrintResumed`
    * `Progress:<progress>`, `progress:<progress>`
    * `JobFinished`, `job_finished`
    * `Pause`, `pause`
    * `ReadyToPrint`
    * `ReadyToPrintCancel`
    * `SlicingStarted`
    * `SlicingDone`
    * `SlicingCancelled`
    * `SlicingFailed`
    * `SlicingProgress:<progress>`, `slicing_progress:<progress>`
    * `SettingsUpdated`  # breaks -> SW-1733
    * `LaserJobDone`
    * `LaserJobCancelled`
    * `LaserJobFailed`
    * `white`, `all_white`
    * `red`, `all_red`
    * `green`, `all_green`
    * `blue`, `all_blue`
    * `yellow`, `all_yellow`
    * `orange`, `all_orange`


## Config
For configuration see:
 * `iobeam/extras/mrbeam_ledstrips.yaml` or 
 * `/etc/mrbeam_ledstrips.yaml` after deployment.


## Change Log

##### 0.1.11
New commands:
* Command `ButtonPressReject`: Intended to give feedback that a button press is an invalid action at the moment. 
Flashes red once and the rolls back.
* README.md added
##### < 0.1.10
See commit log
