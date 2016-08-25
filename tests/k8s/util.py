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
