#!/usr/bin/env python
# -*- coding: utf-8

import os
import vcr


def get_vcr(filepath):
    return vcr.VCR(
        path_transformer=vcr.VCR.ensure_suffix('.yaml'),
        match_on=("method", "scheme", "host", "port", "path", "query", "body"),
        cassette_library_dir=os.path.splitext(filepath)[0]
    )


def assert_any_call_with_useful_error_message(mockk, uri, *args):
    """
    If an AssertionError is raised in the assert, find any other calls on mock where the first parameter is uri and
    append those calls to the AssertionErrors message to more easily find the cause of the test failure.
    """

    def format_call(call):
        if len(call) > 1:
            return 'call({}, {})'.format(call[0], call[1])
        else:
            return 'call({})'.format(call[0])

    try:
        mockk.assert_any_call(uri, *args)
    except AssertionError as ae:
        other_calls = [call[0] for call in mockk.call_args_list if call[0][0] == uri]
        if other_calls:
            extra_info = '\n\nURI {} got the following other calls:\n{}'.format(uri, '\n'.join(
                format_call(call) for call in other_calls))
            raise AssertionError(ae.message + extra_info)
        else:
            raise
