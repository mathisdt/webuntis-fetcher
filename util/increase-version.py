# this script is used in the pipeline build

import tomli, tomli_w

with open("pyproject.toml", "rb") as f:
    data = tomli.load(f)
print(f'previous version: {data["project"]["version"]}')
data["project"]["version"] = str(int(data["project"]["version"]) + 1)
print(f'updated version:  {data["project"]["version"]}')
with open("pyproject.toml", "wb") as f:
    tomli_w.dump(data, f)
