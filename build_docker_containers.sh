#!/bin/sh
RESET=0
DETACH=0
VPN=0
export COMPOSE_PROJECT_NAME=threat-hunting-games
usage() {
  echo "Usage: $0 [ -d Run in Detached Mode ] [ -r Reset the environment data in GHOSTS ] [ -v Build the VPN configuration of the containers] " 1>&2
}
while getopts "drv" arg; do
  case $arg in
    d) DETACH="1" ;;
    r) RESET=1 ;;
    v) VPN="1" ;;
    *) echo 'error' >&2
      exit 1
  esac
done

if [ $RESET -eq 1 ]
then
  echo "RESETTING ENVIRONMENT DATA..."
  rm -rf Containers/Environment_Data/db_data
  rm -rf Containers/Environment_Data/g_data
  rm -rf Containers/Environment_Data/spectre_data
echo "ALL ENVIRONMENT DATA RESET..."
echo " "
fi
if [ $VPN -eq 1 ]
echo "BUILDING VPN VERSION OF CONTAINER..."
then
  if [ $DETACH -eq 1 ]
  then
    docker compose --file Containers/docker-compose.vpn.yml up -d --force--recreate
    docker ps
  else
    docker compose --file Containers/docker-compose.vpn.yml up --force-recreate
  fi
else
  if [ $DETACH -eq 1 ]
  then
    docker compose --file Containers/docker-compose.yml up -d --force-recreate
    docker ps
  else
    docker compose --file Containers/docker-compose.yml up --force-recreate
  fi
fi
