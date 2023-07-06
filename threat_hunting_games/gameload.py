try:
    # for scripts living in subdirs, e.g. ./threat_hunting_games/examples
    from .games.v0 import v0
    from .games.v1 import v1
    from .games.v2 import v2
    from .games.v2 import v2_seq
    from .games.v2 import v2_tensormod
    from .games.v2 import v2_matrix
    from .games.v3 import v3_lockbit_seq
    from .games.v3 import v3_lb_seq_zsum
    from .games.v4_policy import v4_lb_seq_zsum
    from .games.v5_ghosts import v5_policy_game
except (ModuleNotFoundError, ImportError):
    # for scripts living in top level ./threat_hunting_games
    from games.v0 import v0
    from games.v1 import v1
    from games.v2 import v2
    from games.v2 import v2_seq
    from games.v2 import v2_tensormod
    from games.v2 import v2_matrix
    from games.v3 import v3_lockbit_seq
    from games.v3 import v3_lb_seq_zsum
    from games.v4_policy import v4_lb_seq_zsum
    from .games.v5_ghosts import v5_policy_game

#current_game = v2
#current_game = v2_seq
#current_game = v2_tensormod
#current_game = v2_matrix
#current_game = v3_lockbit_seq
#current_game = v4_lb_seq_zsum
current_game = v5_policy_game

game_name = current_game.game_name
