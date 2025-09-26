# OSF JAIRO Cloud Add-on: Custom Add-ons for OSF in Japan

## License

[Apache License Version 2.0](LICENSE) © 2024 National Institute of Informatics

## Setting up JAIRO Cloud Add-on

An administrator of an institution can enable the JAIRO Cloud add-on from the admin panel and set up the OAuth2 client information for JAIRO Cloud. The members of the institution can link their JAIRO Cloud account with their OSF account.

If the JAIRO Cloud is non-HTTPS sites, you should set the `OAUTHLIB_INSECURE_TRANSPORT` environment variable for osf.io:

```
OAUTHLIB_INSECURE_TRANSPORT=1
```

## Linking an index on JAIRO Cloud with your project

1. Go to user settings. Under "Add-ons", select "JAIRO Cloud" and click submit.
2. Under "Configure Add-ons", select your the repository and log-in by your account.
3. Go to the the node settings page. Under "Select Add-ons", select "JAIRO Cloud" and click submit.
4. Under "Configure Add-ons", select your index and click submit.

Notes on privacy settings:
 - Only the user that linked his or her JAIRO Cloud account can change the index linked from that account. Other contributors can still deauthorize the node.
 - For contributors with write permission to the node:
    - The user can access the content of indices and items.
    - Items in index can be viewed.
    - Items can be uploaded.
 - For non-contributors, when a node is public:
    - The user can access the content of indices and items.
 - For non-contributors, when a node is private, there is no access to the WEKO add-on.

## Developer Utilities

### Quick RO-Crate/CSV generation

You can run the same payload builder that the WEKO deposit uses to inspect BagIt/RO-Crate/CSV outputs locally.

```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    addons/weko/scripts/example-manuscript-metadata.json \
    /code/tmp/demo-ro-crate.json --format ro-crate
```

- `config`: JSON metadata template under `addons/weko/scripts/`
- `output`: `/code` 内の保存先パス。`--format` で `zip` (BagIt), `ro-crate`, `csv` を指定
- `--skip-flatten`: RO-Crate の flatten を無効化可能（`--format=ro-crate` 時のみ）

```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    addons/weko/scripts/example-metadata.json \
    /code/tmp/demo-index.csv --format csv
```

`tmp` ディレクトリ配下の出力は WEKO 本番と同じ構成になる。
- BagIt (zip) を生成する場合で `index.csv` が不要なら `--skip-csv` を指定して CSV を省略できる。

#### Example

```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    addons/weko/scripts/example-manuscript-metadata.json \
    /code/tmp/demo-ro.json --format ro-crate

# Inspect the root dataset
jq '."@graph"[] | select(."@id"=="./")' tmp/demo-ro.json
```

In this output `./` has `wk:isSplited: true` and `hasPart` pointing to `#dataset-1` / `#dataset-2`; each dataset node lists only its own files in `hasPart`.
