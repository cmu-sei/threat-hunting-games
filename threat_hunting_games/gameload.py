try:
    from . import v0
    from . import v1
    from . import v2
    from . import v2_seq
    from . import v2_tensormod
    from . import v2_matrix
except ImportError:
    import v0
    import v1
    import v2
    import v2_seq
    import v2_tensormod
    import v2_matrix

current_game = v2
#current_game = v2_seq
#current_game = v2_tensormod
#current_game = v2_matrix

game_name = current_game.game_name
