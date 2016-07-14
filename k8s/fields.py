#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import


class Field(object):
    """Generic field on a k8s model"""
    def __init__(self, type, default_value=None, alt_type=None):
        self.type = type
        self.alt_type = alt_type
        self.name = "__unset__"
        self._default_value = default_value

    def dump(self, inst):
        value = getattr(inst, self.name, self.default_value)
        return self._as_dict(value)

    def load(self, instance, value):
        new_value = self._from_dict(value)
        instance._values[self.name] = new_value

    def set(self, instance, kwargs):
        value = kwargs.get(self.name, self.default_value)
        self.__set__(instance, value)

    def __get__(self, instance, obj_type=None):
        return instance._values.get(self.name, self.default_value)

    def __set__(self, instance, value):
        try:
            other = value
            child = instance._values.get(self.name, self.default_value)
            try:
                if other is None:
                    child = None
                else:
                    child.update(other)
            except AttributeError:
                for field in value._meta.fields:
                    setattr(child, field.name, getattr(other, field.name, field.default_value))
            instance._values[self.name] = child
        except (AttributeError, NameError):
            instance._values[self.name] = value

    def __delete__(self, instance):
        del instance._values[self.name]

    @property
    def default_value(self):
        from .base import Model
        if issubclass(self.type, Model) and self._default_value is None:
            return self.type()
        return self._default_value

    @staticmethod
    def _as_dict(value):
        try:
            return value.as_dict()
        except AttributeError:
            """ If we encounter a dict with all None-elements, we return None.
                This is because the Kubernetes-API does not support empty string values, or "null" in json.
            """
            if isinstance(value, dict):
                d = {k: v for k, v in value.items() if v is not None}
                return d if d else None
            else:
                return value

    def _from_dict(self, value):
        if value is None:
            return self.default_value
        try:
            return self.type.from_dict(value)
        except AttributeError:
            if isinstance(value, self.type) or (self.alt_type and isinstance(value, self.alt_type)):
                return value
            return self.type(value)

    def __repr__(self):
        return "{}(name={}, type={}, default_value={}, alt_type={})".format(
                self.__class__.__name__,
                self.name,
                self.type,
                self.default_value,
                self.alt_type
        )


class ReadOnlyField(Field):
    """ReadOnlyField can only be set by the API-server"""
    def __set__(self, instance, value):
        pass


class OnceField(Field):
    """OnceField can only be set on new instances, and is immutable after creation on the server"""
    def __set__(self, instance, value):
        if instance._new:
            super(OnceField, self).__set__(instance, value)


class ListField(Field):
    """ListField is a list (array) of a single type on a model"""
    def __init__(self, type, default_value=None):
        if default_value is None:
            default_value = []
        super(ListField, self).__init__(type, default_value)

    def dump(self, inst):
        return [self._as_dict(v) for v in getattr(inst, self.name, self.default_value)]

    def load(self, instance, value):
        if value is None:
            value = self.default_value
        instance._values[self.name] = [self._from_dict(v) for v in value]
