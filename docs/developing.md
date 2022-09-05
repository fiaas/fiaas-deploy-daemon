# Developer Documentation

## Creating a Release

fiaas-deploy-daemon is released by pushing an [annotated git tag](https://git-scm.com/book/en/v2/Git-Basics-Tagging#_annotated_tags) (a tag containing a message) named `v$SEMVER_VERSION`:

```shell
git tag -a vMAJOR.MINOR.PATCH [git ref]
```
The version number must follow [semantic versioning](semver2). git ref must be a commit on the master branch.

The message of the annotated tag should contain the release notes, describing the changes included in the release. A header will be added automatically by the release tooling, so you don't need to include one in the release notes. These release notes end up on the resulting release in Github.

(Regular non-annotated git tags should also create a release, but in that case the tagged commit's message will be used as the release notes, which might not be particularly descriptive.)

When you're done writing release notes and the tag is created locally, push it to trigger the CI tag build, which creates a release in github:

```shell
git push origin vMAJOR.MINOR.PATCH
```

### Versioning
- If a backwards incompatible change is introduced or a feature is removed, increase the major version.
- If a new feature is added, but backwards compatibility is preserved, increase the minor version.
- For bug fixes and similar, increase the patch version.

For cases that do not fit into the above, refer to the [semver spec](semver2) (and consider updating this documentation).

[semver2]: https://semver.org/spec/v2.0.0.html
