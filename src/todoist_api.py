import datetime

import todoist


def get_api(token):
	api = todoist.TodoistAPI(token, cache='./cache/')
	api.sync()
	if not api.state['user']:
		return api, None
	tz_info = api.state['user']['tz_info']
	timezone = datetime.timezone(
		datetime.timedelta(hours=tz_info['hours'], minutes=tz_info['minutes']),
		tz_info['timezone']
	)
	return api, timezone
