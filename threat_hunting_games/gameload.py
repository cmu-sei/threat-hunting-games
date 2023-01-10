try:
    from . import v0
    from . import v1
    from . import v2
    from . import v2_seq
except ImportError:
    import v0
    import v1
    import v2
    import v2_seq

current_game = v2
#current_game = v2_seq

game_name = current_game.game_name
