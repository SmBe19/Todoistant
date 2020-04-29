#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess

import client

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_frontend(args):
    os.setpgrp()  # create new process group, become its leader
    try:
        subprocess.run(['gunicorn', '--bind', '0.0.0.0:{}'.format(args.port), 'src.frontend.frontend:app'])
    finally:
        os.killpg(0, signal.SIGTERM)


def run_server(args):
    import server
    server.run_server(args)


def main():
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
