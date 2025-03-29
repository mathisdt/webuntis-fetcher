VERSION 0.8

build:
    FROM python:3.13-slim-bookworm
    WORKDIR /project
    RUN pip3 install build
    COPY src src
    COPY pyproject.toml ./
    RUN python3 -m build
    SAVE ARTIFACT dist AS LOCAL dist

build-and-release-on-pypi:
    ARG --required TWINE_PASSWORD
    ARG --required GITHUB_TOKEN
    BUILD +build
    FROM python:3.13-slim-bookworm
    WORKDIR /project
    RUN pip3 install twine tomli tomli-w
    RUN apt-get update >/dev/null 2>&1 && apt-get -y install curl gpg >/dev/null 2>&1
    RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
    RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    RUN apt-get update >/dev/null 2>&1 && apt-get -y install gh >/dev/null 2>&1
    RUN if [ -z "$TWINE_PASSWORD" ]; then echo "no Twine password given"; exit 1; fi; \
        if [ -z "$GITHUB_TOKEN" ]; then echo "no Github token given"; exit 1; fi
    COPY .git .git
    COPY +build/dist dist
    RUN --push export BRANCH=$(git symbolic-ref --short HEAD); \
               echo "on branch: $BRANCH"; \
               if [ "$BRANCH" == "master" -o "$BRANCH" == "main" ]; then \
                 echo "upload to PyPI"; \
                 python3 -m twine upload --repository pypi --verbose dist/*; \
                 echo "increase version number"; \
                 python3 <<EOF \
                 import tomli, tomli_w \
                 with open("pyproject.toml", "rb") as f: \
                   data = tomli.load(f) \
                 print(f'previous version: {data["project"]["version"]}') \
                 data["project"]["version"] = str(int(data["project"]["version"])+1) \
                 print(f'updated version:  {data["project"]["version"]}') \
                 with open("pyproject.toml", "wb") as f: \
                   tomli_w.dump(data, f) \
                 EOF; \
                 echo "commit and push increased version"; \
                 export DESTINATION_BRANCH=$(git rev-parse --abbrev-ref HEAD); \
                 export SHA=$(git rev-parse $DESTINATION_BRANCH:$FILE_TO_COMMIT); \
                 export CONTENT=$(base64 -i $FILE_TO_COMMIT); \
                 gh api --method PUT /repos/:owner/:repo/contents/pyproject.toml \
                   --field message="update version number [skip actions]" \
                   --field content="$CONTENT" \
                   --field encoding="base64" \
                   --field branch="$DESTINATION_BRANCH" \
                   --field sha="$SHA"; \
               else \
                 echo "not uploading to PyPI"; \
               fi
