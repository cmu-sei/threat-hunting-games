The use of policies with this game can applied via a bot, as is
traditional, *or* from within the game state, which is unconventional.
If the former is desired, pass the name of the policy (as defined in
./policy.py) using the `policy` parameter while creating the Game
instance. If the former (conventional bot use) is desired then just
instantiate a Game without the `policy` parameter.

Supporting both of these methods allows the game to be passed into the
many examples and algorithms (which don't use bots, just a game) while
also using a policy. The traditional way uses a bot harness that deploy
their own policies from outside of the game state.

Using both methods simultaneously is not supported.

An example of a bot that uses a policy is
open_spiel.python.bots.policy.PolicyBot

