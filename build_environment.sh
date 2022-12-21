#!/bin/sh
if [ "$3" = "--reset" ]
then
  rm GHOSTS_Environment/Environment_Data/*
  touch GHOSTS_Environment/Environment_Data/.keep
fi
if [ "$1" = "vpn" ]
then
  if [ "$3" = "-d" ]
  then
    docker compose --file docker-compose.vpn.yml -d
    docker ps
  else
    docker compose --file docker-compose.vpn.yml
  fi
elif [ "$1" = "non-vpn" ]
then
  if [ "$3" = "-d" ]
  then
    docker compose --file docker-compose.yml -d
    docker ps
  else
    docker compose --file docker-compose.yml
  fi
else
  echo "Please provide argument after script call: ['vpn', 'non-vpn']"
  exit 1
fi
