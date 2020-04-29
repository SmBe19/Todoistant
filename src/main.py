#!/usr/bin/env python3
import argparse
import os
import subprocess

import dotenv

import client
import server

os.chdir(os.path.dirname(os.path.dirname(__file__)))
dotenv.load_dotenv('secrets.env')


def run_frontend(args):
    subprocess.run(['gunicorn', '--bind', '0.0.0.0:{}'.format(args.port), 'src.frontend.frontend:app'])


def main():
    parser = argparse.ArgumentParser(description='Manage Todoistant')
    subparsers = parser.add_subparsers(dest='command')
    server.prepare_parser(subparsers)
    client.prepare_parser(subparsers)

    frontend = subparsers.add_parser('frontend')
    frontend.set_defaults(func=run_frontend)
    frontend.add_argument('port', type=int)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
