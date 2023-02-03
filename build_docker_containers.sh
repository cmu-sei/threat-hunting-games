#!/bin/bash
# Check that the Docker Daemon is running
systemctl start docker

if [ "$2" = "--reset" ]
then
  rm GHOSTS_Environment/Environment_Data/*
  touch GHOSTS_Environment/Environment_Data/.keep
fi
if [ "$3" = "-d" ]
then
  docker compose --file Docker_Container/docker-compose.yml up -d
  docker ps
else
  docker compose --file Docker_Container/docker-compose.yml up
fi

