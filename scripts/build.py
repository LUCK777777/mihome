from pathlib import Path
import os

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config-source.yaml"
DIST = ROOT / "dist"
TEST_URL = "https://www.gstatic.com/generate_204"
SUB_MARK = "${SUB_URL}"
TEST_GROUP_TYPES = {"url-test", "fallback", "load-balance"}


yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096


def load_source():
    with SOURCE.open() as f:
        return yaml.load(f)


def write_config(name, data):
    DIST.mkdir(exist_ok=True)
    with (DIST / f"{name}.yaml").open("w") as f:
        yaml.dump(data, f)


def replace_sub_url(node, sub_url):
    if isinstance(node, CommentedMap):
        for key, value in list(node.items()):
            if isinstance(value, str):
                node[key] = value.replace(SUB_MARK, sub_url)
            else:
                replace_sub_url(value, sub_url)
    elif isinstance(node, CommentedSeq):
        for i, value in enumerate(node):
            if isinstance(value, str):
                node[i] = value.replace(SUB_MARK, sub_url)
            else:
                replace_sub_url(value, sub_url)


def set_test_urls(node):
    if isinstance(node, CommentedMap):
        if node.get("name") == "TRDR":
            return
        if node.get("type") in TEST_GROUP_TYPES and "url" in node:
            node["url"] = TEST_URL
        health = node.get("health-check")
        if isinstance(health, CommentedMap) and "url" in health:
            health["url"] = TEST_URL
        for value in node.values():
            set_test_urls(value)
    elif isinstance(node, CommentedSeq):
        for value in node:
            set_test_urls(value)


def apply_common(data, sub_url):
    replace_sub_url(data, sub_url)
    set_test_urls(data)

    for provider in data.get("rule-providers", {}).values():
        if isinstance(provider, CommentedMap):
            provider["interval"] = 86400

    for provider in data.get("proxy-providers", {}).values():
        if isinstance(provider, CommentedMap):
            provider["proxy"] = "故障转移"

    for group in data.get("proxy-groups", []):
        if not isinstance(group, CommentedMap) or group.get("name") != "AIGC":
            continue
        pattern = str(group.get("filter", ""))
        for term in ("新加坡", "狮城", "SG"):
            if term not in pattern:
                pattern += f"|{term}"
        group["filter"] = pattern


def set_dns_listen(data, value):
    data.setdefault("dns", CommentedMap())["listen"] = value


def mac(data):
    data["allow-lan"] = False
    data["geodata-loader"] = "standard"
    set_dns_listen(data, "127.0.0.1:1053")


def router(data):
    data["allow-lan"] = True
    data["geodata-loader"] = "memconservative"
    set_dns_listen(data, "0.0.0.0:7874")


def stash(data):
    data["allow-lan"] = False
    data.setdefault("dns", CommentedMap())["nameserver"] = CommentedSeq(["119.29.29.29", "223.5.5.5"])


TARGETS = {
    "mac": mac,
    "router": router,
    "stash": stash,
}


def main():
    sub_url = os.environ.get("SUB_URL", SUB_MARK)
    for name, edit in TARGETS.items():
        data = load_source()
        apply_common(data, sub_url)
        edit(data)
        write_config(name, data)


if __name__ == "__main__":
    main()
