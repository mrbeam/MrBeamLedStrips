# MrBeamLedStrips

MrBeamLedStrips is a standalone compontent that handles Mr Beam II's LED strips.

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