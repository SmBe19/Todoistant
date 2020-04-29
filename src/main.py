#!/usr/bin/env python3
import argparse
import os

import dotenv

import client
import server

os.chdir(os.path.dirname(os.path.dirname(__file__)))
dotenv.load_dotenv('secrets.env')


def main():
    parser = argparse.ArgumentParser(description='Manage Todoistant')
    subparsers = parser.add_subparsers(dest='command')
    server.prepare_parser(subparsers)
    client.prepare_parser(subparsers)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
