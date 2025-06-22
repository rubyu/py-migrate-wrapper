# プロジェクト基本情報

- 名称: py-migrate-wrapper
- 目的: pythonコードからmigrate (https://github.com/golang-migrate/migrate) を呼び出すためのラッパーライブラリを提供する。

# migrateの詳細
- Readme: https://github.com/golang-migrate/migrate
- CLIコマンド: https://github.com/golang-migrate/migrate/tree/master/cmd/migrate

# サポートするmigrateのCLIコマンド

- goto
- up
- down
- drop
- version

# サポートするmigrateのオプション

- source
- path
- database
- prefetch
- lock-timeout
- verbose
- version
- help

# py-migrate-wrapper自体のオプション

- migrateのバイナリへのパス
  - デフォルトでは未指定。ツールはPATHにmigrateが存在すると仮定して動作する。

# 開発関連ファイル

- ./bin/migrate
  - migrateのバイナリ
- .env
  - postgresサーバーの情報などが記載されている

# 開発方針

- 最重要: テストの網羅性、完全性。テストパターンにヌケモレがないこと。
- テストにはsqliteとpostgresを使用する。
  - postgresはPGliteを使用する。
