'''
Tests for content_matching.py
'''

import os
import sqlite3
import uuid
import shutil
from modules import config
from modules.content_matching import (calculate_inter, get_similarity_result, get_similarity_result_based_on_contents_hashes,
                                      get_contents_hashes)

test_db_name = 'responses_content_matching_test'  # test db in tests/ folder based on marketplace crawling results
test_db_temp_name = test_db_name + '_' + str(uuid.uuid4())[:6] + '.db'

test_db_path = config.database_settings['db_path_for_testing']  # directory where test db will be copied to temporarily
test_db_full_path = test_db_path + test_db_temp_name  # full path with file name

tests_dir_path = os.path.dirname(os.path.abspath(__file__))


def setup_function():
    shutil.copyfile(tests_dir_path + config.test_settings['resources_path'] + test_db_name + '.db', test_db_full_path)


def teardown_function():
    os.remove(test_db_full_path)


def test_calculate_inter():
    input1_list = ['Test Application', 'Add Product', 'Please provide the following information to add a product:', 'Code:', 'Description:', 'Price:']
    input2_list = ['Test Application', 'Not found']

    result = calculate_inter(input1_list, input1_list)  # identical input => content similiarity of 100
    assert result == 100

    result = calculate_inter(input1_list, input2_list)  # dissimilar input => cs of 17
    assert result == 17

    result = calculate_inter('', '')  # empty content should match too
    assert result == 100


def test_get_similarity_result():
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()
    # the clazz string is written to the db but not checked during execution, so it could also just be left emtpy
    clazz = 'ContentSimilarityValidatorReplay'  # clazz value when called from filters.py,  'ContentSimilarityValidatorReplay' when called from validators.py
                                     # and 'FindingsVerifier' when called from findings_verifier.py
    method = 'GET'
    content1 = "<p>test</p>"
    content2 = "<p>test</p>"
    url1 = 'https://172.17.0.1:3443/admin_product_add'

    # similar content
    result = get_similarity_result(cursor=cursor, clazz=clazz, username_user_1="user1", username_user_2="user2", method=method, url1=url1, url2=None,
                                   content1=content1, content2=content2, inter_threshold=80, matching_mode='m4i', matching_debug='off',
                                   db_log_level='dev', stripping_tags=[])

    conn.commit()
    assert result == 1

    # dissimiliar content
    content2 = "<p>test1 test2</p>"
    result = get_similarity_result(cursor=cursor, clazz=clazz, username_user_1="user1", username_user_2="user2", method=method, url1=url1, url2=None,
                                   content1=content1, content2=content2, inter_threshold=80, matching_mode='m4i', matching_debug='off',
                                   db_log_level='dev', stripping_tags=[])

    assert result == 0
    conn.close()


def test_get_similarity_result_based_on_content_hashes():
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()
    clazz = 'ContentSimilarityValidatorReplay'
    method = 'GET'
    content1 = "<p>test</p>"
    content2 = "<p>test</p>"
    url1 = 'https://172.17.0.1:3443/admin_product_add'

    content_hahes1 = get_contents_hashes(content1, 'm4i', 'off', stripping_tags=[])
    content_hahes2 = get_contents_hashes(content2, 'm4i', 'off', stripping_tags=[])

    # similar content
    result = get_similarity_result_based_on_contents_hashes(cursor=cursor, clazz=clazz, username_user_1="user1", username_user_2="user2", method=method,
                                                            url1=url1, url2=None, content1=content1, content2=content2, contents_hashes1=content_hahes1,
                                                            contents_hashes2=content_hahes2, inter_threshold=80, matching_mode='m4i', matching_debug='off',
                                                            db_log_level='dev')

    conn.commit()
    assert result == 1

    # dissimiliar content
    content2 = "<p>test1 test </p>"
    content_hahes2 = get_contents_hashes(content2, 'm4i', 'off', stripping_tags=[])
    result = get_similarity_result_based_on_contents_hashes(cursor=cursor, clazz=clazz, username_user_1="user1", username_user_2="user2", method=method,
                                                            url1=url1, url2=None, content1=content1, content2=content2, contents_hashes1=content_hahes1,
                                                            contents_hashes2=content_hahes2, inter_threshold=80, matching_mode='m4i', matching_debug='off',
                                                            db_log_level='dev')

    assert result == 0
    conn.close()


def test_get_content_hashes():
    content = b'''<html><meta><script>console.log("hello world")</script><link><body><p>test text</p><aside>aside </aside>
                  <nav>nav </nav><header>header </header><footer>footer </footer><body></html>
               '''

    # m3 mode: strip meta, script, link tags, keep hidden values
    content_hashes = get_contents_hashes(content, 'm3i', 'off', stripping_tags=[])
    assert content_hashes.stripped_content_m3_list == ['test textaside', 'nav header footer']

    # m4 mode: strip meta, script, link, aside, nav, header, footer, return text values
    content_hashes = get_contents_hashes(content, 'm4i', 'off', stripping_tags=[])
    assert content_hashes.stripped_content_m4_list == ['test text']
