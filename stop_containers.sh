#!/bin/bash
# Stopping all of the containers
docker stop $(docker ps -a -q)
# Removing all of the containers
docker rm -f $(docker ps -a -q)
