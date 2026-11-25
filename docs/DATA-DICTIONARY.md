# 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `building_id` | text | 业务字段 |
| `meter_id` | text | 主键 |
| `room_id` | text | 业务字段 |
| `area_m2` | decimal | 业务字段；同一房间多块表取值必须一致，分摊只计一次 |
| `start_reading` | decimal | 业务字段；本表本周期起读数 |
| `end_reading` | decimal | 业务字段；本表本周期止读数 |
| `main_kwh` | decimal | 业务字段；楼栋总表周期电量 |
| `handover_from` | decimal 可空 | 换表交接段起点（房间累计电量轴，kWh），与 `handover_to` 同时为空或同时提供 |
| `handover_to` | decimal 可空 | 换表交接段终点；多表房间各段须首尾相接，段长等于该表计差 |

空字符串、`-`、`NA`、`null` 和 `未提供` 按空值处理。金额字段在整理层转为整数分或整数最小单位；日期按 ISO 日期解析；带时间的字段按本地时间解析。标识字段保持为文本，前导零不会被去除。
