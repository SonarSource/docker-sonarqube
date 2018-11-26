Develop
=======

Helpful notes for developers of the images.

Releasing a new version of an image
-----------------------------------

Create the new image for the new version:

1. Rename the last version's directory, for example `7.4-community` to `7.5-community`
2. Update the version in `Dockerfile`, and make any other necessary changes (usually none)
3. Run tests, for example: `./run-tests.sh 7.5-community`
4. Create a Pull Request, confirm Travis build passes, get it reviewed and merged

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

Other notes
-----------

The `-alpine` images are not listed on [Docker Hub][hub] because they don't run well on Linux. See [this issue reported for openjdk-alpine](https://github.com/docker-library/openjdk/issues/250), vote for it, or contribute potential solutions or even just solution ideas. We left the recipes for these images in `master`, for easy testing and troubleshooting. You can verify your experiments by modifying an image, say `7.4-community-alpine`, and then run `./build-and-run.sh 7.4-community-alpine` on Linux. If the service doesn't crash, your fix is probably good, and we'll be happy to see it, and make these images official.

---

To control the generated content of the Docker Hub page, look around in the files in `.template-helpers` of the [`docs` repository][docs]. For example, the "Where to get help" section is customized by a copy of `.template-helpers/get-help.md` in `sonarqube/get-help.md`.

---

For more details on the release process, see the documentation in these repositories:

- https://github.com/docker-library/docs
- https://github.com/docker-library/official-images

[hub]: https://hub.docker.com/_/sonarqube/
[docs]: https://github.com/docker-library/docs
