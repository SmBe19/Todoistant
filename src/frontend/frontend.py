#!/usr/bin/env python3

import base64
import os
import sys
import datetime

import dotenv
import requests
from flask import Flask, render_template, session, redirect, url_for, request, flash

sys.path.append(os.path.abspath('src'))

from client import Client
import runner

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv.load_dotenv('secrets.env')

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

assert 'CLIENT_ID' in os.environ
assert 'CLIENT_SECRET' in os.environ


@app.template_filter()
def format_datetime(value, format='%d.%m.%Y %H:%M:%S'):
	if not value:
		return '-'
	timezone = datetime.timezone(
		datetime.timedelta(
			hours=session['timezone']['hours'],
			minutes=session['timezone']['minutes']
		),
		session['timezone']['timezone']
	)
	return value.replace(tzinfo=datetime.timezone.utc).astimezone(timezone).strftime(format)


@app.context_processor
def inject_now():
	return {
		'now': datetime.datetime.utcnow(),
		'debug': app.debug,
	}


@app.route('/')
def index():
	if 'userid' in session:
		return redirect(url_for('config'))
	return render_template('index.html')


@app.route('/config')
def config():
	if 'userid' not in session:
		return redirect(url_for('config'))
	with Client() as client:
		return render_template('config.html', config=client.get_config(session['userid']))


@app.route('/config/update/<assistant>', methods=['POST'])
def update_config(assistant):
	if assistant not in runner.ASSISTANTS:
		flash('Unknown assistant ' + assistant)
		return redirect(url_for('config'))
	assistant_mod = runner.ASSISTANTS[assistant]
	with Client() as client:
		if 'enabled' in request.form:
			client.set_enabled(session['userid'], assistant, request.form['enabled'] == 'true')

		update = {}
		for key in assistant_mod.CONFIG_WHITELIST:
			if key in request.form:
				update[key] = str(request.form[key])
		if update:
			client.update_config(session['userid'], {assistant: update})
	return redirect(url_for('config'))


@app.route('/login', methods=['POST'])
def login():
	if not app.debug:
		return redirect(url_for('index'))
	session['userid'] = request.form['userid']
	session['full_name'] = 'Test User'
	session['avatar'] = ''
	session['timezone'] = {
		'timezone': 'Europe/Zurich',
		'hours': 2,
		'minutes': 0,
	}
	return redirect(url_for('config'))


@app.route('/logout', methods=['POST'])
def logout():
	session.clear()
	return redirect(url_for('index'))


@app.route('/oauth/redirect')
def oauth_redirect():
	state = base64.urlsafe_b64encode(os.urandom(32)).decode()
	session['OAUTH_STATE'] = state
	return redirect(
		'https://todoist.com/oauth/authorize?client_id={}&scope={}&state={}'.format(
			os.environ['CLIENT_ID'],
			'data:read_write',
			state
		)
	)


@app.route('/oauth/callback')
def oauth_callback():
	def fail(msg):
		flash(msg)
		return redirect(url_for('index'))
	if 'error' in request.args:
		return fail('OAauth failed: ' + request.args['error'])
	state = request.args.get('state')
	if not state or state != session.get('OAUTH_STATE'):
		return fail('Invalid OAuth state')
	code = request.args.get('code')
	if not code:
		return fail('Missing OAuth code')
	res = requests.post('https://todoist.com/oauth/access_token', data={
		'client_id': os.environ['CLIENT_ID'],
		'client_secret': os.environ['CLIENT_SECRET'],
		'code': code,
	}).json()
	if 'error' in res:
		return fail('OAuth failed: ' + res['error'])
	token = res['access_token']
	userinfo = requests.post('https://api.todoist.com/sync/v8/sync', data={
		'token': token,
		'sync_token': '*',
		'resource_types': '["user"]',
	}).json()['user']
	userid = userinfo['id']
	with Client() as client:
		if not client.account_exists(userid):
			return fail('Account is not known. Ask the admin to add your userid: ' + str(userid))
		res = client.set_token(userid, token)
		if res != 'ok':
			return fail('Setting token failed: ' + res)
	session['userid'] = userid
	session['full_name'] = userinfo['full_name']
	session['avatar'] = userinfo['avatar_big']
	session['timezone'] = userinfo['tz_info']
	return redirect(url_for('config'))


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000, debug=True)
