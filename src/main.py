#!/usr/bin/env python3
import datetime
import os

import dotenv
import todoist

import automover
import priosorter

os.chdir(os.path.dirname(os.path.dirname(__file__)))
dotenv.load_dotenv('secrets.env')


def main():
    if not os.path.isdir('cache'):
        os.mkdir('cache')
    api = todoist.TodoistAPI(os.environ['TODOIST_TOKEN'], cache='./cache/')
    api.sync()
    tz_info = api.state['user']['tz_info']
    timezone = datetime.timezone(datetime.timedelta(hours=tz_info['hours'], minutes=tz_info['minutes']), tz_info['timezone'])
    automover.auto_move(api, timezone)
    priosorter.sort_prios(api, timezone)


if __name__ == '__main__':
    main()
