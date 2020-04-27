#!/usr/bin/env python3
import os

import dotenv
import todoist

import priosorter

os.chdir(os.path.dirname(os.path.dirname(__file__)))
dotenv.load_dotenv('secrets.env')


def main():
    if not os.path.isdir('cache'):
        os.mkdir('cache')
    api = todoist.TodoistAPI(os.environ['TODOIST_TOKEN'], cache='./cache/')
    priosorter.sort_prios(api)


if __name__ == '__main__':
    main()
