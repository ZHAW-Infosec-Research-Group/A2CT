"""
Tests for findings_verifier.py.
"""


import os
import shutil
import uuid
import sqlite3
from modules import config
from modules.findings_verifier import FindingsVerifier

test_db_name = 'responses_findings_verifier_test'  # test db in tests/ folder based on marketplace crawling results
test_db_temp_name = test_db_name + '_' + str(uuid.uuid4())[:6] + '.db'

test_db_path = config.database_settings['db_path_for_testing']  # directory where test db will be copied to temporarily
test_db_full_path = test_db_path + test_db_temp_name  # full path with file name

test_dir_path = os.path.dirname(os.path.abspath(__file__))


def setup_function():
    shutil.copyfile(test_dir_path + config.test_settings['resources_path'] + test_db_name + '.db', test_db_full_path)


def teardown_function():
    os.remove(test_db_full_path)


def test_findings_verifier():
    findings_verifier = FindingsVerifier(
        username_user_1="donald",
        username_user_2="alice",
        db_path=test_db_path,
        inter_threshold=80,
        matching_mode="m4i",
        matching_debug="off",
        db_name=test_db_temp_name,
        db_log_level="dev",
        stripping_tags=[],
    )
    findings_verifier.check_findings()

    # Verify if all 5 marketplace findings for donald are found
    conn = sqlite3.connect(test_db_full_path)
    cursor = conn.cursor()
    vulnerabilities_after_findings_verifier = cursor.execute('SELECT * from vulnerabilities_after_findings_verifier').fetchall()
    conn.close()

    assert len(vulnerabilities_after_findings_verifier) == 3

    assert vulnerabilities_after_findings_verifier[0][1] == 'donald'
    assert vulnerabilities_after_findings_verifier[0][2] == 'alice'
    assert vulnerabilities_after_findings_verifier[0][3] == 'https://172.17.0.1:3443/admin_product_add'
    assert vulnerabilities_after_findings_verifier[0][6] == b''

    assert vulnerabilities_after_findings_verifier[1][1] == 'donald'
    assert vulnerabilities_after_findings_verifier[1][2] == 'alice'
    assert vulnerabilities_after_findings_verifier[1][3] == 'https://172.17.0.1:3443/admin_product_delete'
    assert vulnerabilities_after_findings_verifier[1][6] == b'productId=4'

    assert vulnerabilities_after_findings_verifier[2][1] == 'donald'
    assert vulnerabilities_after_findings_verifier[2][2] == 'alice'
    assert vulnerabilities_after_findings_verifier[2][3] == 'https://172.17.0.1:3443/admin_product_add'
    assert vulnerabilities_after_findings_verifier[2][6] == b'code=1234&description=testproduct&price=55'
