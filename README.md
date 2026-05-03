# Mihomo Config Generator

`config-source.yaml` 是唯一母版，`scripts/build.py` 生成 `dist/mac.yaml`、`dist/router.yaml`、`dist/stash.yaml`。

```sh
python -m pip install -r requirements.txt
SUB_URL="https://example.com/sub" python scripts/build.py
SUB_URL="https://example.com/sub" python scripts/check.py
```

GitHub Actions 使用仓库 Secret `SUB_URL` 每天自动生成并上传 `dist` artifact，也支持手动运行。
