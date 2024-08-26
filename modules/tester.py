"""
Base class for Tester classes

Classes:
Tester
"""


import sqlite3


class Tester:
    def __init__(self, username_user_1, auth_user_1, username_user_2, auth_user_2, source_table, db_path, inter_threshold,
                 full_mode, regex_to_match='', db_name='responses.db'):
        self.username_user_1 = username_user_1
        self.auth_user_1 = auth_user_1
        self.username_user_2 = username_user_2
        self.auth_user_2 = auth_user_2
        self.source_table = source_table
        self.conn = sqlite3.connect(db_path + db_name)
        self.cursor = self.conn.cursor()
        self.full_mode = full_mode
        self.regex_to_match = regex_to_match
        self.inter_threshold = inter_threshold
