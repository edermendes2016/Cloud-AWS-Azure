"""EN and PT must expose exactly the same keys, so no screen falls back to a missing text."""
import json
import pathlib

I18N = pathlib.Path(__file__).resolve().parents[1] / "app" / "web" / "i18n"


def keys(node, prefix=""):
    if isinstance(node, dict):
        return {k for name, child in node.items() for k in keys(child, f"{prefix}{name}.")}
    if isinstance(node, list):
        return {f"{prefix}[{len(node)}]"}
    return {prefix}


def test_same_keys_in_both_languages():
    en, pt = (json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8")) for lang in ("en", "pt"))
    assert keys(en) == keys(pt)
