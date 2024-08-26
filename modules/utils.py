""" Utility functions

Functions:
deduplicate_dicts

"""

import json
import subprocess
import yaml
import logging


def deduplicate_dicts(dictionaries):
    if len(dictionaries) == 1:
        return dictionaries[0]
    elif len(dictionaries) == 2:
        return {**dictionaries[0], **dictionaries[1]}
    else:
        return {**deduplicate_dicts(dictionaries[:-1]), **dictionaries[-1]}


def reset_application(reset_script):
    logging.info("Reset application with " + reset_script)
    subprocess.call(['python', reset_script])
    logging.debug("Application should be back up")


def authenticate_application(auth_script, user1, pass1, user2, pass2, configfile):
    logging.info("Authenticating with " + auth_script)
    command = ['node', '-e', f'require("{auth_script}").start("{user1}", "{pass1}", "{configfile}")']
    subprocess.call(command)
    if (user2 != ''):
        command2 = ['node', '-e', f'require("{auth_script}").start("{user2}", "{pass2}", "{configfile}")']
        subprocess.call(command2)


def get_auth_config(configfile, authsearch):
    if authsearch == '' or authsearch == 'public':
        return ''
    else:
        logging.debug(f'Reload cookie for {authsearch} from configuration')
        with open(configfile, 'r') as yaml_file:
            config_file = yaml.safe_load(yaml_file)
            users = config_file['auth']['tokens']
            for user_info in users:
                for username in user_info:
                    if username == authsearch:
                        return user_info[username]


def get_credentials_config(configfile, authsearch):
    if authsearch == '' or authsearch == 'public':
        return ''
    else:
        logging.debug(f'Reload credentials for {authsearch} from configuration')
        with open(configfile, 'r') as yaml_file:
            config_file = yaml.safe_load(yaml_file)
            users = config_file['auth']['users']
            for user_info in users:
                for username in user_info:
                    if username == authsearch:
                        return user_info[username]


def get_csrf_value(configfile, username):
    if username == 'public':
        return ''
    else:
        with open(configfile, 'r') as yaml_file:
            logging.debug(f'Loading csrf value for {username}')
            config_file = yaml.safe_load(yaml_file)
            csrf_type = ''
            if 'csrf_header' in config_file:
                csrf_type = 'csrf_header'
            elif 'csrf_field' in config_file:
                csrf_type = 'csrf_field'
            else:
                logging.debug("Could not find csrf_header of csrf_field entry in config file")
                return ''
            if config_file.get(csrf_type):
                csrf_values = config_file[csrf_type]['csrf_values']
                for csrf_entry in csrf_values:
                    if username == list(csrf_entry.keys())[0]:
                        return csrf_entry[username]
            logging.debug(f"Could not find csrf token for user {username}")
            return ''


def is_json(myjson):
    try:
        json.loads(myjson)
    except ValueError as e:
        logging.debug(f"ValueError: {e}")
        return False
    except TypeError as e:
        logging.error(f"utils.py::is_json: TypeError: {e}")
        return False
    return True
