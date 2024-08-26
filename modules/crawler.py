"""
Main crawling component which is responsible for spawning the individual crawlers and collecting the results.

Classes:
Crawler

"""

import logging
from modules.docker_service import DockerService
import time
from modules.utils import authenticate_application, reset_application, get_auth_config
import os


class Crawler():
    """ Orchestrate crawling of the target with different crawlers.

    Keyword arguments:
    target_url -- Target URL to crawl.
    target_domain -- Target domain to prevent following of external links.
    authsearch -- Authentication data for the current user.
    user -- Username of the current user.
    db_path -- Path to the crawling database.
    configfile -- Path to the config file.
    payloadfile -- Path to the payload file.
    full_mode -- Full mode (on or off)
    duplicate_check -- Duplicate check before insertion of new requests during crawling (on or off)
    blocked_word_list -- Regular expression of pages not to crawl
    static_content_extensions -- Regular expression of extensions in URLs not to crawl
    iteration_depth -- Maximum iteration depth for clicking
    """

    crawlers = ['playwright-js']
    docker_service = DockerService()
    results = []

    def __init__(self, target_url, target_domain, authsearch, user, password, db_path, configfile, payloadfile, full_mode, duplicate_check, iteration_depth, auth_script, blocked_word_list='', static_content_extensions='', ignore_tokens=''):
        self.target_url = target_url
        self.target_domain = target_domain
        self.authsearch = authsearch
        self.auth = '' # Auth information will be filled after executing the auth script
        self.user = user
        self.password = password
        self.db_path = db_path
        self.configfile = configfile
        self.payloadfile = payloadfile
        self.blocked_word_list = blocked_word_list
        self.ignore_tokens = ignore_tokens
        self.static_content_extensions = static_content_extensions
        self.full_mode = full_mode
        self.duplicate_check = duplicate_check
        self.iteration_depth = iteration_depth
        self.auth_script = auth_script

    def start_proxy_server(self, crawler):
        """ Start mitmproxy as Docker container and return a container object. """
        logging.info('Starting proxy')
        container = self.docker_service.spawn_container(
            image_name='a2ct/mitmproxy',
            command='mitmdump -s /home/mitmproxy/scripts/add_header.py -s /home/mitmproxy/scripts/save_responses.py --set ssl_insecure',
            volumes={self.db_path: {'bind': '/home/mitmproxy/db_volume/', 'mode': 'rw'}},
            env_variables=[
                'user=' + self.user,
                'crawler=' + crawler,
                'domain=' + self.target_domain,
                'blocked_words=' + self.blocked_word_list,
                'full_mode=' + self.full_mode,
                'duplicate_check=' + self.duplicate_check
            ],
            detached=True
        )
        return container

    def start_crawling(self, reset_script, auth_script):
        """ Crawl the target page with all configured crawlers and return a list of used crawlers. """
        for crawler in self.crawlers:
            if self.full_mode == 'on':
                reset_application(reset_script)

            # Authenticate current user, creating authenticated /tmp/session.json and /tmp/state.json files
            authenticate_application(auth_script, self.user, self.password, '', '', self.configfile)

            self.auth = get_auth_config(self.configfile, self.authsearch)
            logging.info("Use cookie for " + self.authsearch + ": " + self.auth)

            proxy_container = self.start_proxy_server(crawler)
            proxy_ip_address = self.docker_service.inspect_container(
                proxy_container.id)['NetworkSettings']['Networks']['bridge']['IPAddress']
            logging.info('Starting crawling process for user {} with crawler {}'.format(self.user, crawler))
            command = '--target_url=' + self.target_url + ' '
            command += '--target_domain=' + self.target_domain
            """ Wait for mitmproxy to start and be ready to accept connections"""
            time.sleep(5)
            pwd = os.getcwd()
            # Start the crawler container pass in the authenticated state.json and session.json
            # username and password are only passed along for logging currently
            crawler_output = self.docker_service.spawn_container(
                image_name='a2ct/' + crawler,
                command=command,
                env_variables=['http_proxy=http://' + proxy_ip_address + ':8080',
                               'https_proxy=https://' + proxy_ip_address + ':8080',
                               'blocked_words=' + self.blocked_word_list,
                               'static_content_extensions=' + self.static_content_extensions,
                               'ignore_tokens=' + self.ignore_tokens,
                               'iteration_depth=' + str(self.iteration_depth),
                               'user=' + self.user,
                               'pass=' + self.password
                               ],
                volumes={self.payloadfile: {'bind': '/tmp/payload.yml', 'mode': 'rw'},
                         '/tmp/state.json': {'bind': '/tmp/state.json', 'mode': 'rw'},
                         '/tmp/session.json': {'bind': '/tmp/session.json', 'mode': 'rw'},
                        },
                detached=False,
                init=True
            )
            self.docker_service.write_container_logs(crawler_output)
            self.docker_service.write_container_logs(proxy_container)
            proxy_container.stop()
        return self.crawlers
