#!/usr/bin/env python3

import base64
import datetime
import os
import sys
from typing import Dict

import dotenv
import requests
from flask import Flask, render_template, session, redirect, url_for, request, flash

sys.path.append(os.path.abspath('src'))

from todoistapi.todoist_api import get_api
from assistants.assistants import ASSISTANTS
from utils.utils import utc_to_local
from client import Client

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv.load_dotenv('secrets.env')

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

assert 'CLIENT_ID' in os.environ
assert 'CLIENT_SECRET' in os.environ


@app.template_filter()
def format_datetime(value: datetime.datetime, date_format: str = '%d.%m.%Y %H:%M:%S') -> str:
    if not value:
        return '-'
    timezone = datetime.timezone(
        datetime.timedelta(
            hours=session['timezone']['hours'],
            minutes=session['timezone']['minutes']
        ),
        session['timezone']['timezone']
    )
    return utc_to_local(value, timezone).strftime(date_format)


@app.template_test()
def prio_label(value: str) -> bool:
    return value.startswith('prio')


@app.context_processor
def inject_now() -> Dict[str, object]:
    return {
        'now': datetime.datetime.utcnow(),
        'debug': app.debug,
    }


@app.route('/')
def index() -> object:
    if 'userid' in session:
        return redirect(url_for('config'))
    return render_template('index.html')


@app.route('/config')
def config() -> object:
    if 'userid' not in session:
        return redirect(url_for('index'))
    with Client() as client:
        current_config = client.get_config(session['userid'])
        enabled = {}
        for assistant in ASSISTANTS.keys():
            enabled[assistant] = assistant in current_config and current_config[assistant]['enabled']
        projects = client.get_projects(session['userid'])
        labels = client.get_labels(session['userid'])
        templates = client.get_templates(session['userid'])
        return render_template('config.html', config=current_config, enabled=enabled, projects=projects, labels=labels,
                               templates=templates)


@app.route('/config/update/<assistant>', methods=['POST'])
def update_config(assistant: str) -> object:
    if 'userid' not in session:
        return redirect(url_for('index'))
    if assistant not in ASSISTANTS.keys():
        flash('Unknown assistant ' + assistant)
        return redirect(url_for('config'))
    assist = ASSISTANTS[assistant]
    with Client() as client:
        if 'enabled' in request.form:
            client.set_enabled(session['userid'], assistant, request.form['enabled'] == 'true')

        update = {}
        for key in assist.get_config_allowed_keys():
            if key in request.form:
                intstr = int if assist.contains_int_value(key) else str
                if assist.contains_list_value(key):
                    update[key] = list(filter(bool, map(intstr, request.form.getlist(key))))
                else:
                    update[key] = intstr(request.form[key])
        if update:
            client.update_config(session['userid'], {assistant: update})
    return redirect(url_for('config'))


@app.route('/template/start', methods=['POST'])
def start_template() -> object:
    if 'userid' not in session:
        return redirect(url_for('index'))
    if 'template_id' not in request.form or 'project_id' not in request.form:
        flash('Missing argument')
        return redirect(url_for('config'))
    try:
        template_id = request.form['template_id']
        project_id = request.form['project_id']
    except ValueError:
        flash('Invalid template or project')
        return redirect(url_for('config'))
    with Client() as client:
        res = client.start_template(session['userid'], template_id, project_id)
        if res != 'ok':
            flash('Starting template failed: ' + res)
    return redirect(url_for('config'))


@app.route('/config/telegram_disconnect', methods=['POST'])
def telegram_disconnect() -> object:
    if 'userid' not in session:
        return redirect(url_for('index'))
    with Client() as client:
        client.telegram_disconnect(session['userid'])
    return redirect(url_for('config'))


@app.route('/config/telegram_connect', methods=['POST'])
def telegram_connect() -> object:
    if 'userid' not in session:
        return redirect(url_for('index'))
    if 'code' not in request.form:
        return redirect(url_for('config'))
    with Client() as client:
        res = client.telegram_connect(session['userid'], request.form['code'])
        if res != 'ok':
            flash('Connecting Telegram account failed: ' + res)
    return redirect(url_for('config'))


@app.route('/login', methods=['POST'])
def login() -> object:
    if not app.debug or not request.form['userid']:
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
def logout() -> object:
    session.clear()
    return redirect(url_for('index'))


@app.route('/oauth/redirect')
def oauth_redirect() -> object:
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
def oauth_callback() -> object:
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
    api = get_api(token, sync=False, cache=False)
    api.sync_user_info()
    with Client() as client:
        if not client.account_exists(api.user.id):
            return fail('Account is not known. Ask the admin to add your userid: ' + str(api.user.id))
        res = client.set_token(api.user.id, token)
        if res != 'ok':
            return fail('Setting token failed: ' + res)
    session['userid'] = api.user.id
    session['full_name'] = api.user.full_name
    session['avatar'] = api.user.avatar_big
    session['timezone'] = api.user.tz_info
    return redirect(url_for('config'))


@app.route('/telegram/hook/<token>', methods=['POST'])
def telegram_hook(token: str) -> str:
    with Client() as client:
        client.telegram_update(token, request.json)
    return ''


@app.route('/todoist/hook', methods=['POST'])
def todoist_hook() -> str:
    # TODO check hmac
    with Client() as client:
        client.todoist_hook(request.headers['X-Todoist-Delivery-Id'], request.json)
    return ''


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
