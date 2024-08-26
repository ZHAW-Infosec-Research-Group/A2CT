"""
Mitmproxy script to inject authentication headers into proxied requests
"""

import os
import base64
from http.cookies import SimpleCookie
import re
import logging

logging.getLogger().setLevel(logging.INFO)

domain_list = ''
blocked_word_list = ''
full_mode = ''


# Needed for testing because global variables that read env vars during import time are difficult to mock.
def get_env_vars():
    global domain_list, blocked_word_list, full_mode
    domain_list = os.environ['domain'].split(',')  # Support list domains
    blocked_word_list = os.environ['blocked_words']
    full_mode = os.environ['full_mode']


def request(flow):
    get_env_vars()

    # Check if there is a match with the do-not-call-pages regex
    if blocked_word_list != '' and re.search(blocked_word_list, flow.request.pretty_url) is not None:
        logging.info(f'blocked {flow.request.pretty_url} due to blocked word list {blocked_word_list}')
        flow.kill()

    # If full mode is off, only allow GET requests
    if full_mode == 'off' and not flow.request.method == 'GET':
        logging.info('blocked non-GET request because full-mode is off')
        flow.kill()

    # Check the host to block requests to external domains
    # "pretty_host" uses the Host header as preferred source, if this leads
    # to incorrect detection we can switch to "host"
    # The URL of the request can either contain exactly the same host as our target_domain or
    # be a subdomain of target_domain, meaning the host must have at least a dot (.) in front of it.
    domain_check_passed = False
    # Check if the current URL matches any of the allowed domains
    for domain in domain_list:
        if domain == flow.request.pretty_host or flow.request.pretty_host.endswith('.' + domain):
            domain_check_passed = True
            break
    if not domain_check_passed:
        logging.info(f'blocked {flow.request.pretty_url} due to being outside of allowed domain list {domain_list}')
        flow.kill()

