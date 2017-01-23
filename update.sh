#!/usr/bin/env bash

printf "Downloading new version...\n"
git fetch --all
git reset --hard origin/master
printf "Remove old version...\n"
sudo pip uninstall -y mrbeam-ledstrips
printf "Installing new version...\n"
sudo python setup.py install
printf "Restarting service...\n"
sudo systemctl restart mrbeam_ledstrips.service

