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

    def dump(self, instance):
        value = getattr(instance, self.name)
        return self._as_dict(value)

    def load(self, instance, value):
        new_value = self._from_dict(value)
        instance._values[self.name] = new_value

    def set(self, instance, kwargs):
        value = kwargs.get(self.name, self.default_value)
        self.__set__(instance, value)

    def is_valid(self, instance):
        return True

    def is_set(self, instance):
        return instance._values.get(self.name) != self.default_value

    def __get__(self, instance, obj_type=None):
        value = instance._values.get(self.name, self.default_value)
        return value

    def __set__(self, instance, new_value):
        current_value = instance._values.get(self.name)
        if new_value == current_value:
            return
        if new_value is not None:
            try:
                current_value.update(new_value)
                return
            except AttributeError:
                pass
        instance._values[self.name] = new_value

    def __delete__(self, instance):
        del instance._values[self.name]

    @property
    def default_value(self):
        from .base import Model
        if issubclass(self.type, Model) and self._default_value is None:
            return self.type(new=False)
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
                self._default_value,
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

    def dump(self, instance):
        return [self._as_dict(v) for v in getattr(instance, self.name)]

    def load(self, instance, value):
        if value is None:
            value = self.default_value
        instance._values[self.name] = [self._from_dict(v) for v in value]


class RequiredField(Field):
    """Required field must have a value from the start"""

    def is_valid(self, instance):
        value = self.__get__(instance)
        return value is not None and super(RequiredField, self).is_valid(instance)
