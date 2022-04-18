# -*- coding: utf-8 -*-
"""Utility functions for the RushFiles add-on.
"""

import os

def get_os():
    uname = os.uname()
    return '{}:{}'.format(uname[0], uname[2])
