#!/usr/bin/env bash

printf "Downloading new version...\n"
git fetch --all
git reset --hard origin/master
printf "finished!\n"
printf "Restarting service...\n"
sudo systemctl restart mrbeam_ledstrip.service
printf "finished!\n"
