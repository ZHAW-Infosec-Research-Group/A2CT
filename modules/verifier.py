"""
Base class for Verifier classes

Classes:
Tester
"""


import sqlite3


class Verifier:
    def __init__(self, username_user_1, username_user_2, db_path, inter_threshold, db_name='responses.db'):
        self.username_user_1 = username_user_1
        self.username_user_2 = username_user_2
        self.conn = sqlite3.connect(db_path + db_name)
        self.cursor = self.conn.cursor()
        self.inter_threshold = inter_threshold
