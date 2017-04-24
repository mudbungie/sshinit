#!/usr/bin/env python3

import unittest
import sshinit

def handle_args_fail_without_args():
    try:
        handle_args([]):
        return False
    except sshinit.InputError:
        return True

