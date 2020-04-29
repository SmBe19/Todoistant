import todoist

handlers = {}


def handler(f):
	handlers[f.__name__] = f
	return f


@handler
def add_account(token, mgr):
	print('Add Account')
	api = todoist.TodoistAPI(token)
	api.sync()
	if not api.state['user']:
		return 'bad token'
	with mgr.get(api.state['user']['id']) as cfg:
		cfg['token'] = token
	return 'account added'
