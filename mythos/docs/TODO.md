# Mythos TODO

## Backend

- 完善动态 `PlayerFileTree` 版本计算：将 `progress.version`、`accounts.version` 以及所有会影响文件 `access_rule` 的玩家状态版本纳入版本指纹；升级当前 `pft3_` schema/prefix，并同步更新 `FileIdCodec`、`PlayerFileTree`、API、测试和架构文档。完成后，`GET /files/d/version` 的 ETag 才能独立覆盖动态文件可见性变化。
