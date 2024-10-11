#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Script to programatically edit YAML files.

**Needs ruamel.yaml, which is not normally part of our dependencies**

Add new editors as needed, to extend the toolkit as we go along.
"""

import argparse
import os

from ruamel.yaml import YAML


class Editor(object):
    @classmethod
    def get_editor(cls, name):
        for subclass in cls.__subclasses__():
            if subclass.__name__.lower() == name.lower():
                return subclass()

    @classmethod
    def editors(cls):
        return [subclass.__name__.lower() for subclass in cls.__subclasses__()]

    def accepts(self, filepath):
        return True

    def edit(self, data):
        raise NotImplementedError()


class SortEnvVariables(Editor):
    def accept(self, filepath):
        return "deployment" in filepath

    def edit(self, data):
        containers = data["spec"]["template"]["spec"]["containers"]
        container = containers[0]
        env_variables = container.get("env", [])
        env_variables.sort(key=lambda x: x["name"])
        container["env"] = env_variables
        return data


class RemoveEmptyEnvVariables(Editor):
    def accepts(self, filepath):
        return "deployment" in filepath

    def edit(self, data):
        containers = data["spec"]["template"]["spec"]["containers"]
        container = containers[0]
        env_variables = [x for x in container.get("env", []) if x.get("value") or x.get("valueFrom")]
        container["env"] = env_variables
        return data


class AddFinalizers(Editor):
    def accepts(self, filepath):
        return "expected" in filepath

    def edit(self, data):
        if data["kind"] == "Deployment":
            self._add_finalizers(data["spec"]["template"]["metadata"])
        self._add_finalizers(data["metadata"])
        return data

    def _add_finalizers(self, metadata):
        metadata["finalizers"] = []


def process_file(editor, filepath):
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(filepath) as fobj:
        data = yaml.safe_load(fobj)
    try:
        data = editor.edit(data)
    except KeyError:
        return
    with open(filepath, "w") as fobj:
        yaml.dump(data, fobj)


def process_files(editor):
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")):
        for filename in files:
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                if "invalid" in filename:
                    continue
                filepath = os.path.join(root, filename)
                if editor.accepts(filepath):
                    process_file(editor, filepath)


def main(editors):
    for name in editors:
        editor = Editor.get_editor(name)
        process_files(editor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("editor", nargs="+", help="Name of an editor to apply", choices=Editor.editors())
    options = parser.parse_args()
    main(options.editor)
