try:
    # for scripts living in subdirs, e.g. ./threat_hunting_games/examples
    print("trying .games")
    from .games import v0
    from .games import v1
    from .games import v2
    from .games import v2_seq
    from .games import v2_tensormod
    from .games import v2_matrix
except (ModuleNotFoundError, ImportError):
    # for scripts living in top level ./threat_hunting_games
    print("trying games")
    from games import v0
    from games import v1
    from games import v2
    from games import v2_seq
    from games import v2_tensormod
    from games import v2_matrix

print("imports complete")

#current_game = v2
#current_game = v2_seq
#current_game = v2_tensormod
current_game = v2_matrix

game_name = current_game.game_name
