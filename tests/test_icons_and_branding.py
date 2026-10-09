"""Automated verification suite for 2026 FreeLanSync Iconography & Branding.
Enforces the 14-Phase Spec-Driven, Anti-Slop invariants across Android, Desktop, and Web.
"""
from pathlib import Path
from PIL import Image
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
RES_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "res"
DESKTOP_BUILD_DIR = REPO_ROOT / "desktop-app" / "build"
WEB_INDEX = REPO_ROOT / "server" / "static" / "index.html"


def test_android_vector_layers():
    """Verify adaptive icon vector foreground and background syntax and color tokens."""
    fg_xml = RES_DIR / "drawable" / "ic_launcher_foreground.xml"
    bg_xml = RES_DIR / "drawable" / "ic_launcher_background.xml"
    assert fg_xml.exists(), "Foreground XML missing"
    assert bg_xml.exists(), "Background XML missing"

    fg_text = fg_xml.read_text(encoding="utf-8")
    assert 'android:viewportWidth="108"' in fg_text
    assert 'android:viewportHeight="108"' in fg_text
    # Canonical colors: Cyan (#38BDF8) & Indigo (#6366F1)
    assert "#38BDF8" in fg_text
    assert "#6366F1" in fg_text
    # Zero legacy AI slop
    assert "aiOrbit" not in fg_text
    assert "diamond" not in fg_text.lower()

    bg_text = bg_xml.read_text(encoding="utf-8")
    assert "#FF0F172A" in bg_text or "#0F172A" in bg_text
    assert "#FF020617" in bg_text or "#020617" in bg_text


def test_android_themed_icons_support():
    """Verify Android 13+ Material You monochrome themed icon declaration."""
    for filename in ["ic_launcher.xml", "ic_launcher_round.xml"]:
        xml_path = RES_DIR / "mipmap-anydpi-v26" / filename
        assert xml_path.exists(), f"{filename} missing"
        text = xml_path.read_text(encoding="utf-8")
        assert "<monochrome" in text, f"Missing <monochrome> in {filename}"
        assert 'android:drawable="@drawable/ic_launcher_foreground"' in text


def test_android_mipmap_png_dimensions():
    """Verify all raster mipmap PNG fallbacks match required OEM density dimensions."""
    expected_densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in expected_densities.items():
        dir_path = RES_DIR / folder
        for name in ["ic_launcher.png", "ic_launcher_round.png"]:
            file_path = dir_path / name
            assert file_path.exists(), f"Missing {file_path}"
            with Image.open(file_path) as img:
                assert img.size == (size, size), f"{name} in {folder} has size {img.size}, expected ({size}, {size})"
                assert img.format == "PNG"


def test_desktop_app_icon_assets():
    """Verify Desktop electron build artifacts: 512px icon, multi-res ICO, and 16/32px tray."""
    icon_png = DESKTOP_BUILD_DIR / "icon.png"
    icon_ico = DESKTOP_BUILD_DIR / "icon.ico"
    tray_16 = DESKTOP_BUILD_DIR / "tray.png"
    tray_32 = DESKTOP_BUILD_DIR / "tray@2x.png"

    assert icon_png.exists(), "Desktop icon.png missing"
    with Image.open(icon_png) as img:
        assert img.size == (512, 512)

    assert icon_ico.exists(), "Desktop icon.ico missing"
    assert icon_ico.stat().st_size > 1000, "Desktop icon.ico is empty or truncated"

    assert tray_16.exists(), "Desktop tray.png missing"
    with Image.open(tray_16) as img:
        assert img.size == (16, 16)
        # Must have alpha transparency for tray
        assert img.mode == "RGBA"

    assert tray_32.exists(), "Desktop tray@2x.png missing"
    with Image.open(tray_32) as img:
        assert img.size == (32, 32)
        assert img.mode == "RGBA"


def test_web_branding_and_anti_slop():
    """Verify web dashboard header, modal, and favicon use clean 2026 glyph and zero AI slop."""
    assert WEB_INDEX.exists()
    content = WEB_INDEX.read_text(encoding="utf-8")

    # Anti-Slop verification: No leftover AI agent orbit/spark artifacts
    assert "aiOrbit" not in content
    assert "ai-agent" not in content
    assert "aiSqBg" not in content
    assert "aiCore" not in content

    # Canonical 2026 Continuity Glyph elements present
    assert "FreeLanSync 2026 Continuity" in content
    assert "Gigabit Continuity Hub" in content
    assert "#38BDF8" in content
    assert "#6366F1" in content

