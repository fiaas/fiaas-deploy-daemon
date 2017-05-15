#!/usr/bin/env python
# -*- coding: utf-8 -*-

from k8s.base import Model, Field, WatchEvent


class Example(Model):
    class Meta:
        url_template = '/example'
        watch_list_url = '/watch/example'

    value = Field(int)


class TestWatchEvent(object):
    def test_watch_event_added(self):
        watch_event = WatchEvent({"type": "ADDED", "object": {"value": 42}}, Example)
        assert watch_event.type == WatchEvent.ADDED
        assert watch_event.object == Example(value=42)

    def test_watch_event_modified(self):
        watch_event = WatchEvent({"type": "MODIFIED", "object": {"value": 42}}, Example)
        assert watch_event.type == WatchEvent.MODIFIED
        assert watch_event.object == Example(value=42)

    def test_watch_event_deleted(self):
        watch_event = WatchEvent({"type": "DELETED", "object": {"value": 42}}, Example)
        assert watch_event.type == WatchEvent.DELETED
        assert watch_event.object == Example(value=42)
