#!/usr/bin/env python3
import argparse
import os

import client

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_frontend(args: argparse.Namespace) -> None:
    os.execvp('gunicorn', ['gunicorn', '--bind', '0.0.0.0:{}'.format(args.port), 'src.frontend.frontend:app'])


def run_server(args: argparse.Namespace) -> None:
    import server
    server.run_server(args)


def main() -> None:
    parser = argparse.ArgumentParser(description='Manage Todoistant')
    subparsers = parser.add_subparsers(dest='command')
    server = subparsers.add_parser('server')
    server.set_defaults(func=run_server)

    frontend = subparsers.add_parser('frontend')
    frontend.set_defaults(func=run_frontend)
    frontend.add_argument('port', type=int)

    client.prepare_parser(subparsers)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
