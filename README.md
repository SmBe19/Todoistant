# Todoistant
Assistant for Todoist

not created by, affiliated with, or supported by Doist

## How to run
Start the server with `./src/main.py server`. This will start a server listening on a socket for the frontend and command line tool. Furthermore, it starts the runner which runs the assistants.

Start the frontend with `./src/main.py frontend` (for debugging, run with `./src/frontend/frontend.py`). You have to setup an OAuth application with Todoist and save the config in `secrets.env`.

To add an account, run `./src/main.py add_account` with your userid. Set the token with `./src/main.py set_token` or use the frontend for OAuth. Then, enable assistants with `./src/main.py enable <userid> <assistant> <true/false>`.
