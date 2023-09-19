import os, sys

import arena, policies

def add_std_args(DEFAULTS, parser, no_defaults=False):
    help_str = "Defender detect action cost structure."
    args = ["--detection-costs", "--dc"]
    if no_defaults:
        parser.add_argument(*args, help=help_str)
    else:
        help_str += f" DEFAULTS.detection_costs"
        parser.add_argument(*args, default=DEFAULTS.detection_costs,
                help=help_str)
    help_str = "Attacker advance action rewards structure."
    args = ["--advancement-rewards", "--ar"]
    if no_defaults:
        parser.add_argument(*args, help=help_str)
    else:
        help_str += f" (DEFAULTS.advancement_rewards"
        parser.add_argument(*args, default=DEFAULTS.detection_costs,
                help=help_str)
    def_def_policy = DEFAULTS.defender_policy
    if DEFAULTS.defender_action_picker:
        def_def_policy = '-'.join([def_def_policy,
            DEFAULTS.defender_action_picker])
    parser.add_argument("--defender-policy", "--dp", default=def_def_policy,
            help=f"Defender policy ({DEFAULTS.defender_policy})")
    def_atk_policy = DEFAULTS.attacker_policy
    if DEFAULTS.attacker_action_picker:
        def_atk_policy = '-'.join([def_atk_policy,
                DEFAULTS.attacker_action_picker])
    parser.add_argument("--attacker-policy", "--ap", default=def_atk_policy,
            help=f"Attacker policy ({DEFAULTS.attacker_policy})")
    parser.add_argument("-l", "--list-policies", action="store_true",
            help="List available policies")
    help_str = "WAIT as a possible action for both players."
    if DEFAULTS.use_waits:
        parser.add_argument("--no-waits", action="store_true",
                help=f"Exclude {help_str}")
    else:
        parser.add_argument("--use-waits", action="store_true",
            help=f"Include {help_str}")
    help_str = "IN_PROGRESS actions (random within a range hard   coded in arena.py per action) prior to finalizing an action."
    if DEFAULTS.use_timewaits:
        parser.add_argument("--no-timewaits", action="store_true",
                help=f"Exclude {help_str}")
    else:
        parser.add_argument("--use-timewaits", action="store_true",
                help=f"Include {help_str}")
    help_str = "general percent failure for actions as well as a p  ercent failure for actions applied to their corresponding action of the other   player (percentages hard coded in arena.py)."
    if DEFAULTS.use_chance_fail:
        parser.add_argument("--no-chance-fail", action="store_true",
                help=f"Disable using a {help_str}")
    else:
        parser.add_argument("--use-chance-fail", action="store_true",
                help=f"Use a {help_str}")
    parser.add_argument("--list-advancement-rewards", "-lar",
            action="store_true", help="List attacker rewards choices")
    parser.add_argument("--list-detection-costs", action="store_true",
            help="List defender costs choices")

def handle_std_args(args):
    if args.list_policies:
        for policy_name in policies.list_policies_with_pickers_strs():
            print("  ", policy_name)
        sys.exit()
    if args.list_detection_costs:
        for dc in arena.list_detection_utilities():
            print("  ", dc)
        sys.exit()
    if args.list_advancement_rewards:
        for au in arena.list_advancement_utilities():
            print("  ", au)
        sys.exit()
    if args.list_policies:
        for policy_name in policies.list_policies_with_pickers_strs():
            print("  ", policy_name)
        sys.exit()
    if args.list_detection_costs:
        for dc in arena.list_detection_utilities():
            print("  ", dc)
        sys.exit()
    if args.list_advancement_rewards:
        for au in arena.list_advancement_utilities():
            print("  ", au)
        sys.exit()
    def_policy = def_action_picker = None
    def_pol_parts = args.defender_policy.split('-')
    if len(def_pol_parts) > 1:
        def_policy, def_action_picker = def_pol_parts
    else:
        def_policy = def_pol_parts[0]
    atk_policy = atk_action_picker = None
    atk_pol_parts = args.attacker_policy.split('-')
    if len(atk_pol_parts) > 1:
        atk_policy, atk_action_picker = atk_pol_parts
    else:
        atk_policy = atk_pol_parts[0]
    try:
        use_waits = args.use_waits
    except AttributeError:
        use_waits = not args.no_waits
    try:
        use_timewaits = args.use_timewaits
    except AttributeError:
        use_timewaits = not args.no_timewaits
    try:
        use_chance_fail = args.use_chance_fail
    except AttributeError:
        use_chance_fail = not args.no_chance_fail
    values = {
        "advancement_rewards": args.advancement_rewards,
        "detection_costs": args.detection_costs,
        "defender_policy": def_policy,
        "defender_action_picker": def_action_picker,
        "attacker_policy": atk_policy,
        "attacker_action_picker": atk_action_picker,
        "use_waits": use_waits,
        "use_timewaits": use_timewaits,
        "use_chance_fail": use_chance_fail,
    }
    return values
