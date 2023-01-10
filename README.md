This repository contains simulations and other source code related to
the the SEI research project on applications of game theory to threat
hunting.

# Toolchain

## Docker Container
In order to spin up a [Docker](https://www.docker.com/) container you can run the following commands:

**VPN Build**:
`./build_docker_container.sh vpn`

**Non VPN Build**:
`./build_docker_container.sh non-vpn`

## Pyenv and pyenv-virtualenv (optional, encouraged)

The Python version being targeted is 3.10.\*. This is not a carefully
chosen version, except that some features landed in 3.10 that the
project uses, and upgrading hasn\'t yet been investigated. I suggest
using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions.
To use virtual environments and pyenv together, see
[pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).

Once pyenv and pyenv-virtualenv are installed (e.g., using
`brew install pyenv`{.verbatim} on Mac, or downloading and installing
for Linux as described
[here](https://bgasparotto.com/install-pyenv-ubuntu-debian), or via the
[method described at the project
Github](https://github.com/pyenv/pyenv#basic-github-checkout)), the
correct Python version can be

Poetry also has tools for selecting environments for the project, which
you may prefer to use. These directions will mostly assume

## Poetry

All other dependencies are managed via
[Poetry](https://python-poetry.org/). Poetry\'s main virtue is managing
dependencies, including downloading and installing them into a virtual
environment, in a way that lets the project control which versions are
installed. It also functions as a build tool.

To make Poetry management easier, the project is principally organized
as a single Python package. Development efforts with different needs
(e.g., those in other languages) will be maintained in different
repositories as necessary. Poetry has a number

When you have your virtualenv active, `poetry install`{.verbatim} in the
top-level directory should download the dependencies from pypi and
install them.

## Other Packages

Some of the examples and algorithms use the following python modules:

  * [TensorFlow](https://www.tensorflow.org/install/pip)
  * [pandas](https://pandas.pydata.org/)
  * [CVXOPT](https://cvxopt.org/)

Some of the examples involving Nash-equilibria require the following
system packages:

  * [lrsnash](https://manpages.ubuntu.com/manpages/jammy/man1/lrsnash.1.html) (`apt install lrsnash`)

## Additional build dependencies

To keep code quality high and catch mistakes early, this project uses
several code analysis tools. Links are to the PyPI page unless noted;
additiona links are available from there.

-   [Black](https://pypi.org/project/black/), the \"uncompromising code
    formatter\"
-   [Pylint](https://pypi.org/project/pylint/), a static code analyzer
-   [Mypy](https://pypi.org/project/mypy/), a static type checker.
    ([Documentation](https://mypy.readthedocs.io/en/stable/#))
-   [pytest](https://pypi.org/project/pytest/), a test framework
-   [Jedi](https://pypi.org/project/jedi/), a static analysis tool used
    for adding code completion and other features to editors. See the
    plugins for [Vim](https://github.com/davidhalter/jedi-vim) and
    [Sublime](https://github.com/CyanSalt/Sublime-Jedi).

Jedi is optional, but developers should run the rest and seek to make
the code warning-clean, either by fixing problems or, after careful
consideration, by making local exceptions.

## openspiel

The main runtime dependency is the
[OpenSpiel](https://pypi.org/project/open-spiel/) game simulation
framework.
