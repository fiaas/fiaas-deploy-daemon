#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from collections import namedtuple

import six

from .client import Client, NotFound
from .fields import Field

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class MetaModel(type):
    """Metaclass for Model

    Responsibilities:
    Creating the _meta attribute, with url_template (if present), list of fields
        and for convenience, a list of field names.
    Creates properties for name and namespace if the instance has a metadata field.
    Mixes in ApiMixIn if the Model has a Meta attribute, indicating a top level
        Model (not to be confused with _meta).
    """
    @staticmethod
    def __new__(mcs, cls, bases, attrs):
        attr_meta = attrs.pop("Meta", None)
        if attr_meta:
            bases += (ApiMixIn,)
        meta = {
            "url_template": getattr(attr_meta, "url_template", ""),
            "fields": [],
            "field_names": []
        }
        field_names = meta["field_names"]
        fields = meta["fields"]
        for k, v in list(attrs.items()):
            if isinstance(v, Field):
                v.name = k
                field_names.append(k)
                fields.append(v)
        Meta = namedtuple("Meta", meta.keys())
        attrs["_meta"] = Meta(**meta)
        if "metadata" in field_names:
            if "name" not in field_names:
                attrs["name"] = property(lambda self: self.metadata.name)
            if "namespace" not in field_names:
                attrs["namespace"] = property(lambda self: self.metadata.namespace)
        return super(MetaModel, mcs).__new__(mcs, cls, bases, attrs)


class ApiMixIn(object):
    """ApiMixIn class for top level Models

    Contains methods for working with the API
    """
    _client = Client()

    @classmethod
    def _build_url(cls, **kwargs):
        return cls._meta.url_template.format(**kwargs)

    @classmethod
    def find(cls, name, namespace="default"):
        url = cls._build_url(name="", namespace=namespace)
        resp = cls._client.get(url, params={"labelSelector": "app={}".format(name)})
        return [cls.from_dict(item) for item in resp.json()[u"items"]]

    @classmethod
    def get(cls, name, namespace="default"):
        """Get from API server if it exists"""
        url = cls._build_url(name=name, namespace=namespace)
        resp = cls._client.get(url)
        instance = cls.from_dict(resp.json(), name)
        return instance

    @classmethod
    def get_or_create(cls, **kwargs):
        """If exists, get from API, else create new instance"""
        try:
            name = kwargs.get("name")
            if "namespace" in kwargs:
                namespace = kwargs.get("namespace")
            elif "metadata" in kwargs:
                namespace = kwargs.get("metadata").namespace
            else:
                namespace = "default"
            instance = cls.get(name, namespace)
            for field in cls._meta.fields:
                field.set(instance, kwargs)
            return instance
        except NotFound:
            return cls(new=True, **kwargs)

    @classmethod
    def delete(cls, name, namespace="default"):
        url = cls._build_url(name=name, namespace=namespace)
        cls._client.delete(url)

    def save(self):
        """Save to API server, either update if existing, or create if new"""
        if self._new:
            url = self._build_url(name="", namespace=self.namespace)
            self._client.post(url, self.as_dict())
        else:
            url = self._build_url(name=self.name, namespace=self.namespace)
            self._client.put(url, self.as_dict())


class Model(six.with_metaclass(MetaModel)):
    """A kubernetes Model object

    Contains fields for each attribute in the API specification, and methods for export/import.
    """
    def __init__(self, new=True, **kwargs):
        self._new = new
        self._values = {}
        kwarg_names = set(kwargs.keys())
        for field in self._meta.fields:
            kwarg_names.discard(field.name)
            field.set(self, kwargs)
        if "metadata" in self._meta.field_names and "name" in kwargs:
            self.metadata.name = kwargs.get("name")
            kwarg_names.discard("name")
        if kwarg_names:
            raise TypeError("{}() got unexpected keyword-arguments: {}".format(self.__class__.__name__, ", ".join(kwarg_names)))

    def as_dict(self):
        if all(getattr(self, field.name) == field.default_value for field in self._meta.fields):
            return None
        d = {}
        for field in self._meta.fields:
            value = field.dump(self)
            if value is not None:
                d[field.name] = value
        return d

    @classmethod
    def from_dict(cls, d, name=None):
        if name:
            instance = cls(new=False, name=name)
        else:
            instance = cls(new=False)
        for field in cls._meta.fields:
            field.load(instance, d.get(field.name))
        return instance

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,
                               ", ".join("{}={}".format(key, getattr(self, key)) for key in self._meta.field_names))

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()
