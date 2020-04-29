#!/usr/bin/env python3

import os

import dotenv
from flask import Flask

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
dotenv.load_dotenv('secrets.env')

app = Flask(__name__)


@app.route('/')
def index():
	return 'Hi'


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000, debug=True)
