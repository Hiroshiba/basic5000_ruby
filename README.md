# BASIC5000ルビ付き台本

JSUT BASIC5000の漢字仮名交じり文にルビを付け、静的HTMLを生成するリポジトリです。

公開URLは次の想定です。

https://hiroshiba.github.io/basic5000_ruby/

## 生成

```bash
uv sync
uv run basic5000-ruby-build
```

生成物は `site` に出力されます。

## 検証

```bash
uv run basic5000-ruby-validate
```

## デプロイ

GitHub Pages は GitHub Actions からデプロイします。
リポジトリの Pages 設定で Source を GitHub Actions にしてから、`GitHub Pagesへデプロイ` workflow を手動実行してください。

```bash
gh workflow run deploy-pages.yml
```

## 参照データ

- [JSUT](https://sites.google.com/site/shinnosuketakamichi/publication/jsut)
- [みんなで作るJSUTコーパスbasic5000](https://tyc.rei-yumesaki.net/material/minnade-jsut/)

## ライセンス

ソースコードはMITライセンスです。
