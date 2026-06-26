#!/usr/bin/env python3
"""检查编程手常用 Python 环境。"""

import importlib.util
import sys

PACKAGES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "statsmodels": "statsmodels",
    "openpyxl": "openpyxl",
    "PIL": "pillow",
}


def main():
    missing = [pip for module, pip in PACKAGES.items() if importlib.util.find_spec(module) is None]
    if missing:
        print("缺失依赖: " + ", ".join(missing))
        print("安装命令: python -m pip install " + " ".join(missing))
        return 1
    print("编程手 Python 环境 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
