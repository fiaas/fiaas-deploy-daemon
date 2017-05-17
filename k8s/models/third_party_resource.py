#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from .common import ObjectMeta
from ..base import Model
from ..fields import Field, ListField


class Version(Model):
    name = Field(six.text_type)
    value = Field(six.text_type)


class ThirdPartyResource(Model):
    class Meta:
        url_template = "/apis/extensions/v1beta1/thirdpartyresources/{name}"

    metadata = Field(ObjectMeta)
    description = Field(six.text_type)
    versions = ListField(Version)
