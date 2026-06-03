#!/usr/bin/env python3
"""
config_loader 模組單元測試
"""

import unittest
from unittest.mock import patch, mock_open
import sys
import json
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import (
    load_config,
    load_agents_config,
    load_quality_rules,
    clear_config_cache,
    get_config_dir,
)


class TestGetConfigDir(unittest.TestCase):
    """測試 get_config_dir 函式"""

    @patch.dict('os.environ', {'CLAUDE_PROJECT_DIR': '/test/project'})
    def test_with_env_var(self):
        """測試使用環境變數"""
        config_dir = get_config_dir()
        self.assertEqual(str(config_dir), "/test/project/.claude/config")


class TestLoadAgentsConfig(unittest.TestCase):
    """測試 load_agents_config 函式"""

    def setUp(self):
        """每個測試前清除快取"""
        clear_config_cache()

    def test_default_config(self):
        """測試預設配置"""
        with patch('config_loader.load_config', side_effect=FileNotFoundError):
            config = load_agents_config()
            self.assertIn("known_agents", config)
            self.assertIn("agent_dispatch_rules", config)
            self.assertIn("basil-hook-architect", config["known_agents"])

    def test_config_caching(self):
        """測試配置快取"""
        with patch('config_loader.load_config') as mock_load:
            mock_load.return_value = {"known_agents": ["test-agent"]}
            # 第一次呼叫
            config1 = load_agents_config()
            # 第二次呼叫應使用快取
            config2 = load_agents_config()
            # 只應該呼叫一次
            self.assertEqual(mock_load.call_count, 1)
            self.assertEqual(config1, config2)


class TestLoadQualityRules(unittest.TestCase):
    """測試 load_quality_rules 函式"""

    def setUp(self):
        """每個測試前清除快取"""
        clear_config_cache()

    def test_default_config(self):
        """測試預設配置"""
        with patch('config_loader.load_config', side_effect=FileNotFoundError):
            config = load_quality_rules()
            self.assertIn("trigger_conditions", config)
            self.assertIn("cache", config)
            self.assertIn("decision_rules", config)


class TestClearConfigCache(unittest.TestCase):
    """測試 clear_config_cache 函式"""

    def test_clear_cache(self):
        """測試清除快取"""
        with patch('config_loader.load_config') as mock_load:
            mock_load.return_value = {"test": "value"}
            # 載入配置
            load_agents_config()
            # 清除快取
            clear_config_cache()
            # 再次載入應該重新呼叫
            load_agents_config()
            self.assertEqual(mock_load.call_count, 2)


if __name__ == "__main__":
    unittest.main()
