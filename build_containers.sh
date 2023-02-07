#!/bin/bash
# Check that the Docker Daemon is running
systemctl start docker
export COMPOSE_PROJECT_NAME=threat-hunting-games

if [ "$2" = "--reset" ]
then
  rm GHOSTS_Environment/Environment_Data/*
  touch GHOSTS_Environment/Environment_Data/.keep
fi
if [ "$3" = "--verbose" ]
then
  docker compose --file Docker_Container/docker-compose.yml up --force-recreate
else
  docker compose --file Docker_Container/docker-compose.yml up --detach --force-recreate
  docker ps
fi

