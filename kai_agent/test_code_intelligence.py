#!/usr/bin/env python3
"""
Tests for Kai Code Intelligence module.
Run: python3 -m pytest kai_agent/test_code_intelligence.py -v
     or: python3 kai_agent/test_code_intelligence.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure we can import from parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.code_intelligence import (
    CodeAnalysis,
    CodeIntelligence,
    ToolRegistry,
    analyze_code,
    analyze_file,
    detect_language,
    generate_class,
    generate_function,
    generate_test,
    scan_project,
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def test_detect_language():
    assert detect_language("foo.py") == "python"
    assert detect_language("bar.js") == "javascript"
    assert detect_language("baz.tsx") == "typescript"
    assert detect_language("Cargo.toml") == "unknown"
    assert detect_language(Path("src/main.go")) == "go"


# ---------------------------------------------------------------------------
# Python analysis
# ---------------------------------------------------------------------------

PYTHON_SAMPLE = """\
import os
import json
from pathlib import Path

def process_data(data: dict, config: dict) -> dict:
    '''Process data with configuration.'''
    result = {}
    for key, value in data.items():
        if key in config.get('allowed_keys', []):
            result[key] = value * 2
    return result

class DataProcessor:
    def __init__(self, name: str):
        self.name = name
        self.data = {}

    def load(self, file_path: str) -> bool:
        with open(file_path) as f:
            self.data = json.load(f)
        return True
"""


def test_python_analysis():
    r = analyze_code(PYTHON_SAMPLE, "python")
    assert r.language == "python"
    assert r.lines > 20
    assert "process_data" in r.functions
    assert "DataProcessor" in r.classes
    assert "os" in r.imports
    assert "json" in r.imports
    assert r.complexity >= 2  # has a for + if


# ---------------------------------------------------------------------------
# JavaScript analysis
# ---------------------------------------------------------------------------

JS_SAMPLE = """\
import React from 'react';
import { useState } from 'react';

function Counter() {
    const [count, setCount] = useState(0);
    const increment = () => setCount(count + 1);
    return <div><h1>{count}</h1></div>;
}

export default Counter;
"""


def test_js_analysis():
    r = analyze_code(JS_SAMPLE, "javascript")
    assert r.language == "javascript"
    assert "Counter" in r.functions
    assert "react" in r.imports


# ---------------------------------------------------------------------------
# Generic language fallback
# ---------------------------------------------------------------------------

def test_generic_analysis():
    r = analyze_code("some random\nstuff here\n", "go")
    assert r.language == "go"
    assert r.lines >= 2
    assert r.functions == []


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

def test_gen_function_python():
    code = generate_function("add", ["a: int", "b: int"], "int", "Add two numbers")
    assert "def add(a: int, b: int) -> int:" in code
    assert "Add two numbers" in code


def test_gen_function_js():
    code = generate_function("greet", ["name"], "string", "Say hi", "javascript")
    assert "function greet(name)" in code


def test_gen_class_python():
    code = generate_class("MyClass", ["save", "load"], "BaseClass")
    assert "class MyClass(BaseClass):" in code
    assert "def save(self)" in code


def test_gen_class_js():
    code = generate_class("Widget", ["render"], None, "javascript")
    assert "class Widget" in code
    assert "render()" in code


def test_gen_test():
    code = generate_test("add", [{"input": [1, 2], "expected": 3}])
    assert "class TestAdd(unittest.TestCase):" in code
    assert "test_add_1" in code
    assert "self.assertEqual" in code


# ---------------------------------------------------------------------------
# File analysis (real file)
# ---------------------------------------------------------------------------

def test_analyze_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(PYTHON_SAMPLE)
        f.flush()
        r = analyze_file(f.name)
    os.unlink(f.name)
    assert r.language == "python"
    assert "process_data" in r.functions
    assert "DataProcessor" in r.classes


def test_analyze_file_missing():
    r = analyze_file("/no/such/file.py")
    assert r.issues
    assert "not found" in r.issues[0].lower()


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def test_tool_registry():
    reg = ToolRegistry()
    reg.register("echo", "Echo input", "test", lambda x: x, {"x": str})
    reg.register("add", "Add numbers", "math", lambda a, b: a + b, {"a": int, "b": int})

    tools = reg.list_tools()
    names = [t["name"] for t in tools]
    assert "echo" in names
    assert "add" in names

    # handler should not appear in list_tools output
    for t in tools:
        assert "handler" not in t

    assert reg.execute("echo", x="hello") == "hello"
    assert reg.execute("add", a=2, b=3) == 5
    assert "error" in reg.execute("nonexistent")


def test_tool_registry_categories():
    reg = ToolRegistry()
    reg.register("a", "", "cat1", lambda: 1)
    reg.register("b", "", "cat1", lambda: 2)
    reg.register("c", "", "cat2", lambda: 3)

    assert len(reg.list_tools("cat1")) == 2
    assert len(reg.list_tools("cat2")) == 1
    assert len(reg.list_tools("cat3")) == 0


# ---------------------------------------------------------------------------
# Project scanner
# ---------------------------------------------------------------------------

def test_scan_project():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "main.py").write_text("print('hi')\n")
        (Path(td) / "index.js").write_text("console.log('hi');\n")
        (Path(td) / "sub").mkdir()
        (Path(td) / "sub" / "util.py").write_text("def helper(): pass\n")

        result = scan_project(td)
        assert "main.py" in result["files"]
        assert "sub/util.py" in result["files"]
        assert result["languages"].get("python", 0) == 2
        assert result["languages"].get("javascript", 0) == 1
        assert result["total_lines"] >= 3


# ---------------------------------------------------------------------------
# CodeIntelligence facade
# ---------------------------------------------------------------------------

def test_facade():
    ci = CodeIntelligence()
    r = ci.analyze("def foo(): pass", "python")
    assert "foo" in r.functions

    code = ci.gen_function("bar", ["x: int"], "str")
    assert "def bar" in code

    tools = ci.list_tools()
    assert any(t["name"] == "analyze_code" for t in tools)

    result = ci.execute_tool("analyze_code", code="def test(): pass", language="python")
    assert hasattr(result, "functions") or "functions" in result


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {t.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Passed: {passed}  Failed: {failed}  Total: {passed + failed}")
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
