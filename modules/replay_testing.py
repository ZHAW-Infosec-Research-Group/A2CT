"""
Access control testing via replaying of requests

Classes:
ReplayTester
"""

import requests
import re
import base64
import logging
import json
from modules.tester import Tester
from modules.validators import (StatuscodeValidator, RedirectValidator, ContentSimilarityValidatorReplay, RegexMatchValidator)
from http.cookies import SimpleCookie
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ReplayTester(Tester):
    """ Test for access control vulnerabilities by replaying requests.

    Keyword arguments:

    username_user_1 -- Username for the first user
    auth_user_1 -- Authentication information for the first user
    username_user_2 -- Username for the second user
    auth_user_2 -- Authentication information for the second user
    source_table -- Table from which to take results from for replay testing
    db_path -- Path to the database file
    inter_threshold -- Threshold for the Intersection algorithm
    csrf_fieldname -- The field name to use for the CSRF token
    csrf_headername -- The header name to use for the CSRF token
    csrf_tokenvalue -- The value of the CSRF token
    matching_mode -- The matching mode to use
    matching_debug -- Whether matching debugging should be used
    full_mode -- Switch for full mode
    db_log_level -- Level of logging in the database
    regex_to_match -- Regular expression that indicates successful replay response
    db_name -- Name of the database file
    stripping_tags -- HTML tags that should be stripped during content matching

    """

    def __init__(self, username_user_1, auth_user_1, username_user_2, auth_user_2, source_table, db_path, inter_threshold, csrf_fieldname,
                 csrf_headername, csrf_tokenvalue, matching_mode, matching_debug, full_mode, db_log_level, stripping_tags,
                 regex_to_match='', db_name='responses.db'):

        super().__init__(username_user_1, auth_user_1, username_user_2, auth_user_2, source_table, db_path, inter_threshold, full_mode,
                         regex_to_match, db_name)

        self.csrf_fieldname = csrf_fieldname
        self.csrf_headername = csrf_headername
        self.csrf_tokenvalue = csrf_tokenvalue
        self.matching_mode = matching_mode
        self.matching_debug = matching_debug
        self.db_log_level = db_log_level
        self.stripping_tags = stripping_tags
        self.cursor.execute(
            '''CREATE TABLE IF NOT EXISTS replay_testing_results
            (id integer PRIMARY KEY, first_user TEXT, second_user TEXT, request_url TEXT, request_method TEXT, request_header TEXT,
            request_body blob, response_status_code TEXT, response_headers TEXT, request_response blob)'''
        )
        self.cursor.execute(
            '''CREATE TABLE IF NOT EXISTS vulnerabilities_after_replay_testing
            (id integer PRIMARY KEY, first_user TEXT, second_user TEXT, request_url TEXT, request_method TEXT, request_header TEXT, request_body BLOB)'''
        )
        self.conn.commit()

    def run_tests(self):
        first_user_data = self.cursor.execute(
            f'''SELECT id, first_user, second_user, crawler, request_url, request_header, request_method, cast(request_body as BLOB), response_status_code,
             response_header, response_body FROM {self.source_table} WHERE first_user = ? and second_user = ? ''',
            (self.username_user_1, self.username_user_2)
        ).fetchall()

        for data in first_user_data:
            # Cookie names from user1's auth cookies (keys of key-morsel pairs) that are used in case the public user is replayed
            user_1_auth_cookie_keys = []

            status_code_original_request = data[8]
            if str(status_code_original_request).startswith(('4', '5')):
                continue

            if data[6] == 'GET':
                if str(status_code_original_request).startswith('3'):
                    continue

            logging.debug(f'Replaying {data[6]} {data[4]}')
            cookies = {}
            headers = {}

            if data[5]:
                headers = json.loads(data[5])

            if headers and 'Cookie' in headers:
                # keep existing cookies
                cookie = SimpleCookie()
                cookie.load(headers['Cookie'])
                for key, morsel in cookie.items():
                    cookies[key.strip()] = morsel.value.strip()

            # Remove "default" headers if present
            if headers:
                headers.pop('Authorization', None)
                headers.pop('Cookie', None)
                headers.pop('Host', None)
                headers.pop('Accept-Encoding', None)
                headers.pop('Connection', None)
                if (self.csrf_headername != ''):
                    headers.pop(self.csrf_headername, None)
                    headers[self.csrf_headername] = self.csrf_tokenvalue

            if 'Cookie' in self.auth_user_1:
                # Get keys form auth cookie keys from auth_user_1
                auth_user_1_content = self.auth_user_1.split()[1]
                user_1_cookies = SimpleCookie()
                user_1_cookies.load(auth_user_1_content)
                user_1_auth_cookie_keys = list(user_1_cookies.keys())  # remember the auth cookie keys in case user 2 is public user
                try:
                    auth_cookie_user_2 = self.auth_user_2.split()[1]
                except IndexError:
                    # If we land here the second user is the public user
                    auth_cookie_user_2 = ''
                auth_cookie_content = SimpleCookie()
                auth_cookie_content.load(auth_cookie_user_2)
                if auth_cookie_content:
                    # This loop only executes if auth_cookie_content actually contains items
                    for key, morsel in auth_cookie_content.items():
                        cookies[key] = morsel.value
                else:
                    # user2 is public user: we have to clear the auth cookies currently present in the cookies dict
                    # so that the public user doesn't get session ids of other users, which would falsify the replay testing results
                    for key in user_1_auth_cookie_keys:
                        cookies.pop(key)

            if 'JWT' in self.auth_user_1:
                headers['Authorization'] = 'Bearer' + ' ' + self.auth_user_2

            if 'HTTP_Basic_Auth' in self.auth_user_1:
                http_basic_auth_encoded = base64.b64encode(self.auth_user_2)
                headers['Authorization'] = 'Bearer' + ' ' + http_basic_auth_encoded

            # Replace the synchronizer token value in the request body
            # e.g. if csrf_fieldname is "form_key", regex will be "form_key=[^&]+" and the old token will be replaced with a fresh one
            if self.csrf_fieldname != '' and self.csrf_tokenvalue != '':
                regex = self.csrf_fieldname + r"=[^&]+"
                databody = re.sub(regex, self.csrf_fieldname + "=" + self.csrf_tokenvalue, data[7].decode('utf-8'))
            else:
                databody = data[7]

            # Prepare and send the request separately instead of in one go with requests.request() so that we
            # can exract the headers as they are sent (containing the supplied cookies)
            replay_request = requests.Request(
                method=data[6],
                url=data[4],
                data=databody,
                cookies=cookies,
                headers=headers,
            )
            prepared_request = replay_request.prepare()
            session = requests.Session()
            replay_response = session.send(prepared_request, verify=False, allow_redirects=False)

            self.cursor.execute(
                f'INSERT INTO replay_testing_results VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    self.username_user_1,
                    self.username_user_2,
                    replay_response.url,
                    replay_response.request.method,
                    json.dumps(dict(prepared_request.headers)),
                    databody,
                    replay_response.status_code,
                    json.dumps(dict(replay_response.headers)),
                    replay_response.content
                )
            )

            statuscode_validator = StatuscodeValidator(data, replay_response, self.full_mode)
            if statuscode_validator.validate():
                logging.debug('StatuscodeValidator successful for %s %s with status code %d' % (
                    data[6], data[4], int(replay_response.status_code)))
            else:
                continue

            if str(status_code_original_request).startswith('3'):
                redirect_validator = RedirectValidator(data, replay_response)
                if redirect_validator.validate():
                    logging.debug('RedirectValidator successful for %s %s' % (data[6], data[4]))
                    self.cursor.execute(
                        'INSERT INTO vulnerabilities_after_replay_testing VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                        (
                            self.username_user_1,
                            self.username_user_2,
                            data[4],
                            data[6],
                            data[5],
                            data[7]
                        )
                    )
                    self.conn.commit()
                    continue
                else:
                    continue

            if self.regex_to_match:
                regex_match_validator = RegexMatchValidator(data, replay_response, self.regex_to_match)
                if regex_match_validator.validate():
                    logging.debug('RegexMatchValidator successful for %s' % data[4])
                else:
                    continue

            content_similarity_validator = ContentSimilarityValidatorReplay(data, replay_response, self.cursor, self.username_user_1, self.username_user_2,
                                                                            self.inter_threshold, self.matching_mode, self.matching_debug, self.db_log_level,
                                                                            self.stripping_tags)
            if content_similarity_validator.validate():
                logging.debug('ContentSimilarityValidatorReplay successful for %s' % data[4])
                self.cursor.execute(
                    'INSERT INTO vulnerabilities_after_replay_testing VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                    (
                        self.username_user_1,
                        self.username_user_2,
                        data[4],
                        data[6],
                        data[5],
                        data[7]
                    )
                )
                self.conn.commit()

        self.conn.commit()
        self.conn.close()
