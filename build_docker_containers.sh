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
    docker compose --file Docker_Container/docker-compose.vpn.yml up -d
    docker ps
  else
    docker compose --file Docker_Container/docker-compose.vpn.yml up
  fi
elif [ "$1" = "non-vpn" ]
then
  if [ "$3" = "-d" ]
  then
    docker compose --file Docker_Container/docker-compose.yml up -d
    docker ps
  else
    docker compose --file Docker_Container/docker-compose.yml up
  fi
else
  echo "Please provide argument after script call: ['vpn', 'non-vpn']"
  exit 1
fi
