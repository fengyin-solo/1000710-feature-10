"""照明设施业务规则：状态流转、巡检留档、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "light"
REQUIRED_FIELDS = ["设施编号", "灯杆编号", "灯具类型"]
STATUS_ORDER = ["待检修", "正常亮灯", "缺亮待修", "已停用"]
ACTION_RULES = {"安排检修": "正常亮灯", "确认正常": "缺亮待修", "停用设施": "已停用"}
NEGATIVE_ACTIONS = ["停用设施"]
INSPECTION_REQUIRED_FIELDS = ["巡检日期", "灯具类型", "上次更换时间", "本次结论"]
INSPECTION_DATE_FIELDS = ["巡检日期", "上次更换时间"]


class LightService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        pole: str | None = None,
        lamp: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设施编号", ""))]
        if pole:
            rows = [row for row in rows if pole in str(row.get("灯杆编号", ""))]
        if lamp:
            rows = [row for row in rows if lamp in str(row.get("灯具类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._with_latest(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        data = self._with_latest(entry)
        data["inspections"] = self._sorted_inspections(entry)
        return data

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
        return entry, []

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
        return entry, f"照明设施已{action}"

    def add_inspection(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        """给灯杆留一条巡检记录；同一根灯杆同一天重复提交时覆盖旧记录，只留最新一条。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"照明设施 {entry_id} 不存在或已归档", False
        missing = [field for field in INSPECTION_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}", False
        cleaned = {field: str(values.get(field) or "").strip() for field in INSPECTION_REQUIRED_FIELDS}
        for field in INSPECTION_DATE_FIELDS:
            try:
                date.fromisoformat(cleaned[field])
            except ValueError:
                return None, f"{field}格式应为 YYYY-MM-DD，请检查后重试", False
        inspections = entry.setdefault("inspections", [])
        for record in inspections:
            if record.get("巡检日期") == cleaned["巡检日期"]:
                record.update(cleaned)
                return record, "", True
        record = {"id": max((int(item.get("id", 0)) for item in inspections), default=0) + 1}
        record.update(cleaned)
        inspections.append(record)
        return record, "", False

    def _sorted_inspections(self, entry: dict[str, Any]) -> list[dict[str, Any]]:
        inspections = entry.get("inspections") or []
        return sorted(
            inspections,
            key=lambda item: (str(item.get("巡检日期", "")), int(item.get("id", 0))),
            reverse=True,
        )

    def _with_latest(self, row: dict[str, Any]) -> dict[str, Any]:
        """台账与详情共用的汇总口径：最近巡检都取同一条记录，保证两边一致。"""
        data = {key: value for key, value in row.items() if key != "inspections"}
        inspections = self._sorted_inspections(row)
        data["最近巡检"] = inspections[0] if inspections else None
        return data
