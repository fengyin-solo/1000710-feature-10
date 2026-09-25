"""照明设施业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.seed import LIGHT_INSPECTION_SEED
from app.store import store

MODULE = "light"
REQUIRED_FIELDS = ["设施编号", "灯杆编号", "灯具类型"]
STATUS_ORDER = ["待检修", "正常亮灯", "缺亮待修", "已停用"]
ACTION_RULES = {"安排检修": "正常亮灯", "确认正常": "缺亮待修", "停用设施": "已停用"}
NEGATIVE_ACTIONS = ["停用设施"]

INSPECTION_REQUIRED_FIELDS = ["巡检日期", "本次结论"]
INSPECTION_FIELDS = ["巡检日期", "灯具类型", "上次更换时间", "本次结论", "巡检人", "备注"]


class LightService:
    def __init__(self) -> None:
        # 巡检记录单独留档：真实项目里是一张巡检表，这里先用内存列表顶住。
        self._inspections: list[dict[str, Any]] = [dict(row) for row in LIGHT_INSPECTION_SEED]

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        lamp_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("设施编号", "")) or keyword in str(row.get("灯杆编号", ""))
            ]
        if lamp_type:
            rows = [row for row in rows if lamp_type in str(row.get("灯具类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._with_latest(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return self._with_latest(row)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._with_latest(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"照明设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于照明设施可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._with_latest(entry), f"照明设施已{action}"

    def list_inspections(self, light_id: int) -> list[dict[str, Any]]:
        """单根灯杆的巡检留档，按巡检日期倒序，最近的排在最前。"""
        records = [row for row in self._inspections if int(row.get("light_id", 0)) == light_id]
        return sorted(
            records,
            key=lambda row: (str(row.get("巡检日期", "")), int(row.get("id", 0))),
            reverse=True,
        )

    def latest_inspection(self, light_id: int) -> dict[str, Any] | None:
        records = self.list_inspections(light_id)
        return records[0] if records else None

    def create_inspection(
        self, light_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, bool, str]:
        """登记一次巡检；同一灯杆同一天重复提交时只保留最新一条。"""
        entry = store.find(MODULE, light_id)
        if entry is None:
            return None, False, f"照明设施 {light_id} 不存在或已归档"
        missing = [field for field in INSPECTION_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, False, f"缺少必填字段：{'、'.join(missing)}"
        cleaned = {field: str(values.get(field) or "").strip() for field in INSPECTION_FIELDS}
        if not cleaned["灯具类型"]:
            cleaned["灯具类型"] = str(entry.get("灯具类型") or "")
        existing = next(
            (
                row for row in self._inspections
                if int(row.get("light_id", 0)) == light_id and str(row.get("巡检日期", "")) == cleaned["巡检日期"]
            ),
            None,
        )
        pole = entry.get("灯杆编号") or entry.get("设施编号") or light_id
        if existing is not None:
            existing.update(cleaned)
            return existing, False, f"灯杆 {pole} 在 {cleaned['巡检日期']} 已有巡检记录，已更新为最新一条"
        record = {"id": max((int(row.get("id", 0)) for row in self._inspections), default=0) + 1}
        record["light_id"] = light_id
        record.update(cleaned)
        self._inspections.append(record)
        return record, True, f"灯杆 {pole} 的巡检记录已登记留档"

    def _with_latest(self, row: dict[str, Any]) -> dict[str, Any]:
        """台账与详情共用一个出口：都带上最近一次巡检，保证两边看到的一致。"""
        entry = dict(row)
        entry["最近巡检"] = self.latest_inspection(int(row.get("id", 0)))
        return entry
