#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import json
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
            "watch_list_url": getattr(attr_meta, "watch_list_url", ""),
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
    def list(cls, namespace="default"):
        url = cls._build_url(name="", namespace=namespace)
        resp = cls._client.get(url)
        return [cls.from_dict(item) for item in resp.json()[u"items"]]

    @classmethod
    def watch_list(cls):
        """Return a generator that yields WatchEvents of cls"""
        url = cls._meta.watch_list_url
        if not url:
            raise NotImplementedError("Cannot watch_list, no watch_list_url defined on class {}".format(cls))
        resp = cls._client.get(url, stream=True, timeout=None)
        for line in resp.iter_lines(chunk_size=None):
            if line:
                try:
                    event_json = json.loads(line)
                    event = WatchEvent(event_json, cls)
                    yield event
                except ValueError:
                    LOG.exception("Unable to parse JSON on watch event, discarding event. Line: %r", line)

    @classmethod
    def get(cls, name, namespace="default"):
        """Get from API server if it exists"""
        url = cls._build_url(name=name, namespace=namespace)
        resp = cls._client.get(url)
        instance = cls.from_dict(resp.json())
        return instance

    @classmethod
    def get_or_create(cls, **kwargs):
        """If exists, get from API, else create new instance"""
        try:
            metadata = kwargs.get("metadata")
            instance = cls.get(metadata.name, metadata.namespace)
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
            url = self._build_url(name="", namespace=self.metadata.namespace)
            self._client.post(url, self.as_dict())
        else:
            url = self._build_url(name=self.metadata.name, namespace=self.metadata.namespace)
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
        if kwarg_names:
            raise TypeError("{}() got unexpected keyword-arguments: {}".format(self.__class__.__name__, ", ".join(kwarg_names)))
        if self._new:
            self._validate_fields()

    def _validate_fields(self):
        for field in self._meta.fields:
            if not field.is_valid(self):
                raise TypeError("Value of field {} is not valid on {}".format(field.name, self))

    def as_dict(self):
        if all(getattr(self, field.name) == field.default_value for field in self._meta.fields):
            return None
        d = {}
        for field in self._meta.fields:
            value = field.dump(self)
            if value is not None:
                d[_api_name(field.name)] = value
        return d

    def update(self, other):
        for field in self._meta.fields:
            setattr(self, field.name, getattr(other, field.name))

    @classmethod
    def from_dict(cls, d):
        instance = cls(new=False)
        for field in cls._meta.fields:
            field.load(instance, d.get(_api_name(field.name)))
        instance._validate_fields()
        return instance

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,
                               ", ".join("{}={}".format(key, getattr(self, key)) for key in self._meta.field_names))

    def __eq__(self, other):
        try:
            return self.as_dict() == other.as_dict()
        except AttributeError:
            return False


def _api_name(name):
    return name[1:] if name.startswith("_") else name


class WatchEvent(object):

    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"

    def __init__(self, event_json, cls):
        self.type = event_json["type"]
        self.object = cls.from_dict(event_json["object"])

    def __repr__(self):
        return "{cls}(type={type}, object={object})".format(cls=self.__class__.__name__, type=self.type,
                                                            object=self.object)
