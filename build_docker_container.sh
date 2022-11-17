#!/bin/sh

if [ "$1" = "vpn-build" ]
then
  docker build --pull --no-cache --target vpn-build -f Dockerfile -t threat-hunting-game:vpn .
elif [ "$1" = "non-vpn-build" ]
then
  docker build --pull --no-cache --target non-vpn-build -f Dockerfile -t threat-hunting-game:non-vpn .
else
  echo "Please provide argument after script call ['vpn-build', 'non-vpn-build']"
fi