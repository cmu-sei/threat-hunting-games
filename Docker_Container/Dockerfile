FROM docker.cc.cert.org/threat-hunting-games/threat-hunting-games-base:latest as source-code-threat_hunting_games

RUN mkdir /src
WORKDIR /src

COPY /tests /src/tests
COPY /threat_hunting_games /src/threat_hunting_games
COPY /Docker_Container/Create_GHOSTS_Env.py /src/Create_GHOSTS_Env.py
COPY /Docker_Container/Logs/api-calls.log /src/Logs/api-calls.log

# Run tests
#RUN ./virtualenv/bin/python3.10 ./virtualenv/lib/python3.10/site-packages/pytest tests
