#!/usr/bin/env python3

import base64
import os
import requests

import dotenv
from flask import Flask, render_template, session, redirect, url_for, request, flash

import sys
sys.path.append(os.path.abspath('src'))

from client import Client

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
dotenv.load_dotenv('secrets.env')

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

assert 'CLIENT_ID' in os.environ
assert 'CLIENT_SECRET' in os.environ


@app.route('/')
def index():
	if 'userid' in session:
		return redirect(url_for('config'))
	return render_template('index.html')


@app.route('/config')
def config():
	if 'userid' not in session:
		return redirect(url_for('config'))
	return render_template('config.html')


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
	}).json()
	print(userinfo)
	userid = userinfo['user']['id']
	with Client() as client:
		if not client.account_exists(userid):
			return fail('Account is not known. Ask the admin to add your userid: ' + str(userid))
		client.set_token(userid, token)
	session['userid'] = userid
	return redirect(url_for('config'))


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000, debug=True)
