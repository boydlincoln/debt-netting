"""本地配置：与业务数据分离存放，密钥只留在本机配置文件中。"""
from __future__ import annotations

import copy
import json
import os
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "settings.json"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "debt_netting.db"
MATERIAL_DIR = DATA_DIR / "materials"
EXPORT_DIR = DATA_DIR / "exports"
ONTOLOGY_PATH = ROOT / "ontology" / "debt_ontology.owl"
WEB_DIR = ROOT / "web"

PROVIDER_PRESETS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "qwen": {
        "label": "通义千问（DashScope 兼容模式）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "wenxin": {
        "label": "文心一言（千帆 v2）",
        "base_url": "https://qianfan.baidubce.com/v2",
        "model": "ernie-4.5-turbo-128k",
    },
    "custom": {
        "label": "自定义 OpenAI 兼容接口",
        "base_url": "",
        "model": "",
    },
}

DEFAULT_SETTINGS = {
    "as_of_date": None,                     # None 表示取当天
    "masking": True,                        # 上传线上模型前脱敏
    "allow_text_upload": True,              # 是否允许原始材料文本出本地上云
    "include_priority_groups": True,        # 优先顺位债权按组独立参与净额计算
    "exact_solver_seconds": 3.0,            # 精确求解时间预算
    "review_required_for_ai": True,         # AI 抽取结果须人工复核后才入池
    "llm": {
        "enabled": False,
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "",
        "temperature": 0.1,
        "timeout": 60,
        "json_mode": True,
    },
    "installments": {
        "enabled": True,
        "period_days": 30,
        "periods": 3,
    },
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Settings:
    """线程安全的本地 JSON 配置。"""

    def __init__(self, path: Path | None = None):
        self.path = path or CONFIG_PATH
        self._lock = threading.RLock()
        self._data: dict = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> dict:
        with self._lock:
            data = copy.deepcopy(DEFAULT_SETTINGS)
            if self.path.exists():
                try:
                    patch = json.loads(self.path.read_text(encoding="utf-8"))
                    data = _deep_merge(data, patch)
                except (OSError, ValueError):
                    pass
            env_key = os.environ.get("DEBT_LLM_API_KEY", "").strip()
            if env_key:
                data["llm"]["api_key"] = env_key
            self._data = data
            return copy.deepcopy(data)

    def save(self, patch: dict | None = None) -> dict:
        with self._lock:
            if patch:
                self._data = _deep_merge(self._data, patch)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
            return copy.deepcopy(self._data)

    @property
    def data(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def as_of_date(self) -> str:
        value = self.data.get("as_of_date")
        if value:
            return str(value)
        return date.today().isoformat()

    def public(self) -> dict:
        """返回可下发前端的配置（密钥脱敏）。"""
        data = self.data
        key = (data.get("llm") or {}).get("api_key") or ""
        data["llm"]["has_api_key"] = bool(key)
        if key:
            data["llm"]["api_key_masked"] = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        data["llm"]["api_key"] = ""
        data["providers"] = PROVIDER_PRESETS
        data["paths"] = {
            "ontology": str(ONTOLOGY_PATH),
            "database": str(DB_PATH),
            "config": str(self.path),
        }
        return data
