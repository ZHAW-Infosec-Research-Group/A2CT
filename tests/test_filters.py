"""
Tests for filters.py.
"""


import os
import shutil
import uuid
import pytest
import sqlite3
from modules.filters import DeduplicationFilter, PublicContentFilter, OtherUserContentFilter, StandardPagesFilter, StaticContentFilter
from modules import config

# Test db names passed to the setup_function fixture before every test
generic_filter_test_db_name = 'responses_generic_filter_test'
deduplication_filter_test_db_name = 'responses_deduplication_filter_test'
public_content_filter_test_db_name = 'responses_public_content_filter_test'
other_user_content_filter_test_db_name = 'responses_other_user_content_filter_test'

test_db_full_path = ''  # Will be set by the setup_function
test_db_path = config.database_settings['db_path_for_testing']
test_dir_path = os.path.dirname(os.path.abspath(__file__))
ignore_tokens = "tokenCSRF|csrfmiddlewaretoken|form_key"


@pytest.fixture
def setup_function(test_db_name):
    global test_db_full_path
    test_db_temp_name = test_db_name + '_' + str(uuid.uuid4())[:6] + '.db'
    test_db_full_path = test_db_path + test_db_temp_name
    shutil.copyfile(test_dir_path + config.test_settings['resources_path'] + test_db_name + '.db', test_db_full_path)


def teardown_function():
    os.remove(test_db_full_path)


# Generic filters: DeduplicationFilter, PublicContentFilter, StaticContentFilter, StandardPagesFilter
@pytest.mark.parametrize('test_db_name', [deduplication_filter_test_db_name])
def test_deduplication_filter_deduplication_mode_1(setup_function):
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    filtered_table_name = DeduplicationFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        deduplication_mode='1',
        ignore_tokens=ignore_tokens
    ).filter()

    assert filtered_table_name == 'crawling_results_after_deduplication_filter'

    '''
    # Exact duplicate filter tests
    '''
    # Check that exact duplicate (row id 28) is removed (orig: row id 1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 28')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that exact query-string duplicate (row id 29) is removed (orgi: row id 2, query string: filter=test)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    '''
    # Query-string permutations filter test
    '''
    # Check that query-string permutation (row id 33: b=1&a=1) is removed (permutation of row id 32: a=1&b=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that row id 35 is not removed (query-string b=2&a=1&c=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''
    # Deduplication_mode = 1 tests: requests bodies are ignored when comparing requests
    '''
    # Check that exact request body duplicate (row id 30) is removed (row id 8 has same request body: username=Hello+World&password=Passw0rd%21)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request body permutation (row id 34) is removed (permutation of row id 19), deduplication_mode = 1 ignores this difference
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 34')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id: 38) is removed (based on id: 19, but added parameter to request body), deduplication_mode = 1 ignores this difference
    # (id: 38, price=55&code=1234&description=testproduct&test=test does not have the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    '''JSON request body tests'''
    # Check that request body permutation (row id 41) is removed (duplicate of 39 with parameter value of "a" changed), deduplication_mode = 1 ignores this difference
    # (id: 41, {"b":"1", "a":"2"} has the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 41')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 42) is removed (duplicate of 39 with parameter additional parameter "c"), deduplication_mode = 1 ignores this difference 
    # (id: 42, {"b":"1", "a":"1", "c":"1"} doesn't have the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 37) body with BLOB 0xaabbccddeeff is removed (exact duplicate of row id 36), deduplication_mode = 1 ignores this but still removes it
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 55-58 (query-string in body), id 59-62 (json query params in body)

    # Check that request (id 55, URL: ...?a=1&b=2, body: c=1&d=1) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 61, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 62, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 63)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 64)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 67
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 69')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 68
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 70')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()


@pytest.mark.parametrize('test_db_name', [deduplication_filter_test_db_name])
def test_deduplication_filter_deduplication_mode_2(setup_function):
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    filtered_table_name = DeduplicationFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        deduplication_mode='2',
        ignore_tokens=ignore_tokens
    ).filter()

    assert filtered_table_name == 'crawling_results_after_deduplication_filter'

    '''
    # Exact duplicate filter tests
    '''
    # Check that exact duplicate (id 28) is removed (orig: id 1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 28')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that exact query-string duplicate (id 29) is removed (orig: id 2, query string: filter=test)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    '''
    # Query-string permutations filter test
    '''
    # Check that query-string permutation (id 33: b=1&a=1) is removed (permutation of id 32: a=1&b=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that id 35 is not removed (query-string b=2&a=1&c=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''
    # Deduplication_mode = 2 tests: requests bodies are compared but only recognize different parameter names, not parameter values
    '''
    # Check that exact request body duplicate (id 30) is removed (id 8 has same request body: username=Hello+World&password=Passw0rd%21)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request body permutation (id 34) is removed (permutation of id 19), deduplication_mode = 2 treats them as equal
    # (id: 34, price=55&code=1234&description=testproduct has the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 34')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id: 38) is NOT removed (based on id: 19, but added parameter to request body), deduplication_mode = 2 treats them as different
    # (id: 38, price=55&code=1234&description=testproduct&test=test does not have the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''JSON request body tests'''
    # Check that request body permutation (id 41) is removed (duplicate of 39 with parameter value of "a" changed), deduplication_mode = 2 treats them as equal
    # (id: 41, {"b":"1", "a":"2"} has the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 41')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 42) is NOT removed (duplicate of 39 with parameter additional parameter "c"), deduplication_mode = 2 treats them as different
    # (id: 42, {"b":"1", "a":"1", "c":"1"} doesn't have the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request body with BLOB 0xaabbccddeeff is removed (exact duplicate of id 36), deduplication_mode = 2 treats them as equal
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that request id 43 exists
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that id 44 - 47 got deleted as duplicates of 43

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=2, dedup mode 2 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=1&b=, dedup mode 2 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=, dedup mode 2 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=, first request of this type, should not bet deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=1, dedup mode 2 should delete this as duplicate of request id 51
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 55-58 (query-string in body), id 59-62 (json query params in body)

    # Check that request (id 55, URL: ...?a=1&b=2, body: c=1&d=1) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 59, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 61, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 62, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 63)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 64)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 67
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 69')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 68
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 70')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()


@pytest.mark.parametrize('test_db_name', [deduplication_filter_test_db_name])
def test_deduplication_filter_deduplication_mode_3(setup_function):
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    filtered_table_name = DeduplicationFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        deduplication_mode='3',
        ignore_tokens=ignore_tokens
    ).filter()

    assert filtered_table_name == 'crawling_results_after_deduplication_filter'

    '''
    # Exact duplicate filter tests
    '''
    # Check that exact duplicate (id 28) is removed (orig: id 1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 28')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that exact query-string duplicate (id 29) is removed (orgi: id 2, query string: filter=test)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    '''
    # Query-string permutations filter test
    '''
    # Check that query-string permutation (id 33: b=1&a=1) is removed (permutation of id 32: a=1&b=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that id 35 is not removed (query-string b=2&a=1&c=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''
    # Deduplication_mode = 3 tests: requests bodies are compared with parameter names AND parameter values
    '''
    # Check that exact request body duplicate (id 30) is removed (id 8 has same request body: username=Hello+World&password=Passw0rd%21)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request body permutation (id 34) is removed (permutation of id 19), deduplication_mode = 3 treats them as equal
    # (id: 34, price=55&code=1234&description=testproduct has the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 34')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id: 38) is NOT removed (based on id: 19, but added parameter to request body), deduplication_mode = 3 treats them as different
    # (id: 38, price=55&code=1234&description=testproduct&test=test does not have the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''JSON request body tests'''
    # Check that request body permutation (id 41) is removed (duplicate of 39 with parameter value of "a" changed), deduplication_mode = 3 treats them as equal
    # (id: 41, {"b":"1", "a":"2"} has the same parameter names as (id: 39, {"b":"1", "a":"1"}) but different values
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 41')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 42) is NOT removed (duplicate of 39 with parameter additional parameter "c"), deduplication_mode = 3 treats them as different
    # (id: 42, {"b":"1", "a":"1", "c":"1"} doesn't have the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 37) body with BLOB 0xaabbccddeeff is removed (exact duplicate of id 36), deduplication_mode = 3 treats them as equal
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that request id 43 exists
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that id 44 - 47 got deleted as duplicates of 43

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=2, dedup mode 3 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=1&b=, dedup mode 3 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=, dedup mode 3 should delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=, first request of this type, should not bet deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=1, dedup mode 3 should delete this as duplicate of request id 52
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: d=&c=1, dedup mode 3 should delete this as duplicate of request id 52
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 55-58 (query-string in body), id 59-62 (json query params in body)

    # Check that request (id 55, URL: ...?a=1&b=2, body: c=1&d=1) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&b=1, body: c=1&d=1) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?b=2&b=2, body: d=1&c=2) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&b=1, body: c=1&d=1&e=1) is not removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 59, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 61, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 62, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 63)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 64)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 67
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 69')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 68
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 70')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()


@pytest.mark.parametrize('test_db_name', [deduplication_filter_test_db_name])
def test_deduplication_filter_deduplication_mode_4(setup_function):
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    filtered_table_name = DeduplicationFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        deduplication_mode='4',
        ignore_tokens=ignore_tokens
    ).filter()

    assert filtered_table_name == 'crawling_results_after_deduplication_filter'

    '''
    # Exact duplicate filter tests
    '''
    # Check that exact duplicate (id 28) is removed (orig: id 1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 28')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that exact query-string duplicate (id 29) is removed (orgi: id 2, query string: filter=test)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    '''
    # Query-string permutations filter test
    '''
    # Check that query-string permutation (id 33: b=1&a=1) is removed (permutation of id 32: a=1&b=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that id 35 is not removed (query-string b=2&a=1&c=1)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''
    # Deduplication_mode = 4 tests: requests bodies are compared with parameter names AND parameter values
    '''
    # Check that exact request body duplicate (id 30) is removed (id 8 has same request body: username=Hello+World&password=Passw0rd%21)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request body permutation (id 34) is removed (permutation of id 19), deduplication_mode = 4 treats them as equal
    # (id: 34, price=55&code=1234&description=testproduct has the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 34')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id: 38) is NOT removed (based on id: 19, but added parameter to request body), deduplication_mode = 4 treats them as different
    # (id: 38, price=55&code=1234&description=testproduct&test=test does not have the same parameter names as (id: 19, code=1234&description=testproduct&price=55)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    '''JSON request body tests'''
    # Check that request body permutation (id 41) is not removed (duplicate of 39 with parameter value of "a" changed), deduplication_mode = 4 treats them as different
    # (id: 41, {"b":"1", "a":"2"} has the same parameter names as (id: 39, {"b":"1", "a":"1"}) but different values
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 41')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 42) is NOT removed (duplicate of 39 with parameter additional parameter "c"), deduplication_mode = 4 treats them as different
    # (id: 42, {"b":"1", "a":"1", "c":"1"} doesn't have the same parameter names as (id: 39, {"b":"1", "a":"1"})
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 37) body with BLOB 0xaabbccddeeff is removed (exact duplicate of id 36), deduplication_mode = 3 treats them as equal
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that request id 43 exists
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that id 44 - 47 got deleted as duplicates of 43

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=2, dedup mode 4 should not delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=1&b=, dedup mode 4 should not delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=, dedup mode 4 should not delete this as duplicate of request id 48
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=, first request of this type, should not bet deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=1, dedup mode 4 should not delete this as duplicate of request id 52
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: d=&c=1, dedup mode 4 should delete this as duplicate of request id 52
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 55-58 (query-string in body), id 59-62 (json query params in body)

    # Check that request (id 55, URL: ...?a=1&b=2, body: c=1&d=1) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&b=1, body: c=1&d=1) is removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?b=2&b=2, body: d=1&c=2) is not removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 58, URL: ...?b=2&b=1, body: c=1&d=1&e=1) is not removed as duplicate of id 55
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 59, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is not removed
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 61, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is not removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 62, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 59
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 63)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 64)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should not be deleted
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 67
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 69')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 68
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 70')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()


@pytest.mark.parametrize('test_db_name', [public_content_filter_test_db_name])
def test_public_content_filter_deduplication_mode_1(setup_function):
    filtered_table_name = PublicContentFilter(
        'crawling_results_after_deduplication_filter',
        test_db_full_path,
        deduplication_mode='1',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # normal duplicate
    # donald 10, public 1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 10')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string exact duplicate
    # donald 11, public 2
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 11')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params
    # donald 29: products?filter=test&b=1, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values
    # donald 30: products?a=2&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 31: products?a=1&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 31')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body query string, deduplication_mode 1 ignores all request bodies and treats the requests as duplicates
    # query string exact duplicate
    # donald 18: productId=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 18')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 32: productId=1&test=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 32')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different values (dedup 2 sees this as duplicate)
    # donald 33: productId=2, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different order
    # donald 35: c=1&b=1&a=1, public 34: a=1&b=1&c=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body JSON tests
    # query string exact duplicate
    # donald 37: {"a":"1", "b":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 38: {"a":"1", "c":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different values (dedup 2 sees this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 39')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different order
    # donald 40: {"b":"1", "a":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 40')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 61)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 62)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 65
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 66
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_public_content_filter'


@pytest.mark.parametrize('test_db_name', [public_content_filter_test_db_name])
def test_public_content_filter_deduplication_mode_2(setup_function):
    filtered_table_name = PublicContentFilter(
        'crawling_results_after_deduplication_filter',
        test_db_full_path,
        deduplication_mode='2',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # normal duplicate
    # donald 10, public 1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 10')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string exact duplicate
    # donald 11, public 2
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 11')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params
    # donald 29: products?filter=test&b=1, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values
    # donald 30: products?a=2&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 31: products?a=1&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 31')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body query string, deduplication_mode = 2 ignores all request bodies which only differe in values, not parameter names
    # query string exact duplicate
    # donald 18: productId=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 18')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 32: productId=1&test=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 32')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate)
    # donald 33: productId=2, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different order
    # donald 35: c=1&b=1&a=1, public 34: a=1&b=1&c=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body JSON
    # query string exact duplicate
    # donald 37: {"a":"1", "b":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 38: {"a":"1", "c":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 39')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string same params different order
    # donald 40: {"b":"1", "a":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 40')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=1&b=, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 2 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: d=&c=1, dedup mode 2 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 61)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 62)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 65
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 66
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_public_content_filter'


@pytest.mark.parametrize('test_db_name', [public_content_filter_test_db_name])
def test_public_content_filter_deduplication_mode_3(setup_function):
    filtered_table_name = PublicContentFilter(
        'crawling_results_after_deduplication_filter',
        test_db_full_path,
        deduplication_mode='3',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # normal duplicate
    # donald 10, public 1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 10')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string exact duplicate
    # donald 11, public 2
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 11')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params
    # donald 29: products?filter=test&b=1, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values
    # donald 30: products?a=2&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 31: products?a=1&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 31')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body query string
    # query string exact duplicate
    # donald 18: productId=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 18')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 32: productId=1&test=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 32')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate, dedup 3 & 4 not)
    # donald 33: productId=2, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 35: c=1&b=1&a=1, public 34: a=1&b=1&c=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body JSON
    # query string exact duplicate
    # donald 37: {"a":"1", "b":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2, 3, & 4 see as different)
    # donald 38: {"a":"1", "c":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate, dedup 3 & 4 not)
    # donald 39: {"a":"1", "b":"2"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 39')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 40: {"b":"1", "a":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 40')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=1&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 3 should not delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: d=&c=1, dedup mode 3 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is not removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 61)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 62)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 65
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 66
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_public_content_filter'


@pytest.mark.parametrize('test_db_name', [public_content_filter_test_db_name])
def test_public_content_filter_deduplication_mode_4(setup_function):
    filtered_table_name = PublicContentFilter(
        'crawling_results_after_deduplication_filter',
        test_db_full_path,
        deduplication_mode='4',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # normal duplicate
    # donald 10, public 1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 10')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string exact duplicate
    # donald 11, public 2
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 11')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params
    # donald 29: products?filter=test&b=1, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 29')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values
    # donald 30: products?a=2&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 30')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 31: products?a=1&filter=test, public 28: products?filter=test&a=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 31')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body query string
    # query string exact duplicate
    # donald 18: productId=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 18')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2 & 3 see as different)
    # donald 32: productId=1&test=1, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 32')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate, dedup 3 & 4 not)
    # donald 33: productId=2, public 9: productId=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 33')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 35: c=1&b=1&a=1, public 34: a=1&b=1&c=1
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 35')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # request body JSON
    # query string exact duplicate
    # donald 37: {"a":"1", "b":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 37')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # query string but not same params (dedup 2, 3, & 4 see as different)
    # donald 38: {"a":"1", "c":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 38')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different values (dedup 2 sees this as duplicate, dedup 3 & 4 not)
    # donald 39: {"a":"1", "b":"2"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 39')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # query string same params different order
    # donald 40: {"b":"1", "a":"1"}, public 36: {"a":"1", "b":"1"}
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 40')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41

    # "content-type": "application/x-www-form-urlencoded"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 42')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 43')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 44')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 45')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    # body: a=1&b=2, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 46')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 47')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=1&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 48')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 49')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=, first request of this type, should be deleted because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 50')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 3 should not delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 51')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: d=&c=1, dedup mode 3 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 52')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 53')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 54')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is not removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 55')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 56')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from user public
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 57')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 58')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 59')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 60')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 61')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 62')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 61)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 63')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted (dupe of id 62)
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 64')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 65')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the public user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 66')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 65
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 67')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as dupe of id 66
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE id = 68')
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_public_content_filter'


@pytest.mark.parametrize('test_db_name', [generic_filter_test_db_name])
def test_standard_pages_filter(setup_function):
    standard_pages = "about.php,credits.php,TEST,Test,tEsT,test2"  # some of these have are identical/have no effect unless we the case sensitve tests
    # by default, the following standard pages are always used:
    # self.pages_to_filter = ['index', 'contact', 'about', 'login', 'logout', 'help']

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # Currently, URLs are treated case insensitive. If we want to change this, the two lines below have to be uncommented
    # to set the case_sensitive_like to true, so comparisons with LIKE can be done case sensitive.
    # cursor.execute('PRAGMA case_sensitive_like = true')
    # conn.commit()

    filtered_table_name = StandardPagesFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        standard_pages=standard_pages.split(',')
    ).filter()

    # Check that the standard pages are filtered correctly
    # We use the following SQL statement in filters.py to apply the standard_pages filter:
    # self.cursor.execute('DELETE FROM ' + self.table_name + ' WHERE request_url LIKE ? OR request_url LIKE ?',
    #                     ('%/' + page_to_filter, '%/' + page_to_filter + '?%'))

    # Standard page 'about' should not filter the following url
    first_user = 'donald'
    request_url = 'http://172.17.0.1:8002/admin/configure-plugin/pluginAbout'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Standard page 'about' should not filter 'about&language=en'
    first_user = 'donald'
    request_url = 'http://172.17.0.1:8002/about&language=en'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Standard page 'about' should filter 'about?language=en'
    first_user = 'donald'
    request_url = 'http://172.17.0.1:8002/about?language=en'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Case sensitivity test: uncomment if we decided to want to treat URLs in a case sensitive way

    # The path of URLs can be treated case sensitive
    # Standard page '/test' should not be filtered by standard pages TEST, Test or tEsT
    # first_user = 'donald'
    # request_url = 'http://172.17.0.1:8002/test'
    # request_method = 'GET'
    # request_body = b''
    # cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
    #                (first_user, request_url, request_method, request_body))
    # result = cursor.fetchall()
    # conn.commit()
    # assert len(result) == 1 # Needs case sensitive pragma

    # /ABOUT should not be filtered by "about"
    # first_user = 'donald'
    # request_url = 'http://172.17.0.1:8002/ABOUT'
    # request_method = 'GET'
    # request_body = b''
    # cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
    #                (first_user, request_url, request_method, request_body))
    # result = cursor.fetchall()
    # conn.commit()
    # assert len(result) == 1 # Needs case sensitive pragma

    # /test2?abc should be filtered by "test2"
    first_user = 'donald'
    request_url = 'http://172.17.0.1:8002/test2?abc'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # /test2/abc shouldn't be filtered by "test2"
    first_user = 'donald'
    request_url = 'http://172.17.0.1:8002/test2/abc'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    conn.close()

    assert filtered_table_name == 'crawling_results_after_standard_pages_filter'


@pytest.mark.parametrize('test_db_name', [generic_filter_test_db_name])
def test_static_content_filter(setup_function):
    static_content_extentions = "js,css,img,jpg,png,svg,gif"

    filtered_table_name = StaticContentFilter(
        previous_table_name='crawling_results',
        db_path=test_db_full_path,
        static_content_extensions=static_content_extentions.split(',')
    ).filter()

    assert filtered_table_name == 'crawling_results_after_static_content_filter'


# User dependent filters: OtherUserContentFilter, ContentMatchingFilter
@pytest.mark.parametrize('test_db_name', [other_user_content_filter_test_db_name])
def test_other_user_content_filter_deduplication_mode_1(setup_function):
    username_user_1 = "donald"
    username_user_2 = "alice"

    filtered_table_name = OtherUserContentFilter(
        previous_table_name='crawling_results_after_standard_pages_filter',
        db_path=test_db_full_path,
        username_user_1=username_user_1,
        username_user_2=username_user_2,
        deduplication_mode='1',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # Normal duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string exact duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params
    # donald: products?filter=test&b=1, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test&b=1'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values
    # donald: products?a=2&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=2&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald: products?a=1&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=1&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body query string, deduplication_mode 1 ignores all request bodies and treats the requests as duplicates
    # Query string exact duplicate
    # donald: productId=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see this as different)
    # donald: productId=1&test=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1&test=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params different values (deduplication mode 1 & 2 see this as duplicate)
    # donald: productId=2, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params different order
    # donald: c=1&b=1&a=1, alice: a=1&b=1&c=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'c=1&b=1&a=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body JSON tests
    # query string exact duplicate
    # donald: {"a":"1", "b":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see as different)
    # donald: {"a":"1", "c":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "c":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params different values (deduplication_mode 2 sees this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params different order
    # donald 40: {"b":"1", "a":"1"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"b":"1", "a":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?a=1&b=2'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'd=1&d=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1&e=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?a=1&b=2'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"1", "e":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate 
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=def&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_other_user_content_filter'


@pytest.mark.parametrize('test_db_name', [other_user_content_filter_test_db_name])
def test_other_user_content_filter_deduplication_mode_2(setup_function):
    username_user_1 = "donald"
    username_user_2 = "alice"

    filtered_table_name = OtherUserContentFilter(
        previous_table_name='crawling_results_after_standard_pages_filter',
        db_path=test_db_full_path,
        username_user_1=username_user_1,
        username_user_2=username_user_2,
        deduplication_mode='2',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # Normal duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string exact duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params
    # donald: products?filter=test&b=1, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test&b=1'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values
    # donald: products?a=2&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=2&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald: products?a=1&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=1&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body query string, deduplication_mode 2 ignores differences in parameter values
    # Query string exact duplicate
    # donald: productId=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see as different)
    # donald: productId=1&test=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1&test=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication mode 1 & 2 see this as duplicate)
    # donald: productId=2, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params, different order
    # donald: c=1&b=1&a=1, alice: a=1&b=1&c=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'c=1&b=1&a=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body JSON tests
    # query string exact duplicate
    # donald: {"a":"1", "b":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 & 3 see as different)
    # donald: {"a":"1", "c":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "c":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication_mode 2 sees this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string same params different order
    # donald 40: {"b":"1", "a":"1"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"b":"1", "a":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41

    content_type_url = "https://172.17.0.1:3443/content-type-test-url"

    # "content-type": "application/x-www-form-urlencoded"
    request_body = '{"content-type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    request_body = '{"Content-Type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    parse_qs_url = "https://172.17.0.1:3443/parse_qs_test"

    # body: a=1&b=2, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=1&b=, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=, dedup mode 2 should delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 2 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: d=&c=1, dedup mode 2 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "d=&c=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?a=1&b=2'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is removed as duplicate of id 53 (dedup mode 2 ignores the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'd=1&d=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53 (dedup mode 2 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1&e=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?a=1&b=2'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is removed as duplicate of id 57 (dedup mode 2 ignores the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57 (dedup mode 2 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"1", "e":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate 
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=def&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_other_user_content_filter'


@pytest.mark.parametrize('test_db_name', [other_user_content_filter_test_db_name])
def test_other_user_content_filter_deduplication_mode_3(setup_function):
    username_user_1 = "donald"
    username_user_2 = "alice"

    filtered_table_name = OtherUserContentFilter(
        previous_table_name='crawling_results_after_standard_pages_filter',
        db_path=test_db_full_path,
        username_user_1=username_user_1,
        username_user_2=username_user_2,
        deduplication_mode='3',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # Normal duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string exact duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params
    # donald: products?filter=test&b=1, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test&b=1'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values
    # donald: products?a=2&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=2&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald: products?a=1&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=1&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body query string, deduplication_mode 3 considers differences in parameter names and values
    # Query string exact duplicate
    # donald: productId=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see as different)
    # donald: productId=1&test=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1&test=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication mode 1 & 2 see this as duplicate)
    # donald: productId=2, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params, different order
    # donald: c=1&b=1&a=1, alice: a=1&b=1&c=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'c=1&b=1&a=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body JSON tests
    # query string exact duplicate
    # donald: {"a":"1", "b":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see as different)
    # donald: {"a":"1", "c":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "c":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication_mode 2 sees this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald 40: {"b":"1", "a":"1"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"b":"1", "a":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41
    content_type_url = "https://172.17.0.1:3443/content-type-test-url"

    # "content-type": "application/x-www-form-urlencoded"
    request_body = '{"content-type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    request_body = '{"Content-Type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    parse_qs_url = "https://172.17.0.1:3443/parse_qs_test"

    # body: a=1&b=2, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=1&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 3 should not delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: d=&c=1, dedup mode 3 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "d=&c=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?a=1&b=2'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is not removed as duplicate of id 53 (dedup mode 3 doesn't ignore the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'd=1&c=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53 (dedup mode 3 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1&e=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?a=1&b=2'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is not removed as duplicate of id 57 (dedup mode 3 doesn't ignore the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57 (dedup mode 3 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"1", "e":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1
    
    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate 
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=def&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_other_user_content_filter'


@pytest.mark.parametrize('test_db_name', [other_user_content_filter_test_db_name])
def test_other_user_content_filter_deduplication_mode_4(setup_function):
    username_user_1 = "donald"
    username_user_2 = "alice"

    filtered_table_name = OtherUserContentFilter(
        previous_table_name='crawling_results_after_standard_pages_filter',
        db_path=test_db_full_path,
        username_user_1=username_user_1,
        username_user_2=username_user_2,
        deduplication_mode='4',
        ignore_tokens=ignore_tokens
    ).filter()

    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()

    # Normal duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string exact duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params
    # donald: products?filter=test&b=1, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?filter=test&b=1'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values
    # donald: products?a=2&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=2&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald: products?a=1&filter=test, alice: products?filter=test&a=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/products?a=1&filter=test'
    request_method = 'GET'
    request_body = b''
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body query string, deduplication_mode 3 & 4 consider differences in parameter names and values
    # Query string exact duplicate
    # donald: productId=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2 - 4 see this as different)
    # donald: productId=1&test=1, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=1&test=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication mode 3 & 4 do not see this as duplicate)
    # donald: productId=2, alice: productId=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'productId=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params, different order
    # donald: c=1&b=1&a=1, alice: a=1&b=1&c=1
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'c=1&b=1&a=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Request body JSON tests
    # query string exact duplicate
    # donald: {"a":"1", "b":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Query string but not same params (dedup 2, 3 & 4 see as different)
    # donald: {"a":"1", "c":"1"}, alice: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "c":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different values (deduplication_mode 4 does not see this as duplicate)
    # donald 39: {"a":"1", "b":"2"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Query string same params different order
    # donald 40: {"b":"1", "a":"1"}, alice 36: {"a":"1", "b":"1"}
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/cart_add'
    request_method = 'POST'
    request_body = b'{"b":"1", "a":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check that the Content-Type header is compared in a case insensitive way
    # Check that id 42 - 45 got deleted as duplicates of 41
    content_type_url = "https://172.17.0.1:3443/content-type-test-url"

    # "content-type": "application/x-www-form-urlencoded"
    request_body = '{"content-type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    request_body = '{"Content-Type": "application/x-www-form-urlencoded"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "content-type": "application/x-www-form-urlencoded;charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # "conTent-type": "applIcation/x-wWw-form-urlencOded   ;   charset=UTF-8"
    request_body = '{"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_header = ?', (content_type_url, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # parse_qs tests: check that empty values in query string key-value pairs are parsed correctly by parse_qs()
    parse_qs_url = "https://172.17.0.1:3443/parse_qs_test"

    # body: a=1&b=2, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: a=&b=2, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b=2"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=1&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=1&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: a=&b=, dedup mode 3 should not delete this as duplicate of request id 46
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "a=&b="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: c=1&d=, first request of this type, should be deleted because it's from the second user
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d="))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # body: c=1&d=1, dedup mode 3 should not delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "c=1&d=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # body: d=&c=1, dedup mode 3 should delete this as duplicate of request id 50
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE request_url = ? AND request_body = ?', (parse_qs_url, "d=&c=1"))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Tests that check how requests with query-strings in the URL and request bodies are handled correctly
    # id 53-56 (query-string in body), id 57-60 (json query params in body)

    # Check that request (id 53, URL: ...?a=1&b=2, body: c=1&d=1) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?a=1&b=2'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 54, URL: ...?b=2&a=1, body: c=1&d=1) is removed as duplicate of id 53
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 55, URL: ...?b=2&a=1, body: d=1&c=2) is not removed as duplicate of id 53 (dedup mode 4 doesn't ignore the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'd=1&c=2'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 56, URL: ...?b=2&a=1, body: c=1&d=1&e=1) is not removed as duplicate of id 53 (dedup mode 4 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test?b=2&a=1'
    request_method = 'POST'
    request_body = b'c=1&d=1&e=1'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 57, URL: ...?a=1&b=2, body: {"c":"1", "d":"1"}) is removed because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?a=1&b=2'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 58, URL: ...?b=2&a=1, body: {"c":"1", "d":"1"}) is removed as duplicate of id 57
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"c":"1", "d":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # Check that request (id 59, URL: ...?b=2&a=1, body: {"d":"1", "c":"2"}) is not removed as duplicate of id 57 (dedup mode 4 doesn't ignore the param value differences)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"2"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    # Check that request (id 60, URL: ...?b=2&a=1, body: {"d":"1", "c":"1", "e":"1"}) is not removed as duplicate of id 57 (dedup mode 4 doesn't ignore different keys)
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/query-string-in-url-and-request-body-test2?b=2&a=1'
    request_method = 'POST'
    request_body = b'{"d":"1", "c":"1", "e":"1"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 1

    ''' Ignore token tests '''
    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"def"}, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"def"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test1, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test1'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test2?tokenCSRF=abc&a=1&b=2, request body: {"a":"1", "b":"2", "tokenCSRF":"ghi"}, should be deleted as duplicate 
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test2?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'{"a":"1", "b":"2", "tokenCSRF":"ghi"}'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=abc&a=1&b=2, request body: a=1&b=2&tokenCSRF=def, should be deleted because it's from the second user
    first_user = 'alice'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=abc&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=def'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test3, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test3'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    # URL: /ignore-tokens-test4?tokenCSRF=def&a=1&b=2, request body: a=1&b=2&tokenCSRF=ghi, should be deleted as duplicate
    first_user = 'donald'
    request_url = 'https://172.17.0.1:3443/ignore-tokens-test4?tokenCSRF=def&a=1&b=2'
    request_method = 'POST'
    request_body = b'a=1&b=2&tokenCSRF=ghi'
    cursor.execute('SELECT * FROM ' + filtered_table_name + ' WHERE first_user = ? AND request_url = ? AND request_method = ? and cast(request_body as BLOB) = ?',
                   (first_user, request_url, request_method, request_body))
    result = cursor.fetchall()
    conn.commit()
    assert len(result) == 0

    conn.close()

    assert filtered_table_name == 'crawling_results_after_other_user_content_filter'
