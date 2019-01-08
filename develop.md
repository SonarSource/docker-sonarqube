Develop
=======

Helpful notes for developers of the images.

Releasing a new version of an image
-----------------------------------

Create the new image for the new version:

1. Rename the last version's directory, for example `7.4-community` to `7.5-community`
2. Update the version in `Dockerfile`, and make any other necessary changes (usually none)
3. Update the version in `.travis.yml'
4. Run tests, for example: `./run-tests.sh 7.5-community`
5. Create a Pull Request, confirm Travis build passes, get it reviewed and merged

Update the public repositories for [Docker Hub][hub]:

1. Only if necessary, update files in https://github.com/docker-library/docs/tree/master/sonarqube and create a Pull Request
    1. The markdown format must follow a certain standard, otherwise automated tests will fail. You can test with the `markdownfmt.sh` tool included in the repository, for example `./markdownfmt.sh -d sonarqube/content.md` will output the diff that would have to be done to make the tests pass. You can use the `patch` command to apply the changes, for example: `./markdownfmt.sh -d sonarqube/content.md | patch sonarqube/content.md`
    2. Verify the Pull Request passes the automated tests (visible in the status of the PR)

2. Update https://github.com/docker-library/official-images/blob/master/library/sonarqube
    1. Update the `Tags` and `Directory` entries appropriately
    2. Update the commit sha to the just merged commit in `docker-sonarqube`
    3. Create a Pull Request, with a simple summary of the new release
    4. Verify the Pull Request passes the automated tests (visible in the status of the PR)

3. Wait for the Pull Requests to get merged, and verify the updated page on [Docker Hub][hub]

FAQ
---

Q: Why don't you provide Alpine-based images?

A: As of today, OpenJDK 8 does not officially support Alpine. As such, we don't know a good base image to build on. We did try the unsupported `openjdk:8-alpine` image as base, and we saw seen nonsense problems with nonsense workarounds. We've left the recipes for Alpine-based images in the branch named `alpine`, build and use at your own risk.

Other notes
-----------

To control the generated content of the Docker Hub page, look around in the files in `.template-helpers` of the [`docs` repository][docs]. For example, the "Where to get help" section is customized by a copy of `.template-helpers/get-help.md` in `sonarqube/get-help.md`.

For more details on the release process, see the documentation in these repositories:

- https://github.com/docker-library/docs
- https://github.com/docker-library/official-images

[hub]: https://hub.docker.com/_/sonarqube/
[docs]: https://github.com/docker-library/docs
