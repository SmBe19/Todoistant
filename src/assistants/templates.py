from datetime import datetime, timedelta

from utils import run_every, run_next_in, parse_task_config

INIT_CONFIG = {
	'active': [],
}
CONFIG_VERSION = 1
CONFIG_WHITELIST = [
	'src_project',
]
CONFIG_INT = [
	'src_project',
]
CONFIG_LIST = []


def migrate_config(cfg, old_version):
	pass


should_run = run_every(timedelta(minutes=15))


handle_update = run_next_in(timedelta(seconds=1), {'item:deleted', 'item:completed'})


class ItemDeletedError(Exception):
	pass


def parse_template_item(api, item):
	content, config = parse_task_config(item['content'])
	res = {
		'id': config.get('template-id'),
		'content': content,
		'labels': item['labels'],
		'priority': item['priority'],

		'due': config.get('template-due', None),
		'depends': [x for x in config.get('template-depends', '').split('|') if x],
		'children': [],
		'item_id': None,
		'completed': False,
	}
	for child in api.state['items']:
		if child['parent_id'] == item['id']:
			res['children'].append(parse_template_item(api, child))
	return res


def parse_template(api, timezone, template_id, project_id):
	items = []
	root_item = api.items.get_by_id(template_id)
	project = api.projects.get_by_id(project_id)
	for item in api.state['items']:
		if item['parent_id'] == template_id:
			items.append(parse_template_item(api, item))
	return {
		'template': root_item['content'].rstrip(':'),
		'project': project['name'],
		'project_id': project_id,
		'start': datetime.utcnow(),
		'finished': None,
		'status': 'Running',
		'items': items,
	}


def update_template_state(api, timezone, cfg, tmp, template):
	completed = set()
	finished = [True]  # we use a list so we can access it in the function...

	def collect_completed(item):
		if item['item_id']:
			my_item = api.items.get_by_id(item['item_id'])
			if not my_item:
				template['status'] = 'Item was deleted'
				template['finished'] = datetime.utcnow()
				raise ItemDeletedError()
			if my_item['checked'] == 1:
				completed.add(item['id'])
			else:
				finished[0] = False
		else:
			finished[0] = False
		for child in item['children']:
			collect_completed(child)

	for item in template['items']:
		collect_completed(item)

	if finished[0]:
		template['finished'] = datetime.utcnow()
		template['status'] = 'Finished'
		return

	temp_id_to_task = {}

	def create_new_items(item, parent=None):
		if not item['item_id']:
			for dependency in item['depends']:
				if dependency not in completed:
					return
			new_task = api.items.add(item['content'], project_id=template['project_id'], labels=item['labels'], priority=item['priority'], parent_id=parent)
			if item['due']:
				new_task.update(due={'string': item['due'], 'lang': 'en'})
			temp_id_to_task[new_task['id']] = new_task
			item['item_id'] = new_task['id']
		for child in item['children']:
			create_new_items(child, item['item_id'])

	for item in template['items']:
		create_new_items(item)

	api.commit()

	def assign_ids(item):
		if item['item_id'] in temp_id_to_task:
			item['item_id'] = temp_id_to_task[item['item_id']]['id']
		for child in item['children']:
			assign_ids(child)

	for item in template['items']:
		assign_ids(item)


def run(api, timezone, telegram, cfg, tmp):
	new_active = []
	print('Start templates')
	for template in cfg['active']:
		if not template['finished']:
			try:
				print('Start update_template_state')
				update_template_state(api, timezone, cfg, tmp, template)
				print('Finished update_template_state')
			except ItemDeletedError:
				template['finished'] = datetime.utcnow()
				template['status'] = 'Item was deleted'
			except Exception as e:
				print('Template exception', e)
			new_active.append(template)
		else:
			if (datetime.utcnow() - template['finished']) < timedelta(days=3):
				new_active.append(template)
	print('Finished templates')
	cfg['active'] = new_active


def get_templates(api, timezone, cfg, tmp):
	if 'src_project' not in cfg:
		return []
	return [{
		'name': item['content'].rstrip(':'),
		'id': item['id'],
	} for item in api.state['items'] if item['project_id'] == cfg['src_project'] and not item['parent_id']]


def start(api, timezone, cfg, tmp, template_id, project_id):
	try:
		template = parse_template(api, timezone, template_id, project_id)
	except RuntimeError:
		return 'Invalid template'
	try:
		update_template_state(api, timezone, cfg, tmp, template)
	except ItemDeletedError:
		return 'Item was deleted ???'
	cfg['active'].append(template)
	return 'ok'
