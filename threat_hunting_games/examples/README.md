These examples are taken from the open_spiel/python/examples directory and slightly modified in order to use various versions of our game implementation by importing the game and therefore registering it with pyspiel.

Sometimes further modifications are necessary in order to get the example working with our game (for example, converting the game from SIMULTANEOUS to turn based with the `pyspiel.load_game_as_turn_based(game_name)` call in `matrix_nash_example.py`

For purposes of comparison with the original scripts in the openspiel/python source directory, two-spaced indentation has been preserved in the files taken from the open_spiel distribution.
