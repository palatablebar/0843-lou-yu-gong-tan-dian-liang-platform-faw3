# 运行说明

## 启动

```bash
docker compose up --build
```

## 测试

```bash
docker compose exec -T app pytest -q
```

## 样例

- `dirty`：包含编码、列数、空值或冲突重复，适合检查隔离区；另含一组换表重叠段，楼栋账平但交接阻断，不能签发。
- `clean`：可通过当前规则并完成签发；含一个换表月房间，旧表与新表交接段首尾相接，按两段合计出账。

## 重置

```bash
docker compose down -v
docker compose up --build
```

历史批次保存在 SQLite 卷中。重置会清除本地批次与签发记录。
