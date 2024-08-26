"""
Filters to process the raw crawling data ith the goal to eliminate requests that are not relevant during further
processing. Each filter copies the original table in the database and manipulates only the copy.

Decorator functions:
copy_table

Classes:
PublicContentFilter
OtherUserContentFilter
StaticContentFilter
StandardPagesFilter

Util functions used by DeduplicationFilter, PublicContentFilter and OtherUserContentFilter
delete_json_query_string_request_body_duplicates
delete_query_string_request_body_duplicates
get_potential_query_string_url_duplicate_requests_with_request_body
"""

import abc
import json
import logging
import sqlite3
import random
import string
import re
from functools import wraps
from urllib.parse import urlparse, parse_qs
from modules.utils import is_json
from modules.html_json_utils import decode_as_list, roll_out_json_as_dict

FORM_URL_HEADER = '''"content-type": "application/x-www-form-urlencoded'''  # missing " at the end is on purpose to allow for more parameters


def contains_form_url_header(request_header):
    return FORM_URL_HEADER in request_header.lower()


def copy_table(func):
    """ Create a temporary copy of the current table and an output table. """

    @wraps(func)
    def wrapper(self):
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.table_name + ' (id integer PRIMARY KEY, first_user TEXT, crawler TEXT, '
            'request_url TEXT, request_header TEXT, request_method TEXT, request_body BLOB, response_status_code TEXT, '
            'response_header TEXT, response_body TEXT)'
        )
        self.cursor.execute('INSERT INTO ' + self.table_name + ' SELECT * FROM ' + self.previous_table_name)
        return func(self)
    return wrapper


def copy_table_generic_filters(func):
    """ Create a temporary copy of the current table and an output table but discard public user requests. """

    @wraps(func)
    def wrapper(self):
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.table_name + ' (id integer PRIMARY KEY, first_user TEXT, crawler TEXT, '
            'request_url TEXT, request_header TEXT, request_method TEXT, request_body BLOB, response_status_code TEXT, '
            'response_header TEXT, response_body TEXT)'
        )
        self.cursor.execute('INSERT INTO ' + self.table_name + ' SELECT * FROM ' + self.previous_table_name + ' WHERE first_user != "public"')
        return func(self)
    return wrapper


# Delete requests with duplicate JSON query string request bodies
def delete_json_query_string_request_body_duplicates(self, duplicate_source_table, deletion_table, current_request_id, user_name, current_request_url,
                                                     current_request_method, current_request_json_dict, only_compare_keys):
    # If the current request url has a query-string, we have to compare other request's URLs as well as their bodies with the current one
    potential_duplicate_requests = []
    if '?' in current_request_url:
        query_param_dict, potential_query_string_duplicate_requests = get_potential_query_string_url_duplicate_requests_with_request_body(self, duplicate_source_table, user_name,
                                                                                                                                          current_request_url, current_request_id,
                                                                                                                                          current_request_method)
        # Iterate through these requests which have the form (id, request_header, request_body, request_url, request_method)
        for potential_duplicate_request in potential_query_string_duplicate_requests:
            # Extract query string as dict from current request url
            potential_duplicate_url = potential_duplicate_request[3]
            # Get query parameters as dict with urlparse and parse_qs
            parsed_url2 = urlparse(potential_duplicate_url)
            query_param_dict2 = parse_qs(parsed_url2.query, keep_blank_values=True)

            apply_ignore_tokens_to_dict(query_param_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(query_param_dict2, self.ignore_tokens)

            # Check if the query-strings of both requests have the same parameter names and values
            if query_param_dict == query_param_dict2:
                potential_duplicate_requests.append(potential_duplicate_request)
    else:
        # Get all potential duplicates of the current request
        if user_name != '' and current_request_id != -1:  # PublicContentFilter
            self.cursor.execute(f'''SELECT id, request_header, request_body FROM {duplicate_source_table}
                                WHERE id != ? AND first_user = ? AND request_url = ? AND request_method = ?''',
                                (current_request_id, user_name, current_request_url, current_request_method))
        else:  # DeduplicationFilter, OtherUserContentFilter
            self.cursor.execute(f'''SELECT id, request_header, request_body FROM {duplicate_source_table}
                                WHERE id != ? AND request_url = ? AND request_method = ?''',
                                (current_request_id, current_request_url, current_request_method))
        potential_duplicate_requests = self.cursor.fetchall()

    for potential_duplicate_request in potential_duplicate_requests:
        other_request_body = potential_duplicate_request[2]
        if is_json(other_request_body):
            other_request_json_data = json.loads(other_request_body, object_pairs_hook=decode_as_list)
            other_request_json_dict = roll_out_json_as_dict(other_request_json_data)

            apply_ignore_tokens_to_dict(current_request_json_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(other_request_json_dict, self.ignore_tokens)

            # Delete request if it's considered a duplicate according to the deduplication mode
            if self.deduplication_mode == '2' or (self.deduplication_mode == '3' and only_compare_keys):
                if current_request_json_dict.keys() == other_request_json_dict.keys():
                    self.cursor.execute(f'DELETE FROM {deletion_table} WHERE id = ?', (potential_duplicate_request[0],))
            elif (self.deduplication_mode == '3' and not only_compare_keys) or self.deduplication_mode == '4':
                if current_request_json_dict == other_request_json_dict:
                    self.cursor.execute(f'DELETE FROM {deletion_table} WHERE id = ?', (potential_duplicate_request[0],))


# Delete requests with duplicate query string request bodies
def delete_query_string_request_body_duplicates(self, duplicate_source_table, deletion_table, current_request_id, user_name, current_request_url,
                                                current_request_method, current_request_query_param_dict, only_compare_keys):
    # If the current request url has a query-string, we have to compare other request's URLs as well as their bodies with the current one
    potential_duplicate_requests = []
    if '?' in current_request_url:
        query_param_dict, potential_query_string_duplicate_requests = get_potential_query_string_url_duplicate_requests_with_request_body(self, duplicate_source_table, user_name,
                                                                                                                                          current_request_url, current_request_id,
                                                                                                                                          current_request_method)
        # Iterate through these requests which have the form (id, request_header, request_body, request_url, request_method)
        for potential_duplicate_request in potential_query_string_duplicate_requests:
            # Extract query string as dict from current request url
            potential_duplicate_url = potential_duplicate_request[3]
            # Get query parameters as dict with urlparse and parse_qs
            parsed_url2 = urlparse(potential_duplicate_url)
            query_param_dict2 = parse_qs(parsed_url2.query, keep_blank_values=True)

            apply_ignore_tokens_to_dict(query_param_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(query_param_dict2, self.ignore_tokens)

            # Check if the query-strings of both requests have the same parameter names and values
            if query_param_dict == query_param_dict2:
                potential_duplicate_requests.append(potential_duplicate_request)
    else:
        # Get all potential duplicates of the current request (we only compare request bodies)
        if user_name != '' and current_request_id != -1:  # PublicContentFilter
            self.cursor.execute(f'''SELECT id, request_header, cast(request_body as BLOB) FROM {duplicate_source_table}
                                WHERE id != ? AND first_user = ? AND request_url = ? AND request_method = ?''',
                                (current_request_id, user_name, current_request_url, current_request_method))
        else:  # DeduplicationFilter, OtherUserContentFilter
            self.cursor.execute(f'''SELECT id, request_header, cast(request_body as BLOB) FROM {duplicate_source_table}
                                WHERE request_url = ? AND request_method = ?''',
                                (current_request_url, current_request_method))
        potential_duplicate_requests = self.cursor.fetchall()

    for potential_duplicate_request in potential_duplicate_requests:
        other_request_header = potential_duplicate_request[1]
        other_request_body = potential_duplicate_request[2]
        if contains_form_url_header(other_request_header):
            try:
                other_request_body_text = other_request_body.decode('utf-8')
                other_request_query_param_dict = parse_qs(other_request_body_text, keep_blank_values=True)

                apply_ignore_tokens_to_dict(current_request_query_param_dict, self.ignore_tokens)
                apply_ignore_tokens_to_dict(other_request_query_param_dict, self.ignore_tokens)

                # Delete request if it's considered a duplicate according to the deduplication mode
                if self.deduplication_mode == '2' or (self.deduplication_mode == '3' and only_compare_keys):
                    if current_request_query_param_dict.keys() == other_request_query_param_dict.keys():
                        self.cursor.execute(f'DELETE FROM {deletion_table} WHERE id = ?', (potential_duplicate_request[0],))
                elif (self.deduplication_mode == '3' and not only_compare_keys) or self.deduplication_mode == '4':
                    if current_request_query_param_dict == other_request_query_param_dict:
                        self.cursor.execute(f'DELETE FROM {deletion_table} WHERE id = ?', (potential_duplicate_request[0],))
            except UnicodeError as e:
                logging.debug(f"Cannot decode www-form-urlencoded request body as UTF-8: {other_request_body}\nUnicodeError: {e}")


def apply_ignore_tokens_to_dict(dict, ignore_tokens):
    """For a given dictionary, blanks out the values of all keys that match the regular expression in the 'ignore_tokens' parameter

       e.g. key-value pair "tokenCRSF": ['123'] is blanked out to "tokenCSRF": [] if 'ignore_tokens' is e.g. "tokenCSRF|csrfmiddlewaretoken|form_key"
    """
    if ignore_tokens != '':
        for key in dict.keys():
            match = re.match(ignore_tokens, key)
            if match:
                dict[key] = []


def get_potential_query_string_url_duplicate_requests_with_request_body(self, duplicate_source_table, user_name, current_request_url, current_request_id, current_request_method):
    # Get base URL
    url_without_parameters = current_request_url.split('?')[0]
    # Get query parameters as dict with urlparse and parse_qs
    parsed_url = urlparse(current_request_url)
    query_param_dict = parse_qs(parsed_url.query, keep_blank_values=True)
    # Get all requests with same user, same base url with ? attached, and same request method
    if user_name != '' and current_request_id != -1:
        self.cursor.execute(f'''SELECT id, request_header, cast(request_body as BLOB), request_url, request_method FROM {duplicate_source_table}
                            WHERE id != ? AND first_user = ? AND request_method = ? AND request_url LIKE ?''',
                            (current_request_id, user_name, current_request_method, url_without_parameters + '?%'))
    else:
        self.cursor.execute(f'''SELECT id, request_header, cast(request_body as BLOB), request_url, request_method FROM {duplicate_source_table}
                            WHERE request_method = ? AND request_url LIKE ?''',
                            (current_request_method, url_without_parameters + '?%'))
    potential_duplicate_requests = self.cursor.fetchall()
    return (query_param_dict, potential_duplicate_requests)


class Filter(object, metaclass=abc.ABCMeta):
    """ Abstract base class for filters. """

    def __init__(self, previous_table_name, db_path):
        self.previous_table_name = previous_table_name
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    @abc.abstractmethod
    def filter(self):
        pass


class DeduplicationFilter(Filter):
    """ Filter duplicate requests from the crawling data and return the new table name.

    Keyword arguments:

    previous_table_name -- Name of the table created by the previous filter.
    db_path -- Path to the database file.
    deduplication_mode -- Mode of how to compare request bodies.
    ignore_tokens -- Regular expression to match request parameter names that should be ignored during comparison of requests.

    """

    def __init__(self, previous_table_name, db_path, deduplication_mode, ignore_tokens):
        super().__init__(previous_table_name, db_path)
        self.table_name = 'crawling_results_after_deduplication_filter'
        self.deduplication_mode = deduplication_mode
        if ignore_tokens:
            self.ignore_tokens = ignore_tokens
        else:
            self.ignore_tokens = ''

    @copy_table
    def filter(self):

        # Get all users from crawling_results table
        self.cursor.execute('SELECT DISTINCT first_user FROM ' + self.table_name)
        user_names = self.cursor.fetchall()
        user_names = [user_name[0] for user_name in user_names]  # extract user name from result tuple

        # Iterate through all users
        for user_name in user_names:
            logging.info(f"Deduplicating requests of user \"{user_name}\"")

            # Get all requests from the current user
            self.cursor.execute(f'''SELECT id, first_user, crawler, request_url, request_header, request_method,
                                cast(request_body as BLOB), response_status_code, response_header, response_body
                                FROM {self.table_name} WHERE first_user = (?)''', (user_name,))

            current_user_requests = self.cursor.fetchall()

            # Iterate through these requests
            for current_request in current_user_requests:
                current_request_id = current_request[0]
                current_request_user = current_request[1]
                current_request_url = current_request[3]
                current_request_header = current_request[4]
                current_request_method = current_request[5]
                current_request_body = current_request[6]

                # Check if the current request still exists in the table
                current_request_results = self.cursor.execute(f"SELECT id FROM {self.table_name} WHERE id = ?", (current_request_id,)).fetchall()
                # We skip already deleted requests to prevent duplicates from deleting each other
                if len(current_request_results) == 0:
                    continue

                # Exact duplicate filter: for current request unconditionally check for duplicates with same user,
                # url, request method, request body
                self.cursor.execute(f'''DELETE FROM {self.table_name} WHERE id != ? AND first_user = ? AND request_url = ?
                                    AND request_method = ? AND cast(request_body as BLOB) = ?''',
                                    (current_request_id, current_request_user, current_request_url, current_request_method,
                                     current_request_body))

                # Handle requests with query-strings in URL but no request body
                if '?' in current_request_url and current_request_body == b'':
                    self.remove_query_string_url_duplicates(user_name, current_request_url, current_request_id, current_request_method, must_have_request_body=False)

                # Handle requests with request bodies
                elif current_request_body != b'':
                    # Deduplication_mode 1 ignores request bodies
                    if self.deduplication_mode == '1':
                        # Remove requests that have the same request_method and request_url (for the current user)
                        if '?' in current_request_url:
                            # Handle requests that have request body and a query-string in the URL
                            self.remove_query_string_url_duplicates(user_name, current_request_url, current_request_id, current_request_method, must_have_request_body=True)
                        else:
                            # Handle requests that only have a request body (no query-string in the URL)
                            self.cursor.execute(f'DELETE FROM {self.table_name} WHERE id != ? AND first_user = ? AND request_url = ? AND request_method = ?',
                                                (current_request_id, user_name, current_request_url, current_request_method))

                    # Deduplication_mode 2, 3 & 4: try to compare request bodies (and query-strings if contained in URL)
                    else:
                        # Check if request body is JSON
                        if is_json(current_request_body):
                            try:
                                current_request_json_data = json.loads(current_request_body, object_pairs_hook=decode_as_list)
                                current_request_json_dict = roll_out_json_as_dict(current_request_json_data)
                                # Delete JSON request body duplicates
                                delete_json_query_string_request_body_duplicates(self, self.table_name, self.table_name, current_request_id, user_name, current_request_url,
                                                                                 current_request_method, current_request_json_dict, only_compare_keys=True)
                            except Exception:
                                continue
                        # Check if request body has content type 'application/x-www-form-urlencoded'
                        elif contains_form_url_header(current_request_header):
                            try:
                                request_body_text = current_request_body.decode('utf-8')
                                current_request_query_param_dict = parse_qs(request_body_text, keep_blank_values=True)
                                delete_query_string_request_body_duplicates(self, self.table_name, self.table_name, current_request_id, user_name, current_request_url,
                                                                            current_request_method, current_request_query_param_dict, only_compare_keys=True)
                            except UnicodeError as e:
                                logging.debug(f"Cannot decode www-form-urlencoded request body as UTF-8: {current_request_body}\nUnicodeError: {e}")
                        # else, request body could be arbitrary binary data and should be handled by the exact duplicate filter

        self.conn.commit()
        self.conn.close()
        return self.table_name

    def get_potential_query_string_url_duplicate_requests(self, duplicate_source_table, user_name, current_request_url, current_request_id, current_request_method, must_have_request_body):
        # Get base URL
        url_without_parameters = current_request_url.split('?')[0]
        # Get query parameters as dict with urlparse and parse_qs
        parsed_url = urlparse(current_request_url)
        query_param_dict = parse_qs(parsed_url.query, keep_blank_values=True)
        # Get all requests with same user, same base url with ? attached, and same request method
        if must_have_request_body:
            self.cursor.execute(f'''SELECT id, request_url, request_method FROM {duplicate_source_table}
                                WHERE id != ? AND first_user = ? AND request_method = ? AND request_url LIKE ? AND cast(request_body as BLOB) != ?''',
                                (current_request_id, user_name, current_request_method, url_without_parameters + '?%', b''))
        else:
            self.cursor.execute(f'''SELECT id, request_url, request_method FROM {duplicate_source_table}
                                WHERE id != ? AND first_user = ? AND request_method = ? AND request_url LIKE ? AND cast(request_body as BLOB) = ?''',
                                (current_request_id, user_name, current_request_method, url_without_parameters + '?%', b''))
        potential_duplicate_requests = self.cursor.fetchall()
        return (query_param_dict, potential_duplicate_requests)

    def remove_query_string_url_duplicates(self, user_name, current_request_url, current_request_id, current_request_method, must_have_request_body):
        query_param_dict, potential_duplicate_requests = self.get_potential_query_string_url_duplicate_requests(self.table_name, user_name,
                                                                                                                current_request_url, current_request_id,
                                                                                                                current_request_method, must_have_request_body)
        # Iterate through these requests
        for potential_duplicate_request in potential_duplicate_requests:
            # Extract query string as dict from current request url
            potential_duplicate_url = potential_duplicate_request[1]
            # Get query parameters as dict with urlparse and parse_qs
            parsed_url2 = urlparse(potential_duplicate_url)
            query_param_dict2 = parse_qs(parsed_url2.query, keep_blank_values=True)

            apply_ignore_tokens_to_dict(query_param_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(query_param_dict2, self.ignore_tokens)

            # Delete duplicate request if the query-strings of both requests have the same parameter names and values
            if query_param_dict == query_param_dict2:
                self.cursor.execute(f'DELETE FROM {self.table_name} WHERE id = ?', (potential_duplicate_request[0],))


class PublicContentFilter(Filter):
    """ Filter content received when crawling with the public user and return the new table name.

    Keyword arguments:

    previous_table_name -- Name of the table created by the previous filter.
    db_path -- Path to the database file
    deduplication_mode -- Mode of how to compare request bodies.
    ignore_tokens -- Regular expression to match request parameter names that should be ignored during comparison of requests.

    """

    def __init__(self, previous_table_name, db_path, deduplication_mode, ignore_tokens):
        super().__init__(previous_table_name, db_path)
        self.table_name = 'crawling_results_after_public_content_filter'
        self.deduplication_mode = deduplication_mode
        if ignore_tokens:
            self.ignore_tokens = ignore_tokens
        else:
            self.ignore_tokens = ''

    @copy_table_generic_filters
    def filter(self):
        # Get all public user requests
        self.cursor.execute(
            f"SELECT request_url, request_header, request_method, response_status_code, cast(request_body as BLOB) FROM {self.previous_table_name} WHERE first_user = 'public'"
        )
        public_user_requests = self.cursor.fetchall()

        # We first filter all non-public user requests that match the exact URL, method and request body of public user requests
        # This deletes the public requests, which we don't need anymore, and all duplicates of public requests by non-public user
        for public_user_request in public_user_requests:
            self.cursor.execute(
                'DELETE FROM ' + self.table_name + ' WHERE request_url = ? AND request_method = ? AND cast(request_body as BLOB) = ?',
                (public_user_request[0], public_user_request[2], public_user_request[4])
            )

        # Filter requests that have the same query parameters in the request URL as public requests but empty request bodies
        self.remove_public_query_string_url_duplicates_for_requests_without_bodies()

        # We now filter requests with request bodies that either have query-strings in their URL, their request body or in both
        for public_user_request in public_user_requests:
            current_request_url = public_user_request[0]
            current_request_header = public_user_request[1]
            current_request_method = public_user_request[2]
            current_request_body = public_user_request[4]

            if current_request_body != b'':
                # Handle requests with request bodies
                # Deduplication_mode 1 ignores request bodies
                if self.deduplication_mode == '1':
                    # Remove requests that have the same request_method and request_url as the current public request
                    if '?' in current_request_url:
                        self.remove_public_query_string_url_duplicates_for_requests_with_bodies(current_request_url, current_request_method)
                    else:
                        self.cursor.execute(f'DELETE FROM {self.table_name} WHERE request_url = ? AND request_method = ?',
                                            (current_request_url, current_request_method))

                # Deduplication_mode 2, 3 & 4: try to compare request bodies (and query-strings if contained in URL)
                else:
                    # Check if request body is JSON
                    if is_json(current_request_body):
                        try:
                            current_request_json_data = json.loads(current_request_body, object_pairs_hook=decode_as_list)
                            current_request_json_dict = roll_out_json_as_dict(current_request_json_data)
                            # Delete JSON request body duplicates
                            delete_json_query_string_request_body_duplicates(self, self.table_name, self.table_name, -1, '', current_request_url,
                                                                             current_request_method, current_request_json_dict, only_compare_keys=False)
                        except Exception:
                            continue
                    # Check if request body has content type 'application/x-www-form-urlencoded'
                    elif contains_form_url_header(current_request_header):
                        try:
                            request_body_text = current_request_body.decode('utf-8')
                            current_request_query_param_dict = parse_qs(request_body_text, keep_blank_values=True)
                            delete_query_string_request_body_duplicates(self, self.table_name, self.table_name, -1, '', current_request_url,
                                                                        current_request_method, current_request_query_param_dict, only_compare_keys=False)
                        except UnicodeError as e:
                            logging.debug(f"Cannot decode www-form-urlencoded request body as UTF-8: {current_request_body}\nUnicodeError: {e}")
                    # else, request body could be arbitrary binary data and should be handled by the exact duplicate filter

        self.conn.commit()
        self.conn.close()
        return self.table_name

    def remove_public_query_string_url_duplicates_for_requests_without_bodies(self):
        # Get all requests with query-strings in their URL and an empty request body
        requests_with_query_parameters = self.cursor.execute(f'SELECT request_url, request_method, id FROM {self.table_name} '
                                                             + 'WHERE request_url like \'%?%\' AND cast(request_body as BLOB) = ?', (b'',)).fetchall()

        for request_with_query_parameters in requests_with_query_parameters:
            url_without_parameters = str(request_with_query_parameters[0]).split("?")[0]
            parsed_url_user1 = urlparse(str(request_with_query_parameters[0]))
            dict_user1 = parse_qs(parsed_url_user1.query, keep_blank_values=True)
            # Get the public requests form the previous table
            self.cursor.execute(f"SELECT request_url, request_method FROM {self.previous_table_name} WHERE first_user = 'public' AND request_method = ? "
                                + "AND request_url LIKE ? AND cast(request_body as BLOB) = ?",
                                (str(request_with_query_parameters[1]), url_without_parameters + '?%', b''))
            public_matching_requests = self.cursor.fetchall()
            for public_request in public_matching_requests:
                parsed_url_user2 = urlparse(str(public_request[0]))
                dict_user2 = parse_qs(parsed_url_user2.query, keep_blank_values=True)
                if dict_user2 == dict_user1:
                    self.cursor.execute('DELETE FROM ' + self.table_name + ' WHERE id = ?', (str(request_with_query_parameters[2]),))

    # Remove non-public user requests that match a URL from the given public user request
    def remove_public_query_string_url_duplicates_for_requests_with_bodies(self, current_request_url, current_request_method):
        # Get base URL
        url_without_parameters = current_request_url.split('?')[0]
        # Get query parameters as dict with urlparse and parse_qs
        parsed_url = urlparse(current_request_url)
        query_param_dict = parse_qs(parsed_url.query, keep_blank_values=True)
        # Get all requests with same user, same base url with ? attached, and same request method
        self.cursor.execute(f'''SELECT id, request_url, request_method FROM {self.table_name} WHERE request_method = ? AND request_url LIKE ? AND cast(request_body as BLOB) != ?''',
                            (current_request_method, url_without_parameters + '?%', b''))
        potential_duplicate_requests = self.cursor.fetchall()

        # Iterate through these requests
        for potential_duplicate_request in potential_duplicate_requests:
            # Extract query string as dict from current request url
            potential_duplicate_url = potential_duplicate_request[1]
            # Get query parameters as dict with urlparse and parse_qs
            parsed_url2 = urlparse(potential_duplicate_url)
            query_param_dict2 = parse_qs(parsed_url2.query, keep_blank_values=True)
            # Delete duplicate request if the query-strings of both requests have the same parameter names and values

            apply_ignore_tokens_to_dict(query_param_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(query_param_dict2, self.ignore_tokens)

            if query_param_dict == query_param_dict2:
                self.cursor.execute(f'DELETE FROM {self.table_name} WHERE id = ?', (potential_duplicate_request[0],))


class StaticContentFilter(Filter):
    """ Filter static content from the crawling data and return the new table name.

    Keyword arguments:

    previous_table_name -- Name of the table created by the previous filter.
    db_path -- Path to the database file.
    static_content_extensions -- File extensions of static content.

    """

    def __init__(self, previous_table_name, db_path, static_content_extensions=None, append_or_replace='append'):
        super().__init__(previous_table_name, db_path)
        if static_content_extensions is None:
            static_content_extensions = []
        self.table_name = 'crawling_results_after_static_content_filter'
        self.extensions_to_filter = ['css', 'js']

        if static_content_extensions:
            self.extensions_to_filter.extend(static_content_extensions)

    @copy_table_generic_filters
    def filter(self):
        # Filter the new table
        for extension_to_filter in self.extensions_to_filter:
            self.cursor.execute('DELETE FROM ' + self.table_name + ' WHERE request_url LIKE ? OR request_url LIKE ?',
                                ('%.' + extension_to_filter, '%.' + extension_to_filter + '?%'))

        self.conn.commit()
        self.conn.close()
        return self.table_name


class StandardPagesFilter(Filter):
    """ Filter standard pages from the crawling data and return the new table name.

    Keyword arguments:

    previous_table_name -- Name of the table created by the previous filter.
    db_path -- Path to the database file.
    standard_pages -- List of pages to filter.

    """

    def __init__(self, previous_table_name, db_path, standard_pages=None):
        super().__init__(previous_table_name, db_path)
        if standard_pages is None:
            standard_pages = []
        self.table_name = 'crawling_results_after_standard_pages_filter'
        self.pages_to_filter = ['index', 'contact', 'about', 'login', 'logout', 'help']

        if standard_pages:
            self.pages_to_filter.extend(standard_pages)

    @copy_table_generic_filters
    def filter(self):
        # Filter the new table
        for page_to_filter in self.pages_to_filter:
            self.cursor.execute('DELETE FROM ' + self.table_name + ' WHERE request_url LIKE ? OR request_url LIKE ?',
                                ('%/' + page_to_filter, '%/' + page_to_filter + '?%'))

        self.conn.commit()
        self.conn.close()
        return self.table_name


class OtherUserContentFilter(Filter):
    """ Filter content received when crawling with the other authenticated user and return the new table name.

    Keyword arguments:

    previous_table_name -- Name of the table created by the previous filter.
    db_path -- Path to the database file.
    username_user_1 -- Username of first user.
    username_user_2 -- Username of second user.
    deduplication_mode -- Mode of how to compare request bodies.
    ignore_tokens -- Regular expression to match request parameter names that should be ignored during comparison of requests.

    """

    def __init__(self, previous_table_name, db_path, username_user_1, username_user_2, deduplication_mode, ignore_tokens):
        super().__init__(previous_table_name, db_path)
        self.username_user_1 = username_user_1
        self.username_user_2 = username_user_2
        self.deduplication_mode = deduplication_mode
        if ignore_tokens:
            self.ignore_tokens = ignore_tokens
        else:
            self.ignore_tokens = ''
        self.temp_table_name = f'crawling_results_after_other_user_content_filter_{"".join(random.choices(string.digits, k=12))}'
        self.table_name = 'crawling_results_after_other_user_content_filter'

    def filter(self):

        # Create a temp table
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.temp_table_name + ' (id integer PRIMARY KEY, first_user TEXT, second_user TEXT, crawler TEXT, '
            'request_url TEXT, request_header TEXT, request_method TEXT, request_body BLOB, response_status_code TEXT, '
            'response_header TEXT, response_body TEXT)'
        )

        # Copy data from the previous filter output into the temp table and add second user information
        data_from_source_table = self.cursor.execute(f'SELECT first_user, crawler, request_url, request_header, request_method, request_body, response_status_code, response_header, response_body from {self.previous_table_name} WHERE first_user = ?', (self.username_user_1,)).fetchall()

        for data in data_from_source_table:
            self.cursor.execute(f'INSERT INTO {self.temp_table_name} VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.username_user_1, self.username_user_2, data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8]))

        # Create an output table for the filter
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.table_name + ' (id integer PRIMARY KEY, first_user TEXT, second_user TEXT, crawler TEXT, '
            'request_url TEXT, request_header TEXT, request_method TEXT, request_body BLOB, response_status_code TEXT, '
            'response_header TEXT, response_body TEXT)'
        )

        # We first filter exact matches from the temp table
        self.cursor.execute(
            f'SELECT request_url, request_method, response_status_code, cast(request_body as BLOB) FROM {self.previous_table_name} WHERE first_user = ?', (self.username_user_2,))
        user2_requests = self.cursor.fetchall()
        for user2_request in user2_requests:
            # Delete requests form the first user which have the same url, request_method and request_body as requests made from the second user
            self.cursor.execute('DELETE FROM ' + self.temp_table_name + ' WHERE first_user = ? and second_user = ? and request_url = ? and request_method = ? AND cast(request_body as BLOB) = ?',
                                (self.username_user_1, self.username_user_2, user2_request[0], user2_request[1], user2_request[3]))

        # We now filter requests from the first user that have the same query parameters in the URL as requests from the second user but in a different order and have no request body
        self.remove_other_user_query_string_url_duplicates()

        # We now filter requests that have the same URLs and same query strings but in their request bodies
        user2_requests = self.cursor.execute(
            f'SELECT request_url, request_header, request_method, cast(request_body as BLOB) FROM {self.previous_table_name} WHERE first_user = ?',
            (self.username_user_2,)).fetchall()

        # We iterate through all requests from user2 (previous table) and delete user1 requests in the new temp table if the requests match
        for user2_request in user2_requests:
            current_request_url = user2_request[0]
            current_request_header = user2_request[1]
            current_request_method = user2_request[2]
            current_request_body = user2_request[3]

            if current_request_body != b'':

                # Deduplication_mode 1 ignores request bodies
                if self.deduplication_mode == '1':
                    # Remove requests that have the same request_method and request_url as the current user2 request
                    if '?' in current_request_url:
                        self.remove_other_user_query_string_url_duplicates_for_requests_with_bodies(current_request_url, current_request_method)
                    else:
                        self.cursor.execute(f'DELETE FROM {self.temp_table_name} WHERE request_url = ? AND request_method = ?',
                                            (current_request_url, current_request_method))

                # Deduplication_mode 2, 3 & 4: try to compare request bodies (and query-strings if contained in URL)
                else:
                    # Check if request body is JSON
                    if is_json(current_request_body):
                        try:
                            current_request_json_data = json.loads(current_request_body, object_pairs_hook=decode_as_list)
                            current_request_json_dict = roll_out_json_as_dict(current_request_json_data)
                            # Delete JSON request body duplicates
                            delete_json_query_string_request_body_duplicates(self, self.temp_table_name, self.temp_table_name, -1, '', current_request_url,
                                                                             current_request_method, current_request_json_dict, only_compare_keys=False)
                        except Exception:
                            continue
                    # Check if request body has content type 'application/x-www-form-urlencoded'
                    elif contains_form_url_header(current_request_header):
                        try:
                            request_body_text = current_request_body.decode('utf-8')
                            current_request_query_param_dict = parse_qs(request_body_text, keep_blank_values=True)
                            delete_query_string_request_body_duplicates(self, self.temp_table_name, self.temp_table_name, -1, '', current_request_url,
                                                                        current_request_method, current_request_query_param_dict, only_compare_keys=False)
                        except UnicodeError as e:
                            logging.debug(f"Cannot decode www-form-urlencoded request body as UTF-8: {current_request_body}\nUnicodeError: {e}")
                    # else, request body could be arbitrary binary data and should be handled by the exact duplicate filter

        # Write results from temp table in output table and delete temp table
        data_from_temp_table = self.cursor.execute(f'SELECT * from {self.temp_table_name}').fetchall()
        for data in data_from_temp_table:
            self.cursor.execute(f'INSERT INTO {self.table_name} VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10]))

        self.cursor.execute(f'DROP TABLE {self.temp_table_name}')

        self.conn.commit()
        self.conn.close()

        return self.table_name

    def remove_other_user_query_string_url_duplicates(self):
        # Get requests from user1
        # Todo: check if we need to onl get requests from user1 here
        requests_with_query_parameters = self.cursor.execute(f'SELECT request_url, request_method, id FROM {self.temp_table_name} '
                                                             + 'WHERE request_url like \'%?%\' AND cast(request_body as BLOB) = ?', (b'',)).fetchall()
        for request_with_query_parameters in requests_with_query_parameters:
            url_without_parameters = str(request_with_query_parameters[0]).split("?")[0]
            parsed_url_user1 = urlparse(str(request_with_query_parameters[0]))
            dict_user1 = parse_qs(parsed_url_user1.query, keep_blank_values=True)

            # Get requests from user2
            self.cursor.execute(f"SELECT request_url, request_method, id FROM {self.previous_table_name} WHERE first_user = ? AND request_method = ? AND request_url LIKE ? AND cast(request_body as BLOB) = ?",
                                (self.username_user_2, str(request_with_query_parameters[1]), url_without_parameters + '?%', b''))
            user2_matching_requests = self.cursor.fetchall()

            for user2_request in user2_matching_requests:

                parsed_url_user2 = urlparse(str(user2_request[0]))
                dict_user2 = parse_qs(parsed_url_user2.query, keep_blank_values=True)

                apply_ignore_tokens_to_dict(dict_user1, self.ignore_tokens)
                apply_ignore_tokens_to_dict(dict_user2, self.ignore_tokens)

                # Delete request from user1 if user2's request matches it
                if dict_user2 == dict_user1:
                    self.cursor.execute('DELETE FROM ' + self.temp_table_name + ' WHERE id = ?', (str(request_with_query_parameters[2]),))

    # Remove user1 requests that match a URL from the given user2 request
    def remove_other_user_query_string_url_duplicates_for_requests_with_bodies(self, current_request_url, current_request_method):
        # Get base URL
        url_without_parameters = current_request_url.split('?')[0]
        # Get query parameters as dict with urlparse and parse_qs
        parsed_url = urlparse(current_request_url)
        query_param_dict = parse_qs(parsed_url.query, keep_blank_values=True)
        # Get all requests with same base url with ? attached, and same request method from user1
        self.cursor.execute(f'SELECT id, request_url, request_method FROM {self.temp_table_name} WHERE first_user = ? '
                            + 'AND request_method = ? AND request_url LIKE ? AND cast(request_body as BLOB) != ?',
                            (self.username_user_1, current_request_method, url_without_parameters + '?%', b''))
        potential_duplicate_requests = self.cursor.fetchall()

        # Iterate through these requests
        for potential_duplicate_request in potential_duplicate_requests:
            # Extract query string as dict from current request url
            potential_duplicate_url = potential_duplicate_request[1]
            # Get query parameters as dict with urlparse and parse_qs
            parsed_url2 = urlparse(potential_duplicate_url)
            query_param_dict2 = parse_qs(parsed_url2.query, keep_blank_values=True)

            apply_ignore_tokens_to_dict(query_param_dict, self.ignore_tokens)
            apply_ignore_tokens_to_dict(query_param_dict2, self.ignore_tokens)

            # Delete request from user1 if user2's request matches it
            if query_param_dict == query_param_dict2:
                self.cursor.execute(f'DELETE FROM {self.temp_table_name} WHERE id = ?', (potential_duplicate_request[0],))
