from datetime import timezone


def utc_to_local(date, local_timezone):
	return date.replace(tzinfo=timezone.utc).astimezone(local_timezone)


def parse_task_config(content):
	pos = content.find('[ ](')
	if pos < 0:
		return content, {}
	endpos = content[pos:].find(')')
	if endpos < 0:
		return content, {}
	res = {}
	config = content[pos+4:pos + endpos]
	for item in config.split(','):
		if ':' in item:
			parts = item.split(':', 1)
			res[parts[0].strip()] = parts[1].strip()
	return content[:pos].strip(), res
