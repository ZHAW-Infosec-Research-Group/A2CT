"""
Validators to test a HTTP response for access control vulnerabilities

Classes:
Validator
StatuscodeValidator
RedirectValidator
ContentSimilarityValidatorReplay
RegexMatchValidator
"""


import abc
import json
import re
import logging
from modules import content_matching


class Validator(object, metaclass=abc.ABCMeta):
    """ Abstract base class for validators """

    def __init__(self, source_data, replay_response):
        self.source_data = source_data
        self.replay_response = replay_response

    @abc.abstractmethod
    def validate(self):
        pass


class StatuscodeValidator(Validator):
    """ Check the status code of the response

    Keyword arguments:

    source_data -- Data of the request
    replay_response -- Response object
    full_mode -- Switch for full mode

    """

    def __init__(self, source_data, replay_response, full_mode):
        super().__init__(source_data, replay_response)
        self.full_mode = full_mode

    def validate(self):

        if self.replay_response.status_code == 401 or self.replay_response.status_code == 403:
            return False

        if self.full_mode == 'off':
            if str(self.replay_response.status_code).startswith('2'):
                return True
            else:
                return False
        else:
            if 200 <= self.replay_response.status_code <= 302 or self.replay_response.status_code == 307:
                return True
            if 302 < self.replay_response.status_code < 400:
                return False


class RedirectValidator(Validator):
    """ Check the redirect location

    Keyword arguments:

    source_data -- Data of the request
    replay_response -- Response object

    """

    def __init__(self, source_data, replay_response):
        super().__init__(source_data, replay_response)

    def validate(self):
        if not self.source_data[9]:
            return True

        source_response_headers = json.loads(self.source_data[9])
        if 'Location' not in source_response_headers:
            return True

        logging.debug('RedirectValidator: Comparing %s and %s' % (source_response_headers['Location'], self.replay_response.headers.get('Location')))
        return source_response_headers['Location'] == self.replay_response.headers.get('Location')


class ContentSimilarityValidatorReplay(Validator):
    """ Check if the response from the replay is similar to the original response (replay testing)

    Keyword arguments:

    source_data -- Data of the request
    username_user_1 -- Username of first user
    username_user_2 -- Username of second user
    replay_response -- Response object
    cursor -- Cursor of the database connection
    inter_threshold -- Threshold for the Intersection algorithm
    matching_mode -- The smatching mode to use
    db_log_level -- Level of logging in the database
    stripping_tags -- HTML tags that should be stripped during content matching

    """

    def __init__(self, source_data, replay_response, cursor, username_user_1, username_user_2, inter_threshold, matching_mode, matching_debug, db_log_level, stripping_tags):
        super().__init__(source_data, replay_response)
        self.cursor = cursor
        self.username_user_1 = username_user_1
        self.username_user_2 = username_user_2
        self.inter_threshold = inter_threshold
        self.matching_mode = matching_mode
        self.matching_debug = matching_debug
        self.db_log_level = db_log_level
        self.stripping_tags = stripping_tags

    def validate(self):
        request_url = self.source_data[4]
        method = self.source_data[6]
        logging.debug('Starting ContentSimilarityValidator for %s' % request_url)
        return content_matching.get_similarity_result(self.cursor, 'ContentSimilarityValidatorReplay', self.username_user_1,
                                                      self.username_user_2, method, request_url, None, self.source_data[10],
                                                      self.replay_response.content, self.inter_threshold, self.matching_mode,
                                                      self.matching_debug, self.db_log_level, self.stripping_tags)


class RegexMatchValidator(Validator):
    """ Check if the respoonse contains a predefined regular expression

    Keyword arguments:

    source_data -- Data of the request
    replay_response -- Response object
    regex_to_match -- Regex that will be matched by the validator

    """

    def __init__(self, source_data, replay_response, regex_to_match):
        super().__init__(source_data, replay_response)
        self.regex_to_match = regex_to_match

    def validate(self):
        if re.search(self.regex_to_match, self.replay_response.text, re.MULTILINE):
            return True
