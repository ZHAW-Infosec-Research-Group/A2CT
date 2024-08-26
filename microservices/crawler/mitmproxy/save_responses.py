"""
Mitmproxy script to save responses of proxied requests to database
"""


import sqlite3
import os
import json
import logging

logging.getLogger().setLevel(logging.INFO)

current_crawling_user = os.environ['user']
current_crawler = os.environ['crawler']
duplicate_check = os.environ['duplicate_check']


class ResponseSaver():

    def __init__(self):
        conn = sqlite3.connect('/home/mitmproxy/db_volume/responses.db')
        c = conn.cursor()

        self.table_name = 'crawling_results'

        c.execute(f'''CREATE TABLE IF NOT EXISTS {self.table_name} (id integer PRIMARY KEY NOT NULL, first_user text NOT NULL, crawler text NOT NULL, 
        request_url text NOT NULL, request_header text NOT NULL, request_method text NOT NULL, request_body blob NOT NULL, response_status_code text NOT NULL, 
        response_header text NOT NULL, response_body blob NOT NULL)''')
        conn.commit()
        conn.close()

    def response(self, flow):
        if flow.request.url.endswith('?'):
            flow.request.url = flow.request.url[:-1]

        conn = sqlite3.connect('/home/mitmproxy/db_volume/responses.db')
        c = conn.cursor()

        if duplicate_check == 'on':
            # Do a duplicate check before attempting to insert a new http request into the DB
            if not c.execute(f'SELECT request_url from {self.table_name} where first_user = ? and request_url = ? and request_method = ? and request_header = ? and request_body = ?',
                             (current_crawling_user, flow.request.url, flow.request.method, json.dumps(dict(flow.request.headers)), flow.request.content)).fetchall():
                c.execute(f'INSERT OR IGNORE INTO {self.table_name} VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                    current_crawling_user, current_crawler, flow.request.url, json.dumps(dict(flow.request.headers)),
                    flow.request.method, flow.request.content, flow.response.status_code,
                    json.dumps(dict(flow.response.headers)), flow.response.content))
        else:
            c.execute(f'INSERT OR IGNORE INTO {self.table_name} VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                current_crawling_user, current_crawler, flow.request.url, json.dumps(dict(flow.request.headers)),
                flow.request.method, flow.request.content, flow.response.status_code,
                json.dumps(dict(flow.response.headers)), flow.response.content))

        conn.commit()
        conn.close()


addons = [
    ResponseSaver()
]
