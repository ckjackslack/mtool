import argparse


class MonoHelpAction(argparse._HelpAction):
    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        print()

        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)]

        line = "-" * 20
        for subparsers_action in subparsers_actions:
            for choice, subparser in subparsers_action.choices.items():
                print()
                print(line, choice, line)
                print()
                for action in subparser._actions:
                    if isinstance(action, (
                        argparse._StoreAction,
                        argparse._StoreTrueAction
                    )):
                        if action.required:
                            param = action.dest
                        else:
                            param = f"{action.dest} [{action.default!r}]"
                        choices = ""
                        if action.choices:
                            choices = f"Allowed choices: {action.choices}"
                        print("\t", param, end="")
                        opts = [opt.strip("[]") for opt in action.option_strings]
                        if opts:
                            print(opts)
                        else:
                            print()
                        print("\t", action.help)
                        if choices:
                            print("\t", choices)
                        print()

        parser.exit()
