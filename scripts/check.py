from pathlib import Path
import os
import sys

from ruamel.yaml import YAML


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config-source.yaml"
DIST = ROOT / "dist"
TEST_URL = "https://www.gstatic.com/generate_204"
SUB_MARK = "${SUB_URL}"
TEST_GROUP_TYPES = {"url-test", "fallback", "load-balance"}
TARGETS = {
    "mac": {"allow-lan": False, "geodata-loader": "standard", "listen": "127.0.0.1:1053"},
    "router": {"allow-lan": True, "geodata-loader": "memconservative", "listen": "0.0.0.0:7874"},
    "stash": {"allow-lan": False},
}


yaml = YAML(typ="safe")


def fail(errors, message):
    errors.append(message)


def load(path, errors):
    try:
        with path.open() as f:
            return yaml.load(f)
    except Exception as exc:
        fail(errors, f"{path}: YAML 解析失败: {exc}")
        return None


def walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def group(data, name):
    for item in data.get("proxy-groups", []) or []:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def check_common(data, errors, name):
    for node in walk(data):
        if not isinstance(node, dict) or node.get("name") == "TRDR":
            continue
        if node.get("type") in TEST_GROUP_TYPES and node.get("url") != TEST_URL:
            fail(errors, f"{name}: 测速分组 URL 未统一")
        health = node.get("health-check")
        if isinstance(health, dict) and health.get("url") != TEST_URL:
            fail(errors, f"{name}: health-check URL 未统一")

    for key, provider in (data.get("rule-providers") or {}).items():
        if provider.get("interval") != 86400:
            fail(errors, f"{name}: rule-provider {key} interval 不是 86400")
        url = provider.get("url", "")
        if url and not url.startswith(("http://", "https://")):
            fail(errors, f"{name}: rule-provider {key} URL 无效")

    sub_url = os.environ.get("SUB_URL")
    for key, provider in (data.get("proxy-providers") or {}).items():
        if provider.get("proxy") != "故障转移":
            fail(errors, f"{name}: proxy-provider {key} proxy 不是 故障转移")
        url = provider.get("url")
        if sub_url and url != sub_url:
            fail(errors, f"{name}: proxy-provider {key} 未使用 SUB_URL")
        if not sub_url and url != SUB_MARK:
            fail(errors, f"{name}: proxy-provider {key} 订阅 URL 不应写死")

    aigc = group(data, "AIGC")
    aigc_filter = str((aigc or {}).get("filter", ""))
    if not all(term in aigc_filter for term in ("新加坡", "狮城", "SG")):
        fail(errors, f"{name}: AIGC 正则未包含新加坡/狮城/SG")


def check_target(data, errors, name):
    expected = TARGETS[name]
    if data.get("allow-lan") is not expected["allow-lan"]:
        fail(errors, f"{name}: allow-lan 不正确")
    if "geodata-loader" in expected and data.get("geodata-loader") != expected["geodata-loader"]:
        fail(errors, f"{name}: geodata-loader 不正确")
    if "listen" in expected and (data.get("dns") or {}).get("listen") != expected["listen"]:
        fail(errors, f"{name}: dns.listen 不正确")
    if name == "stash":
        nameservers = (data.get("dns") or {}).get("nameserver")
        if nameservers != ["119.29.29.29", "223.5.5.5"]:
            fail(errors, "stash: DNS nameserver 未简化")


def main():
    errors = []
    if not SOURCE.exists():
        fail(errors, "缺少 config-source.yaml")
    source = load(SOURCE, errors) if SOURCE.exists() else None
    if source:
        for key, provider in (source.get("proxy-providers") or {}).items():
            if provider.get("url") != SUB_MARK:
                fail(errors, f"config-source.yaml: proxy-provider {key} 订阅 URL 必须使用 ${{SUB_URL}}")

    for name in TARGETS:
        path = DIST / f"{name}.yaml"
        if not path.exists():
            fail(errors, f"缺少 {path}")
            continue
        data = load(path, errors)
        if data is None:
            continue
        if source and group(source, "TRDR") != group(data, "TRDR"):
            fail(errors, f"{name}: TRDR 分组被修改")
        if source and source.get("tun") != data.get("tun"):
            fail(errors, f"{name}: tun 配置被修改")
        check_common(data, errors, name)
        check_target(data, errors, name)

    if errors:
        print("\n".join(errors))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
