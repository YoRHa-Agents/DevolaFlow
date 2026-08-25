"""Static parity and accessibility checks for the bilingual demo site."""

from __future__ import annotations

import re
from pathlib import Path

DEMO_ROOT = Path("workflow-system/human/demo")
SHARED_I18N = DEMO_ROOT / "shared/i18n.js"
PRIMARY_PAGES = (
    Path("index.html"),
    Path("framework-chain/index.html"),
    Path("context-flow/index.html"),
    Path("benchmark-results/index.html"),
    Path("version-timeline/index.html"),
)
TRANSLATED_ATTRIBUTE = re.compile(
    r"""\b(?:data-i18n|data-i18n-placeholder|data-i18n-title|
        data-i18n-aria|data-i18n-aria-label|data-system-aria|
        data-arch-aria|data-ds-aria)\s*=\s*(["'])([^"']+)\1""",
    re.VERBOSE,
)
PROPERTY_KEY = re.compile(r"""(["'])([^"']+)\1\s*:""")
SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE)
SCRIPT_SRC = re.compile(r"""\bsrc\s*=\s*(["'])([^"']+)\1""", re.IGNORECASE)


def _object_at(source: str, start: int) -> str:
    """Return one balanced JavaScript object literal without executing it."""
    assert source[start] == "{", f"expected object at offset {start}"
    depth = 0
    quote: str | None = None
    escaped = False
    index = start

    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""

        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "/" and next_char == "/":
            newline = source.find("\n", index + 2)
            index = len(source) if newline == -1 else newline + 1
            continue
        if char == "/" and next_char == "*":
            comment_end = source.find("*/", index + 2)
            assert comment_end != -1, f"unterminated JavaScript comment at offset {index}"
            index = comment_end + 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
        index += 1

    raise AssertionError(f"unterminated JavaScript object at offset {start}")


def _variable_object(source: str, name: str) -> str:
    match = re.search(rf"\b(?:var|let|const)\s+{re.escape(name)}\s*=\s*\{{", source)
    assert match, f"could not resolve translation object {name!r}"
    return _object_at(source, match.end() - 1)


def _function_body(source: str, name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"could not resolve function {name!r}"
    return _object_at(source, match.end() - 1)


def _nested_language_object(source: str, name: str, lang: str) -> str:
    outer = _variable_object(source, name)
    match = re.search(rf"(?:^|[{{,])\s*{lang}\s*:\s*\{{", outer)
    assert match, f"could not resolve {name}.{lang} translation object"
    return _object_at(outer, match.end() - 1)


def _keys(object_source: str) -> set[str]:
    return {match.group(2) for match in PROPERTY_KEY.finditer(object_source)}


def _registered_keys(source: str) -> dict[str, set[str]]:
    """Extract addTranslations registrations from one HTML or JS source."""
    found = {"en": set(), "zh": set()}
    registration = re.compile(r"""(?:window\.)?addTranslations\(\s*(["'])(en|zh)\1\s*,\s*""")
    for match in registration.finditer(source):
        lang = match.group(2)
        value_start = match.end()
        while value_start < len(source) and source[value_start].isspace():
            value_start += 1
        if source[value_start] == "{":
            dictionary = _object_at(source, value_start)
        else:
            reference = re.match(r"([A-Za-z_$][\w$]*)(?:\.(en|zh))?", source[value_start:])
            assert reference, (
                f"could not statically resolve addTranslations({lang!r}, …) at offset {value_start}"
            )
            name, nested_lang = reference.groups()
            dictionary = (
                _nested_language_object(source, name, nested_lang)
                if nested_lang
                else _variable_object(source, name)
            )
        found[lang].update(_keys(dictionary))
    return found


def _shared_keys(source: str) -> dict[str, set[str]]:
    return {
        lang: _keys(_nested_language_object(source, "TRANSLATIONS", lang)) for lang in ("en", "zh")
    }


def _page_keys(page_path: Path, source: str, demo_root: Path) -> dict[str, set[str]]:
    available = {"en": set(), "zh": set()}
    for attrs, inline_source in SCRIPT.findall(source):
        src_match = SCRIPT_SRC.search(attrs)
        script_source = inline_source
        if src_match:
            src = src_match.group(2)
            if re.match(r"^[a-z]+://", src):
                continue
            script_path = (page_path.parent / src).resolve()
            assert script_path.is_relative_to(demo_root.resolve()), (
                f"{page_path.relative_to(demo_root)} loads script outside demo/: {src}"
            )
            assert script_path.is_file(), (
                f"{page_path.relative_to(demo_root)} references missing script {src}"
            )
            script_source = script_path.read_text(encoding="utf-8")
        registered = _registered_keys(script_source)
        for lang in ("en", "zh"):
            available[lang].update(registered[lang])
    return available


def test_demo_translation_dictionaries_have_language_parity(project_root: Path) -> None:
    """Every statically registered dictionary has identical EN/ZH key sets."""
    demo_root = project_root / DEMO_ROOT
    shared_source = (project_root / SHARED_I18N).read_text(encoding="utf-8")
    shared = _shared_keys(shared_source)
    diagnostics: list[str] = []

    if shared["en"] != shared["zh"]:
        diagnostics.append(
            "shared/i18n.js: "
            f"missing in zh={sorted(shared['en'] - shared['zh'])}; "
            f"missing in en={sorted(shared['zh'] - shared['en'])}"
        )

    registration_sources = sorted((*demo_root.rglob("*.html"), *demo_root.rglob("*.js")))
    discovered = 0
    for source_path in registration_sources:
        registered = _registered_keys(source_path.read_text(encoding="utf-8"))
        if not registered["en"] and not registered["zh"]:
            continue
        discovered += 1
        if registered["en"] != registered["zh"]:
            relative = source_path.relative_to(demo_root)
            diagnostics.append(
                f"{relative}: "
                f"missing in zh={sorted(registered['en'] - registered['zh'])}; "
                f"missing in en={sorted(registered['zh'] - registered['en'])}"
            )

    assert discovered > 0, "no page-local addTranslations registrations were discovered"
    assert not diagnostics, "EN/ZH translation parity failures:\n- " + "\n- ".join(diagnostics)


def test_demo_html_translation_keys_resolve_per_page(project_root: Path) -> None:
    """Every HTML text, placeholder, title, and ARIA key resolves in both languages."""
    demo_root = project_root / DEMO_ROOT
    shared_source = (project_root / SHARED_I18N).read_text(encoding="utf-8")
    shared = _shared_keys(shared_source)
    diagnostics: list[str] = []

    for page_path in sorted(demo_root.rglob("index.html")):
        source = page_path.read_text(encoding="utf-8")
        required = {match.group(2) for match in TRANSLATED_ATTRIBUTE.finditer(source)}
        local = _page_keys(page_path, source, demo_root)
        for lang in ("en", "zh"):
            missing = required - shared[lang] - local[lang]
            if missing:
                diagnostics.append(
                    f"{page_path.relative_to(demo_root)} [{lang}] missing {sorted(missing)}"
                )

    assert "[data-i18n-aria]" in shared_source
    aria_update = shared_source.index("document.querySelectorAll('[data-i18n-aria]')")
    language_event = shared_source.index(
        "document.dispatchEvent(new CustomEvent('devolaflow:languagechange'"
    )
    assert aria_update < language_event, "ARIA labels must update before languagechange fires"

    timeline_html = (demo_root / "version-timeline/index.html").read_text(encoding="utf-8")
    timeline_js = (demo_root / "version-timeline/version-timeline.js").read_text(encoding="utf-8")
    for key in ("vt.scope.aria", "vt.view.aria", "vt.era.aria"):
        assert f'data-i18n-aria="{key}"' in timeline_html
        assert key in shared["en"] | _registered_keys(timeline_js)["en"]
        assert key in shared["zh"] | _registered_keys(timeline_js)["zh"]
    assert "devolaflow:languagechange" in timeline_js
    assert "renderEraFilters();" in timeline_js

    assert not diagnostics, "unresolved demo translation keys:\n- " + "\n- ".join(diagnostics)


def test_catalog_recovery_errors_rerender_with_language_changes(project_root: Path) -> None:
    """Invalid catalogs keep one listener active and refresh localized error text."""
    demo_root = project_root / DEMO_ROOT
    library_html = (demo_root / "workflow-visualizer/index.html").read_text(encoding="utf-8")
    library_js = (demo_root / "workflow-visualizer/visualizer.js").read_text(encoding="utf-8")
    explorer_js = (demo_root / "stage-explorer/explorer.js").read_text(encoding="utf-8")

    library_listener = (
        "document.addEventListener('devolaflow:languagechange', handleLanguageChange);"
    )
    library_init = _function_body(library_js, "init")
    assert library_js.count(library_listener) == 1
    assert library_init.index(library_listener) < library_init.index("if (!catalogIsValid)")
    assert "showCatalogError();" in _function_body(library_js, "handleLanguageChange")
    library_error = _function_body(library_js, "showCatalogError")
    assert "text('seed.catalogError')" in library_error
    assert "summary.textContent = message;" in library_error
    library_keys = _registered_keys(library_html)
    assert "seed.catalogError" in library_keys["en"] & library_keys["zh"]

    explorer_listener = (
        "document.addEventListener('devolaflow:languagechange', handleLanguageChange);"
    )
    assert explorer_js.count(explorer_listener) == 1
    assert explorer_js.index(explorer_listener) < explorer_js.index("if (!seedMembership)")
    assert "showCatalogError();" in _function_body(explorer_js, "handleLanguageChange")
    explorer_error = _function_body(explorer_js, "showCatalogError")
    assert "text('exp.catalog.error')" in explorer_error
    assert "error.textContent = message;" in explorer_error
    assert "document.getElementById('primitive-count').textContent = message;" in explorer_error
    explorer_keys = _registered_keys(explorer_js)
    assert "exp.catalog.error" in explorer_keys["en"] & explorer_keys["zh"]


def test_primary_demo_pages_have_skip_links(project_root: Path) -> None:
    """The five primary destinations expose translated links to real main targets."""
    demo_root = project_root / DEMO_ROOT
    for relative_path in PRIMARY_PAGES:
        source = (demo_root / relative_path).read_text(encoding="utf-8")
        skip_link = re.search(
            r"""<a\b(?=[^>]*\bclass=["'][^"']*\bskip-link\b[^"']*["'])
                (?=[^>]*\bhref=["']\#([^"']+)["'])
                (?=[^>]*\bdata-i18n=["']common\.skip["'])[^>]*>""",
            source,
            re.VERBOSE,
        )
        assert skip_link, f"{relative_path} lacks a translated .skip-link"
        target_id = re.escape(skip_link.group(1))
        assert re.search(
            rf"""<main\b(?=[^>]*\bid=["']{target_id}["'])
                (?=[^>]*\btabindex=["']-1["'])[^>]*>""",
            source,
            re.VERBOSE,
        ), f"{relative_path} skip target #{skip_link.group(1)} is missing or not focusable"
