"""
Entrypoint for the programm

Functions:
parse_config_file
crawling
generic_filtering
delete_table
user_dependent_filtering
create_user_combos
print_results
save_execution_time
vacuum_db
main

"""

import subprocess
import os
import sys
import argparse
import logging
import yaml
import sqlite3
import time
import itertools
from modules.crawler import Crawler
from modules.filters import (DeduplicationFilter, PublicContentFilter, StaticContentFilter, StandardPagesFilter, OtherUserContentFilter)
from modules.replay_testing import ReplayTester
from modules.findings_verifier import FindingsVerifier
from modules.utils import get_csrf_value, reset_application, get_auth_config, get_credentials_config, authenticate_application

parser = argparse.ArgumentParser()
parser.add_argument('--config', help='Configuration file in YAML format', required=True)
parser.add_argument('--run_mode', choices=['cfr', 'cfrv', 'fr', 'frv', 'r', 'rv', 'v'], help='Run mode (crawling, filtering, replay testing, verifying): cfr, cfrv, fr, frv, r, rv, v', required=True)
parser.add_argument('--full_mode', choices=['on', 'off'], help='Full mode (on, off)): on, off', required=True)
parser.add_argument('--deduplication_mode', choices=['1', '2', '3', '4'], help='Deduplication mode (1 = ignore request bodies, 2 = only compare parameter names in request bodies, 3 = (DeduplicationFilter: only compare parameter names in request bodies, PublicContentFilter/OtherUserContentFilter: compare parameter names and values in request bodies), 4 = compare parameter names and values in request bodies): 1, 2, 3, 4', required=True)
parser.add_argument('--matching_mode', choices=['m3i', 'm4i'], help='Matching mode: m3i, m4i', required=True)
parser.add_argument('--matching_debug', choices=['on', 'off'], help='Matching debugging mode (on, off)): on, off', required=True)
parser.add_argument('--db_log_level', choices=['dev', 'dev-reduced', 'prod'], help='Database log level (dev, dev-reduced, prod), dev = full logging, database can become large, dev-reduced = drastically reduces matching results table size, prod = minimal logging, deletes tables as soon as possible and only keeps final vulnerability findings table', required=True)
parser.add_argument('--duplicate_check', choices=['on', 'off'], help='Checks for duplicates in the database before inserting a new request during crawling (on, off)', default='off', required=False)
parser.add_argument('--iteration_depth', choices=range(1, 5), help='Iteration depth for clicking buttons: Positive integer (Default: 1)', type=int, default=1, required=False)


def parse_config_file(configfile):
    config_parameters = {}

    with open(configfile, 'r') as yaml_file:
        config_file = yaml.safe_load(yaml_file)

    if 'target' not in config_file or 'auth' not in config_file:
        logging.error('Config file not correctly formatted: target or auth information missing')
        sys.exit(1)

    if 'target_url' not in config_file['target'] or 'target_domain' not in config_file['target']:
        logging.error('Config file not correctly formatted: target_url or target_domain missing')
        sys.exit(1)

    if not config_file['auth']:
        logging.error('Config file not correctly formatted: auth information cannot be empty')
        sys.exit(1)

    if config_file['auth']['combinations']['type'] != 'selected' and config_file['auth']['combinations']['type'] != 'all':
        logging.error('Config file not correctly formatted: "combinations" need to be one of "selected" or "all"')
        sys.exit(1)

    config_parameters['target_url'] = config_file['target']['target_url']
    config_parameters['target_domain'] = config_file['target']['target_domain']
    config_parameters['path_to_db'] = config_file['target']['path_to_db']
    config_parameters['reset_script'] = config_file['target']['reset_script']
    config_parameters['auth_script'] = config_file['target']['auth_script']
    config_parameters['users'] = config_file['auth']['users']
    config_parameters['combinations'] = config_file['auth']['combinations']
    config_parameters['payloadfile'] = config_file['payloadfile']
    config_parameters['credentials'] = config_file['auth']['users']

    if 'csrf_field' in config_file:
        config_parameters['csrf_fieldname'] = config_file['csrf_field']['fieldname']
        config_parameters['csrf_headername'] = ''
    elif 'csrf_header' in config_file:
        config_parameters['csrf_fieldname'] = ''
        config_parameters['csrf_headername'] = config_file['csrf_header']['headername']
    else:
        config_parameters['csrf_fieldname'] = ''
        config_parameters['csrf_headername'] = ''
        config_parameters['csrf_value'] = ''

    if 'options' in config_file:
        config_parameters['standard_pages'] = config_file['options'].get('standard_pages', '')
        config_parameters['do_not_call_pages'] = config_file['options'].get('do_not_call_pages', '')
        config_parameters['static_content_extensions'] = config_file['options'].get('static_content_extensions', '')
        config_parameters['ignore_tokens'] = config_file['options'].get('ignore_tokens', '')
        config_parameters['html_stripping_tags'] = config_file['options'].get('html_stripping_tags', [])
        config_parameters['regex_to_match'] = config_file['options'].get('regex_to_match', '')
        config_parameters['inter_threshold_validating'] = config_file['options'].get('inter_threshold_validating', 80)

        if config_parameters['html_stripping_tags'] is None:
            config_parameters['html_stripping_tags'] = []
    else:
        config_parameters['standard_pages'] = ''
        config_parameters['do_not_call_pages'] = ''
        config_parameters['static_content_extensions'] = ''
        config_parameters['ignore_tokens'] = ''
        config_parameters['html_stripping_tags'] = []
        config_parameters['regex_to_match'] = ''
        config_parameters['inter_threshold_validating'] = 80

    return config_parameters


def crawling(target_url, target_domain, username, password, db_path, blocked_word_list, static_content_extensions, ignore_tokens, reset_script, auth_script, payloadfile, configfile, full_mode, duplicate_check, iteration_depth):
    crawler = Crawler(
        target_url=target_url,
        target_domain=target_domain,
        authsearch=username,
        user=username,
        password=password,
        db_path=db_path,
        configfile=configfile,
        payloadfile=payloadfile,
        full_mode=full_mode,
        blocked_word_list=blocked_word_list,
        ignore_tokens=ignore_tokens,
        static_content_extensions=static_content_extensions,
        duplicate_check=duplicate_check,
        iteration_depth=iteration_depth,
        auth_script=auth_script
    )
    logging.info(f'Starting crawling with user {username}')
    crawler.start_crawling(reset_script, auth_script)
    logging.info(f'Finished crawling with user {username}')


def generic_filtering(db_path, deduplication_mode, standard_pages, static_content_extensions, ignore_tokens, db_log_level):
    db_path = db_path + 'responses.db'

    generic_filters = [DeduplicationFilter, PublicContentFilter, StaticContentFilter, StandardPagesFilter]

    current_table_name = 'crawling_results'
    old_table_name = ''

    # Apply all generic filters
    for generic_filter in generic_filters:
        if generic_filter == DeduplicationFilter and deduplication_mode:
            filter_instance = generic_filter(
                previous_table_name=current_table_name,
                db_path=db_path,
                deduplication_mode=deduplication_mode,
                ignore_tokens=ignore_tokens
            )
            current_table_name = filter_instance.filter()
            # We do not delete the crawling_results table in the prod mode (used in FindingsVerifier)

        elif generic_filter == PublicContentFilter and deduplication_mode:
            filter_instance = generic_filter(
                previous_table_name=current_table_name,
                db_path=db_path,
                deduplication_mode=deduplication_mode,
                ignore_tokens=ignore_tokens
            )
            old_table_name = current_table_name
            current_table_name = filter_instance.filter()
            if db_log_level == 'prod':
                delete_table(db_path, old_table_name)

        elif generic_filter == StandardPagesFilter and standard_pages:
            filter_instance = generic_filter(
                previous_table_name=current_table_name,
                db_path=db_path,
                standard_pages=standard_pages.split(',')
            )
            old_table_name = current_table_name
            current_table_name = filter_instance.filter()
            if db_log_level == 'prod':
                delete_table(db_path, old_table_name)

        elif generic_filter == StaticContentFilter and static_content_extensions:
            filter_instance = generic_filter(
                previous_table_name=current_table_name,
                db_path=db_path,
                static_content_extensions=static_content_extensions.split(',')
            )
            old_table_name = current_table_name
            current_table_name = filter_instance.filter()
            if db_log_level == 'prod':
                delete_table(db_path, old_table_name)
        else:
            filter_instance = generic_filter(
                previous_table_name=current_table_name,
                db_path=db_path
            )
            old_table_name = current_table_name
            current_table_name = filter_instance.filter()
            if db_log_level == 'prod':
                delete_table(db_path, old_table_name)

    return current_table_name


def delete_table(db_path, table_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    logging.debug(f"Deleting table {table_name}")
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    cursor.execute("VACUUM")
    conn.commit()
    conn.close()


def user_dependent_filtering(db_path, current_table_name, username_user_1, username_user_2, deduplication_mode, ignore_tokens):
    db_path = db_path + 'responses.db'

    # Always run the OtherUserContentFilter
    filter_instance = OtherUserContentFilter(
        previous_table_name=current_table_name,
        db_path=db_path,
        username_user_1=username_user_1,
        username_user_2=username_user_2,
        deduplication_mode=deduplication_mode,
        ignore_tokens=ignore_tokens
    )
    current_table_name = filter_instance.filter()

    return current_table_name


def print_results(db_path, verify_findings):
    conn = sqlite3.connect(db_path + 'responses.db')
    c = conn.cursor()
    if (verify_findings):
        table = 'vulnerabilities_after_findings_verifier'
    else:
        table = 'vulnerabilities_after_replay_testing'
    results = c.execute('SELECT first_user, second_user, request_method, request_url FROM ' + table).fetchall()

    if results:
        logging.info('Vulnerable URLs identified:')
        for result in results:
            logging.info(f'({result[0]}, {result[1]}): {result[2]} {result[3]}')

    if not results:  # and not results_parameter_testing:
        logging.info('No vulnerabilities found')


def save_execution_time(step, time, db_path):
    conn = sqlite3.connect(db_path + 'responses.db')
    c = conn.cursor()
    c.execute('INSERT INTO execution_time VALUES (NULL, ?, ?)', (step, time))
    conn.commit()
    conn.close()


def create_user_combos(config_file_parameters):
    user_combos = []
    if config_file_parameters['combinations']['type'] == 'selected':
        selected_user_pairs = config_file_parameters['combinations']['user_pairs']
        for selected_user_pair in selected_user_pairs:
            user_combos.append(tuple(selected_user_pair.split()))
    else:
        usernames = []
        users = config_file_parameters['users']
        for user_info in users:
            for key in user_info:
                usernames.append(key)
        user_combos = list(itertools.permutations(usernames, 2))  # We sacrifice the memory effiency of the iterator here for easier appending, because we probably won't have huge user lists
        for username in usernames:
            user_combos.append((username, 'public'))
    return user_combos


def main():
    # Root logger writes all log levels (DEBUG and higher) to log file
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', filename='testing.log', filemode='w')
    logging.getLogger().setLevel(logging.DEBUG)

    # Console log handler writes INFO messages or higher to sys.stderr (visible in console)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # Add the handler to the root logger
    logging.getLogger().addHandler(console)

    args = parser.parse_args()
    configfile = args.config
    run_mode = args.run_mode
    full_mode = args.full_mode
    deduplication_mode = args.deduplication_mode
    matching_mode = args.matching_mode
    matching_debug = args.matching_debug
    db_log_level = args.db_log_level
    duplicate_check = args.duplicate_check
    iteration_depth = args.iteration_depth
    config_file_parameters = parse_config_file(configfile)

    if 'c' in run_mode:
        # rename database and create a new one if exist
        if os.path.isfile(config_file_parameters['path_to_db'] + 'responses.db'):
            logging.info("Reset SQLITE Database")
            subprocess.call('./reset_db.sh')

        # Create database for execution time measurement
        conn = sqlite3.connect(config_file_parameters['path_to_db'] + 'responses.db')
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS execution_time (id integer PRIMARY KEY, step text, time real)')
        conn.commit()
        conn.close()
        vacuum_db(config_file_parameters['path_to_db'] + 'responses.db')

    elif 'f' in run_mode:
        # remove filtering tables that will be recreated during the run
        conn = sqlite3.connect(config_file_parameters['path_to_db'] + 'responses.db')
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS crawling_results_after_deduplication_filter')
        c.execute('DROP TABLE IF EXISTS crawling_results_after_public_content_filter')
        c.execute('DROP TABLE IF EXISTS crawling_results_after_other_user_content_filter')
        c.execute('DROP TABLE IF EXISTS crawling_results_after_query_filter')
        c.execute('DROP TABLE IF EXISTS crawling_results_after_standard_pages_filter')
        c.execute('DROP TABLE IF EXISTS crawling_results_after_static_content_filter')
        c.execute('DROP TABLE IF EXISTS replay_testing_results')
        c.execute('DROP TABLE IF EXISTS vulnerabilities_after_replay_testing')
        c.execute('DROP TABLE IF EXISTS vulnerabilities_after_findings_verifier')
        c.execute('DROP TABLE IF EXISTS matching_results')
        conn.commit()
        conn.close()
        vacuum_db(config_file_parameters['path_to_db'] + 'responses.db')
    elif 'r' in run_mode:
        # remove replay testing tables that will be recreated during the run
        conn = sqlite3.connect(config_file_parameters['path_to_db'] + 'responses.db')
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS replay_testing_results')
        c.execute('DROP TABLE IF EXISTS vulnerabilities_after_replay_testing')
        c.execute('DROP TABLE IF EXISTS vulnerabilities_after_findings_verifier')
        c.execute("DELETE FROM matching_results WHERE class = 'ContentSimilarityValidator'")
        conn.commit()
        conn.close()
        filtered_table_name = 'crawling_results_after_other_user_content_filter'
        vacuum_db(config_file_parameters['path_to_db'] + 'responses.db')
    elif 'v' in run_mode:
        # remove replay testing tables that will be recreated during the run
        conn = sqlite3.connect(config_file_parameters['path_to_db'] + 'responses.db')
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS vulnerabilities_after_findings_verifier')
        c.execute("DELETE FROM matching_results WHERE class = 'FindingsVerifier'")
        conn.commit()
        conn.close()
        filtered_table_name = 'crawling_results_after_other_user_content_filter'
        vacuum_db(config_file_parameters['path_to_db'] + 'responses.db')

    # Crawling the application with all configured users
    if 'c' in run_mode:
        start_crawling = time.time()

        logging.info('Starting crawling')
        # We first crawl with the public user
        crawling(
            target_url=config_file_parameters['target_url'],
            target_domain=config_file_parameters['target_domain'],
            username='public',
            password=get_credentials_config(configfile, 'public'),
            db_path=config_file_parameters['path_to_db'],
            blocked_word_list=config_file_parameters['do_not_call_pages'],
            static_content_extensions=config_file_parameters['static_content_extensions'],
            ignore_tokens=config_file_parameters['ignore_tokens'],
            reset_script=config_file_parameters['reset_script'],
            auth_script=config_file_parameters['auth_script'],
            payloadfile=config_file_parameters['payloadfile'],
            configfile=configfile,
            full_mode=full_mode,
            duplicate_check=duplicate_check,
            iteration_depth=iteration_depth
        )

        # Now we start a crawling run for each configured user
        users = config_file_parameters['users']
        for user_info in users:
            for key in user_info:
                username = key

            crawling(
                target_url=config_file_parameters['target_url'],
                target_domain=config_file_parameters['target_domain'],
                username=username,
                password=get_credentials_config(configfile, username),
                db_path=config_file_parameters['path_to_db'],
                blocked_word_list=config_file_parameters['do_not_call_pages'],
                static_content_extensions=config_file_parameters['static_content_extensions'],
                ignore_tokens=config_file_parameters['ignore_tokens'],
                reset_script=config_file_parameters['reset_script'],
                auth_script=config_file_parameters['auth_script'],
                payloadfile=config_file_parameters['payloadfile'],
                configfile=configfile,
                full_mode=full_mode,
                duplicate_check=duplicate_check,
                iteration_depth=iteration_depth

            )

        logging.info('Finished crawling')
        end_crawling = time.time()
        save_execution_time('crawling', end_crawling - start_crawling, config_file_parameters['path_to_db'])

    # Filtering the raw crawler data creating filtered tables for all users
    if 'f' in run_mode:
        start_filtering = time.time()
        logging.info('Starting generic filtering')

        current_table_name = generic_filtering(
            db_path=config_file_parameters['path_to_db'],
            deduplication_mode=deduplication_mode,
            standard_pages=config_file_parameters['standard_pages'],
            static_content_extensions=config_file_parameters['static_content_extensions'],
            ignore_tokens=config_file_parameters['ignore_tokens'],
            db_log_level=db_log_level
        )

        logging.info('Finished generic filtering')

        user_combos = create_user_combos(config_file_parameters)

        logging.info('Starting user-dependent filtering')

        # Run filtering for each combination
        for user_combo in user_combos:
            logging.info(f'Starting filtering for user combination {user_combo[0]} - {user_combo[1]}')
            filtered_table_name = user_dependent_filtering(
                db_path=config_file_parameters['path_to_db'],
                current_table_name=current_table_name,
                username_user_1=user_combo[0],
                username_user_2=user_combo[1],
                deduplication_mode=deduplication_mode,
                ignore_tokens=config_file_parameters['ignore_tokens'],
            )

            logging.info(f'Finished filtering for user combination {user_combo[0]} - {user_combo[1]}')
        vacuum_db(config_file_parameters['path_to_db'] + 'responses.db')  # Always clear temp tables after filtering
        if db_log_level == 'prod':
            delete_table(config_file_parameters['path_to_db'] + 'responses.db', 'crawling_results_after_standard_pages_filter')
        logging.info('Finished user-dependent filtering')
        end_filtering = time.time()
        save_execution_time('filtering', end_filtering - start_filtering, config_file_parameters['path_to_db'])

    # Testing for access control vulnerabilities
    if 'r' in run_mode:
        start_replay_testing = time.time()
        logging.info('Starting replaying')

        user_combos = create_user_combos(config_file_parameters)

        for user_combo in user_combos:
            if full_mode == 'on':
                reset_application(config_file_parameters['reset_script'])
                credentials = config_file_parameters['credentials']
                cred1 = next((cred for cred in credentials if user_combo[0] in cred), None)
                cred2 = next((cred for cred in credentials if user_combo[1] in cred), None)
                pass1 = ''
                pass2 = ''
                if cred1 is not None:
                    pass1 = cred1[user_combo[0]]
                if cred2 is not None:
                    pass2 = cred2[user_combo[1]]
            authenticate_application(config_file_parameters['auth_script'], user_combo[0], pass1, user_combo[1], pass2, configfile)
            logging.info(f'Starting replaying using user combination {user_combo[0]} - {user_combo[1]}')
            replay_tester = ReplayTester(
                username_user_1=user_combo[0],
                auth_user_1=get_auth_config(configfile, user_combo[0]),
                username_user_2=user_combo[1],
                auth_user_2=get_auth_config(configfile, user_combo[1]),
                source_table=filtered_table_name,
                db_path=config_file_parameters['path_to_db'],
                inter_threshold=config_file_parameters['inter_threshold_validating'],
                csrf_fieldname=config_file_parameters['csrf_fieldname'],
                csrf_headername=config_file_parameters['csrf_headername'],
                csrf_tokenvalue=get_csrf_value(configfile, user_combo[1]),
                matching_mode=matching_mode,
                matching_debug=matching_debug,
                full_mode=full_mode,
                db_log_level=db_log_level,
                stripping_tags=config_file_parameters['html_stripping_tags'],
                regex_to_match=config_file_parameters['regex_to_match'],
            )
            replay_tester.run_tests()
            logging.info(f'Finished replaying using user combination {user_combo[0]} - {user_combo[1]}')
        if db_log_level == 'prod':
            delete_table(config_file_parameters['path_to_db'] + 'responses.db', filtered_table_name)
        logging.info('Finished replaying')
        end_replay_testing = time.time()
        save_execution_time('replay_testing', end_replay_testing - start_replay_testing, config_file_parameters['path_to_db'])

    # Verify the findings
    if 'v' in run_mode:
        start_findings_verifier = time.time()
        logging.info('Starting findings verifier')
        user_combos = create_user_combos(config_file_parameters)
        for user_combo in user_combos:
            logging.info(f'Starting findings verifier for user combination {user_combo[0]} - {user_combo[1]}')
            findings_verifier = FindingsVerifier(
                username_user_1=user_combo[0],
                username_user_2=user_combo[1],
                db_path=config_file_parameters['path_to_db'],
                inter_threshold=config_file_parameters['inter_threshold_validating'],
                matching_mode=matching_mode,
                matching_debug=matching_debug,
                db_log_level=db_log_level,
                stripping_tags=config_file_parameters['html_stripping_tags']
            )
            findings_verifier.check_findings()
            logging.info(f'Finished findings verifier for user combination {user_combo[0]} - {user_combo[1]}')
        logging.info('Finished findings verifier')
        end_findings_verifier = time.time()
        save_execution_time('findings_verifier', end_findings_verifier - start_findings_verifier, config_file_parameters['path_to_db'])
        if db_log_level == 'prod':
            db_path = config_file_parameters['path_to_db'] + 'responses.db'
            delete_table(db_path, 'crawling_results')
            delete_table(db_path, 'execution_time')
            delete_table(db_path, 'replay_testing_results')
            if 'v' in run_mode:
                delete_table(db_path, 'vulnerabilities_after_replay_testing')

    if 'v' in run_mode:
        print_results(config_file_parameters['path_to_db'], True)
    else:
        print_results(config_file_parameters['path_to_db'], False)


def vacuum_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('VACUUM')
    conn.commit()
    conn.close()


if __name__ == '__main__':
    main()
