#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from ..base import Model
from ..fields import Field, ReadOnlyField


class ObjectMeta(Model):
    name = Field(six.text_type)
    namespace = Field(six.text_type, "default")
    resourceVersion = ReadOnlyField(six.text_type)
    labels = Field(dict)
    annotations = Field(dict)
