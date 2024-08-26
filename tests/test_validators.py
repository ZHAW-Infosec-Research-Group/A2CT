"""
Tests for validators.py.
"""


import sqlite3
import uuid
import shutil
import os
from modules import config
from requests.models import Response
from modules.validators import RedirectValidator, StatuscodeValidator, ContentSimilarityValidatorReplay, RegexMatchValidator


test_db_name = 'responses_validators_test'
test_db_temp_name = test_db_name + '_' + str(uuid.uuid4())[:6] + '.db'

test_db_path = config.database_settings['db_path_for_testing']  # directory where test db will be copied to temporarily
test_db_full_path = test_db_path + test_db_temp_name  # full path with file name

test_dir_path = os.path.dirname(os.path.abspath(__file__))


def setup_function():
    shutil.copyfile(test_dir_path + config.test_settings['resources_path'] + test_db_name + '.db', test_db_full_path)


def teardown_function():
    os.remove(test_db_full_path)


def test_statuscode_validator_authorized():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 200
    replay_response._content = b'test'
    full_mode = 'on'
    statuscode_validator = StatuscodeValidator([], replay_response, full_mode)
    assert statuscode_validator.validate()


def test_statuscode_validator_unauthorized():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 401
    replay_response._content = b'test'
    full_mode = 'on'
    statuscode_validator = StatuscodeValidator([], replay_response, full_mode)
    assert not statuscode_validator.validate()


def test_statuscode_validator_moved():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 303
    replay_response._content = b'test'
    full_mode = 'on'
    statuscode_validator = StatuscodeValidator([], replay_response, full_mode)
    assert not statuscode_validator.validate()


def test_redirect_validator():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 200
    replay_response._content = b'test'
    # mock or instantiate a Headers object to test last codepath in RedirectValidator
    # replay_response.headers = Headers(host="example.com", content_type="application/xml")

    # source_data[8] is read by RedirectValidator and parsed with json.loads(), which
    # necessitates the JSON structure of '''{"Location": "test"}''' at source_data[8] for proper test
    # redirect_validator = RedirectValidator(source_data=['', '', '', '', '', '', '', '', '''{"Location": "test"}''', 'test'],

    redirect_validator = RedirectValidator(source_data=['', '', '', '', '', '', '', '', '', '''{}'''],
                                           replay_response=replay_response)
    assert redirect_validator.validate()


def test_content_similarity_validator_replay():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 200
    replay_response._content = """{"test": "test"}"""
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()
    content_similarity_validator = ContentSimilarityValidatorReplay(source_data=['', '', '', '', '', '', '', '', '', '', """{"test": "test"}"""],
                                                                    replay_response=replay_response, cursor=cursor,
                                                                    username_user_1='donald', username_user_2='alice', inter_threshold=80,
                                                                    matching_mode='m4i', matching_debug='off', db_log_level='dev', stripping_tags=[])
    assert content_similarity_validator.validate()


def test_regex_match_validator():
    replay_response = Response()
    replay_response.code = "test"
    replay_response.error_type = "test"
    replay_response.status_code = 200
    replay_response._content = b'test'
    regex_match_validator = RegexMatchValidator([], replay_response, '[a-b]*')
    assert regex_match_validator.validate()
