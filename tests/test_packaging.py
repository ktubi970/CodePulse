from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MIT_BODY = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _words(text: str) -> list[str]:
    return text.split()


def test_setuptools_packages_are_declared_explicitly() -> None:
    # Flat layouts with several top-level packages break setuptools auto-discovery.
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(pyproject["tool"]["setuptools"]["packages"])
    on_disk = {
        p.parent.name
        for p in ROOT.glob("*/__init__.py")
        if p.parent.name != "tests"
    }
    assert declared == on_disk


def test_license_is_the_canonical_mit_text() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert re.search(r"^Copyright \(c\) \d{4} \S.+$", text, re.MULTILINE)
    body = text[text.index("Permission is hereby granted"):]
    assert _words(body) == _words(CANONICAL_MIT_BODY)
