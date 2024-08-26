"""
Access control testing via replaying of requests

Classes:
FindingsVerifier
"""

from modules.verifier import Verifier
from modules.content_matching import get_contents_hashes, get_similarity_result, get_similarity_result_based_on_contents_hashes
import logging


class FindingsVerifier(Verifier):
    """ Test for access control vulnerabilities by replaying requests.

    Keyword arguments:

    username_user_1 -- Username for the first user
    auth_user_1 -- Authentication information for the first user
    username_user_2 -- Username for the second user
    auth_user_2 -- Authentication information for the second user
    source_table -- Table to take results from for replay testing
    db_path -- Path to the database file
    inter_threshold -- Threshold for the intersection algorithm
    string_to_match -- String that indicates successful replay response
    regex_to_match -- Regular expression that indicates successful replay response
    matching_mode -- The matching mode to use
    db_log_level -- Level of logging in the database
    db_name -- Name of the database file
    stripping_tags -- HTML tags that should be stripped during content matching

    """

    def __init__(self, username_user_1, username_user_2, db_path, inter_threshold, matching_mode, matching_debug,
                 db_log_level, stripping_tags, db_name='responses.db'):
        super().__init__(username_user_1, username_user_2, db_path, inter_threshold, db_name)
        self.matching_mode = matching_mode
        self.matching_debug = matching_debug
        self.db_log_level = db_log_level
        self.stripping_tags = stripping_tags
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS vulnerabilities_after_findings_verifier
                            (id integer PRIMARY KEY, first_user TEXT, second_user TEXT, request_url TEXT, request_method TEXT, request_header TEXT, request_body TEXT)''')
        self.conn.commit()

    def check_findings(self):
        crawling_results_user2 = self.cursor.execute('SELECT * FROM crawling_results WHERE first_user = ?', (self.username_user_2,)).fetchall()
        replay_testing_results = self.cursor.execute('SELECT * FROM replay_testing_results WHERE first_user = ? AND second_user = ?', (self.username_user_1, self.username_user_2)).fetchall()
        vulnerabilities_after_replay_testing = self.cursor.execute('SELECT * from vulnerabilities_after_replay_testing WHERE first_user = ? AND second_user = ?', (self.username_user_1, self.username_user_2)).fetchall()
        use_fast_mode = True
        user2_contents_hashes_dict = {}

        # If fast mode is used, generate stripped contents and hashes of responses_user2 and store them in dictionnary
        if (use_fast_mode):
            for record in crawling_results_user2:
                entry = get_contents_hashes(record[9], self.matching_mode, self.matching_debug, self.stripping_tags)
                user2_contents_hashes_dict[record[0]] = entry

        # Go through all findings in vulnerabilities_after_replay_testing
        for result in vulnerabilities_after_replay_testing:
            request_url = result[3]
            request_method = result[4]
            request_header = result[5]
            request_body = result[6]
            remove_finding = False

            # Only process GET requests
            if (request_method == 'GET'):

                replay_content = ''

                # Get the corresponding response received during replay testing
                for replay_response in replay_testing_results:
                    if (replay_response[3] == request_url and replay_response[4] == request_method):
                        replay_content = replay_response[9]
                        if (use_fast_mode):
                            replay_response_contents_hashes = get_contents_hashes(replay_content, self.matching_mode, self.matching_debug, self.stripping_tags)

                # Only process contents that are not empty
                if (len(replay_content) > 0):
                    # Go through responses_user2 and check if a similar response was received during crawling
                    for crawling_response in crawling_results_user2:
                        if (use_fast_mode):
                            similarity = get_similarity_result_based_on_contents_hashes(
                                self.cursor,
                                'FindingsVerifier',
                                self.username_user_1,
                                self.username_user_2,
                                request_method,
                                request_url,
                                crawling_response[3],
                                replay_content,
                                crawling_response[9],
                                replay_response_contents_hashes,
                                user2_contents_hashes_dict[crawling_response[0]],
                                self.inter_threshold,
                                self.matching_mode,
                                self.matching_debug,
                                self.db_log_level,
                                compare_subset=True
                            )
                        else:
                            similarity = get_similarity_result(
                                self.cursor,
                                'FindingsVerifier',
                                self.username_user_1,
                                self.username_user_2,
                                request_method,
                                request_url,
                                crawling_response[3],
                                replay_content,
                                crawling_response[9],
                                self.inter_threshold,
                                self.matching_mode,
                                self.matching_debug,
                                self.db_log_level,
                                self.stripping_tags
                            )
                        if (similarity):
                            remove_finding = True
                            break

            # If finding should be kept, copy it into new table results_after_findings_verifier
            if (not remove_finding):
                logging.debug(f'Found vulnerability {result[0]} {self.username_user_1} {self.username_user_2} {request_url} {request_method} {request_body}')
                self.cursor.execute('INSERT INTO vulnerabilities_after_findings_verifier VALUES (?, ?, ?, ?, ?, ?, ?)', (
                    result[0], self.username_user_1, self.username_user_2, request_url, request_method, request_header, request_body))

        self.conn.commit()
        self.conn.close()
