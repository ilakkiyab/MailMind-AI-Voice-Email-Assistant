"""Check WCAG text contrast directly against the shipped theme palette."""
import re
from pathlib import Path
import tomllib

from email_assistant.ui import theme


def contrast(foreground, background):
    def luminance(color):
        color = color.lstrip('#')
        if len(color) == 3:
            color = ''.join(channel * 2 for channel in color)
        channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + .05) / (dark + .05)


def stylesheet():
    return Path(theme.__file__).read_text(encoding='utf-8')


def test_button_palettes_have_readable_text_in_every_state():
    palettes = re.findall(r'--button-bg:(#[\da-f]+);\s*--button-hover:(#[\da-f]+);\s*--button-active:(#[\da-f]+);\s*--button-ink:(#[\da-f]+)', stylesheet())
    assert palettes
    for normal, hover, active, ink in palettes:
        for background in (normal, hover, active):
            assert contrast(ink, background) >= 4.5, (ink, background)


def test_explicit_surface_text_pairs_have_readable_contrast():
    pairs = re.findall(r'background:(#[\da-f]+)(?:!important)?;\s*color:(#[\da-f]+)', stylesheet())
    assert pairs
    for background, ink in pairs:
        assert contrast(ink, background) >= 4.5, (ink, background)


def test_base_theme_and_secondary_text_contrast():
    config = tomllib.loads((Path(__file__).parents[1] / '.streamlit/config.toml').read_text())['theme']
    muted = re.search(r'--muted:(#[\da-f]+)', stylesheet()).group(1)
    for background in (config['backgroundColor'], config['secondaryBackgroundColor'], '#fff'):
        for ink in (config['textColor'], muted):
            assert contrast(ink, background) >= 4.5
