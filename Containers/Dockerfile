FROM python:3.10.8-slim-bullseye
ENV PYVERSION ${pyversion:-3.10.8}
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.2.2 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv" \
    CLANG_PATH="/opt/clang_env"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

RUN mkdir $CLANG_PATH

RUN mkdir -v -p $PYSETUP_PATH
WORKDIR $PYSETUP_PATH
# Prepare virtualenv
RUN python -m venv $VENV_PATH

# Copy over the code base
COPY ../poetry.lock pyproject.toml ./
RUN $VENV_PATH/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org poetry==$POETRY_VERSION
# Copy over code base files
RUN mkdir /src
COPY /tests /src/tests
COPY /threat_hunting_games /src/threat_hunting_games
COPY /GHOSTSConnection /src/GHOSTSConnection
COPY /Logs/GHOSTSConnection.log /src/Logs/GHOSTSConnection.log

WORKDIR $CLANG_PATH
# Install dependencies
RUN apt-get -qq update; \
    apt-get install -qqy --no-install-recommends \
        gnupg2 wget ca-certificates apt-transport-https \
        autoconf automake cmake dpkg-dev file make patch libc6-dev

RUN update-ca-certificates
# Install LLVM
RUN wget -nv -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -

RUN echo "deb http://apt.llvm.org/bullseye/ llvm-toolchain-bullseye-15 main" > /etc/apt/sources.list.d/llvm.list;   \
    apt-get -qq update &&  apt-get install -qqy -t llvm-toolchain-bullseye-15 clang-15 clang-tidy-15 clang-format-15 lld-15 &&   \
    for f in /usr/lib/llvm-15/bin/*; do ln -sf "$f" /usr/bin; done &&   \
    rm -rf /var/lib/apt/lists/*


WORKDIR $PYSETUP_PATH
RUN poetry install --no-interaction --no-ansi

SHELL ["/bin/bash", "-c"]
WORKDIR /src

# Run tests
#RUN ./virtualenv/bin/python3.10 ./virtualenv/lib/python3.10/site-packages/pytest tests
