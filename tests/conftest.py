#!/usr/bin/env python
# -*- coding: utf-8
import itertools

import pytest

pytest_plugins = ['helpers_namespace']


@pytest.helpers.register
def assert_any_call(mockk, first, *args):
    __tracebackhide__ = True

    def _assertion():
        mockk.assert_any_call(first, *args)

    _add_useful_error_message(_assertion, mockk, first, args)


@pytest.helpers.register
def assert_no_calls(mockk, uri=None):
    __tracebackhide__ = True

    def _assertion():
        calls = [call[0] for call in mockk.call_args_list if (uri is None or call[0][0] == uri)]
        assert len(calls) == 0

    _add_useful_error_message(_assertion, mockk, None, None)


@pytest.helpers.register
def assert_dicts(actual, expected):
    __tracebackhide__ = True

    try:
        assert actual == expected
    except AssertionError as ae:
        raise AssertionError(ae.message + _add_argument_diff(actual, expected))


def _add_useful_error_message(assertion, mockk, first, args):
    """
    If an AssertionError is raised in the assert, find any other calls on mock where the first parameter is uri and
    append those calls to the AssertionErrors message to more easily find the cause of the test failure.
    """
    __tracebackhide__ = True
    try:
        assertion()
    except AssertionError as ae:
        other_calls = [call[0] for call in mockk.call_args_list if (first is None or call[0][0] == first)]
        if other_calls:
            extra_info = '\n\nURI {} got the following other calls:\n{}\n'.format(first, '\n'.join(
                _format_call(call) for call in other_calls))
            if len(other_calls) == 1 and len(other_calls[0]) == 2 and args is not None:
                extra_info += _add_argument_diff(other_calls[0][1], args[0])
            raise AssertionError(ae.message + extra_info)
        else:
            raise


def _add_argument_diff(actual, expected, indent=0, acc=None):
    first = False
    if not acc:
        acc = []
        first = True
    if type(actual) != type(expected):
        acc.append("{}{!r} {} {!r}".format(" " * indent * 2, actual, "==" if actual == expected else "!=", expected))
    elif isinstance(actual, dict):
        for k in set(actual.keys() + expected.keys()):
            acc.append("{}{}:".format(" " * indent * 2, k))
            a = actual.get(k)
            e = expected.get(k)
            if a != e:
                _add_argument_diff(a, e, indent + 1, acc)
    elif isinstance(actual, list):
        for a, e in itertools.izip_longest(actual, expected):
            acc.append("{}-".format(" " * indent * 2))
            if a != e:
                _add_argument_diff(a, e, indent + 1, acc)
    else:
        acc.append("{}{!r} {} {!r}".format(" " * indent * 2, actual, "==" if actual == expected else "!=", expected))
    if first:
        return "\n".join(acc)


def _format_call(call):
    if len(call) > 1:
        return 'call({}, {})'.format(call[0], call[1])
    else:
        return 'call({})'.format(call[0])
