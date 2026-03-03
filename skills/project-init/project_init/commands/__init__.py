"""project-init 指令模組.

提供 check 和 setup 兩個指令入口。
"""

from project_init.commands.check import run_check
from project_init.commands.setup import run_setup

__all__ = [
    "run_check",
    "run_setup",
]
