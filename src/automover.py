from datetime import datetime


def auto_move(api, timezone):
	api.sync()
	automove_label = None
	for label in api.state['labels']:
		if label['name'] == 'automove':
			automove_label = label
			break
	if not automove_label:
		return

	now = datetime.now(timezone)
	nowstr = now.strftime('%Y-%m-%d')
	for item in api.state['items']:
		if not item['due'] or item['date_completed']:
			continue
		if automove_label['id'] not in item['labels']:
			continue
		if 'T' in item['due']['date']:
			timepart = 'T' + item['due']['date'].split('T', 1)[1]
		else:
			timepart = ''
		due = datetime.strptime(item['due']['date'].split('T')[0], '%Y-%m-%d')
		if now.date() > due.date():
			new_due = item['due']
			new_due['date'] = nowstr + timepart
			item.update(due=new_due)
	api.commit()
