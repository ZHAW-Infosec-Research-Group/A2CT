"""
Utility functions for content matching during filtering, replay testing and findings verification

"""

import json
import logging
from collections import Counter
from modules.html_json_utils import (remove_tags, get_text_values, roll_out_json)


class ContentsHashes:
    stripped_content_m3_list = []
    stripped_content_m4_list = []


MATCHING_MODE_3_TAGS = ['meta', 'script', 'link']
MATCHING_MODE_4_TAGS = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer']


def write_to_db(cursor, clazz, user1, user2, method, url1, url2, inter_score_m3, inter_score_m4, result_m3i, result_m4i,
                result, mode, content1, content2, stripped_content1_m3, stripped_content2_m3, stripped_content1_m4,
                stripped_content2_m4, db_log_level):
    if db_log_level == 'dev' or (db_log_level == 'dev-reduced' and clazz == 'ContentSimilarityValidatorReplay'):
        cursor.execute('''CREATE TABLE IF NOT EXISTS matching_results 
                        (id integer PRIMARY KEY, class TEXT, first_user TEXT, second_user TEXT, method TEXT, url1 TEXT, url2 TEXT, 
                         inter_score_m3 INTEGER, inter_score_m4 INTEGER, result_m3i INTEGER, result_m4i INTEGER, result INTEGER, mode TEXT, 
                         content1 TEXT, content2 TEXT, stripped_content1_m3 TEXT, stripped_content2_m3 TEXT, stripped_content1_m4 TEXT, 
                         stripped_content2_m4 TEXT)''')
        cursor.execute('INSERT INTO matching_results VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?, ?, ?, ?)',
                       (clazz, user1, user2, method, url1, url2, inter_score_m3, inter_score_m4, result_m3i, result_m4i, result, mode,
                        content1, content2, stripped_content1_m3, stripped_content2_m3, stripped_content1_m4, stripped_content2_m4))


def calculate_inter(input1_list, input2_list, compare_subset=False):
    intersection = list((Counter(input1_list) & Counter(input2_list)).elements())
    if (compare_subset):
        maxlen = len(input1_list)
    else:
        maxlen = max(len(input1_list), len(input2_list))
    if (maxlen == 0):
        return 100
    else:
        return round(100 * len(intersection) / maxlen)


def convert_list_to_string(input):
    if (len(input) == 1):
        if (type(input[0]) != str):
            return input[0]
    return ' '.join(input)


def get_similarity_result(cursor, clazz, username_user_1, username_user_2, method, url1, url2, content1, content2,
                          inter_threshold, matching_mode, matching_debug, db_log_level, stripping_tags):
    stripped_content1_m3 = ''
    stripped_content2_m3 = ''
    stripped_content1_m4 = ''
    stripped_content2_m4 = ''

    inter_score_m3 = 0
    inter_score_m4 = 0

    if (matching_mode == 'm3i' or matching_debug == 'on'):
        stripped_content1_m3_list = get_text_values(remove_tags(content1, MATCHING_MODE_3_TAGS + stripping_tags, prettify=False))
        stripped_content2_m3_list = get_text_values(remove_tags(content2, MATCHING_MODE_3_TAGS + stripping_tags, prettify=False))
        stripped_content1_m3 = convert_list_to_string(stripped_content1_m3_list)
        stripped_content2_m3 = convert_list_to_string(stripped_content2_m3_list)
        inter_score_m3 = calculate_inter(stripped_content1_m3_list, stripped_content2_m3_list)
    if (matching_mode == 'm4i' or matching_debug == 'on'):
        try:
            json_data = json.loads(content1)
            stripped_content1_m4_list = roll_out_json(json_data, False)
        except Exception:
            stripped_content1_m4_list = get_text_values(remove_tags(content1, MATCHING_MODE_4_TAGS + stripping_tags, prettify=False))
            logging.debug(f'DATA: {stripped_content1_m4_list}')
        try:
            json_data = json.loads(content2)
            stripped_content2_m4_list = roll_out_json(json_data, False)
        except Exception:
            stripped_content2_m4_list = get_text_values(remove_tags(content2, MATCHING_MODE_4_TAGS + stripping_tags, prettify=False))
        stripped_content1_m4 = convert_list_to_string(stripped_content1_m4_list)
        stripped_content2_m4 = convert_list_to_string(stripped_content2_m4_list)
        if (matching_mode == 'm4i' or matching_debug == 'on'):
            inter_score_m4 = calculate_inter(stripped_content1_m4_list, stripped_content2_m4_list)

    # Determine similarity
    result_m3i = -1
    result_m4i = -1
    result = -1
 
    if (matching_mode == 'm3i' or matching_debug == 'on'):
        if inter_score_m3 >= inter_threshold:
            result_m3i = True
        else:
            result_m3i = False
        if (matching_mode == 'm3i'):
            result = result_m3i
    if (matching_mode == 'm4i' or matching_debug == 'on'):
        if inter_score_m4 >= inter_threshold:
            result_m4i = True
        else:
            result_m4i = False
        if (matching_mode == 'm4i'):
            result = result_m4i

    write_to_db(cursor, clazz, username_user_1, username_user_2, method, url1, url2, inter_score_m3, inter_score_m4, result_m3i, result_m4i,
                result, matching_mode, content1, content2, stripped_content1_m3, stripped_content2_m3, stripped_content1_m4, stripped_content2_m4,
                db_log_level)
    return result


def get_similarity_result_based_on_contents_hashes(cursor, clazz, username_user_1, username_user_2, method, url1, url2, content1,
                                                   content2, contents_hashes1, contents_hashes2, inter_threshold, matching_mode,
                                                   matching_debug, db_log_level, compare_subset=False):
    stripped_content1_m3 = ''
    stripped_content2_m3 = ''
    stripped_content1_m4 = ''
    stripped_content2_m4 = ''

    inter_score_m3 = 0
    inter_score_m4 = 0

    if (matching_mode == 'm3i' or matching_debug == 'on'):
        stripped_content1_m3 = convert_list_to_string(contents_hashes1.stripped_content_m3_list)
        stripped_content2_m3 = convert_list_to_string(contents_hashes2.stripped_content_m3_list)
        inter_score_m3 = calculate_inter(contents_hashes1.stripped_content_m3_list, contents_hashes2.stripped_content_m3_list)
    if (matching_mode == 'm4i' or matching_debug == 'on'):
        stripped_content1_m4 = convert_list_to_string(contents_hashes1.stripped_content_m4_list)
        stripped_content2_m4 = convert_list_to_string(contents_hashes2.stripped_content_m4_list)
        inter_score_m4 = calculate_inter(contents_hashes1.stripped_content_m4_list, contents_hashes2.stripped_content_m4_list, compare_subset)

    # Determine similarity
    result_m3i = -1
    result_m4i = -1
    result = -1
    if (matching_mode == 'm3i' or matching_debug == 'on'):
        if inter_score_m3 >= inter_threshold:
            result_m3i = True
        else:
            result_m3i = False
        if (matching_mode == 'm3i'):
            result = result_m3i
    if (matching_mode == 'm4i' or matching_debug == 'on'):
        if inter_score_m4 >= inter_threshold:
            result_m4i = True
        else:
            result_m4i = False
        if (matching_mode == 'm4i'):
            result = result_m4i

    write_to_db(cursor, clazz, username_user_1, username_user_2, method, url1, url2, inter_score_m3, inter_score_m4, result_m3i, result_m4i,
                result, matching_mode, content1, content2, stripped_content1_m3, stripped_content2_m3, stripped_content1_m4,
                stripped_content2_m4, db_log_level)
    return result


def get_contents_hashes(content, matching_mode, matching_debug, stripping_tags):
    contents_hashes = ContentsHashes()

    if (matching_mode == 'm3i' or matching_debug == 'on'):
        contents_hashes.stripped_content_m3_list = get_text_values(remove_tags(content, MATCHING_MODE_3_TAGS + stripping_tags, prettify=False))
    if (matching_mode == 'm4i' or matching_debug == 'on'):
        try:
            json_data = json.loads(content)
            contents_hashes.stripped_content_m4_list = roll_out_json(json_data, False)
        except Exception:
            contents_hashes.stripped_content_m4_list = get_text_values(remove_tags(content, MATCHING_MODE_4_TAGS + stripping_tags, prettify=False))
    return contents_hashes
