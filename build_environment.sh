#!/bin/sh
if [ "$1" = "vpn" ]
then
  docker build --pull --no-cache --target vpn -f Dockerfile -t threat-hunting-game:vpn .
elif [ "$1" = "non-vpn" ]
then
  docker build --pull --no-cache --target non-vpn -f Dockerfile -t threat-hunting-game:non-vpn .
else
  echo "Please provide argument after script call: ['vpn', 'non-vpn']"
  exit
fi
echo "Composing Containers....."
if [ "$2" = "-d" ]
then
  if [ "$1" = "vpn" ]
  then
    docker compose up --file docker-compose.vpn.yml -d
    docker ps
  else
    docker compose -d --file docker-compose.vpn.yml up
  fi
else
  if [ "$2" = "-d" ]
  then
    docker compose --file docker-compose.yml up -d
  else
    docker compose --file docker-compose.yml up -d
  fi
fi

