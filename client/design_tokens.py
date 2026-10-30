"""Semantic SGF-AP design tokens shared by login and registration screens.

The client consumes functional names rather than hard-coded colors.  The
contrast helpers are intentionally dependency-free so build-time checks can run
before an Android package is assembled.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ColorToken:
    name: str
    hex: str
    opacity: float = 1.0


# A restrained blue/teal identity keeps the application distinct while the
# neutral surfaces leave business-state colors available for their meanings.
_COLOR_VALUES = {
    "primary": ColorToken("primary", "#0B3D91"),
    "primary_light": ColorToken("primary_light", "#DCE8FA"),
    "primary_dark": ColorToken("primary_dark", "#072A63"),
    "secondary": ColorToken("secondary", "#0F766E"),
    "secondary_light": ColorToken("secondary_light", "#CCFBF1"),
    "secondary_dark": ColorToken("secondary_dark", "#134E4A"),
    "accent": ColorToken("accent", "#B45309"),
    "background_general": ColorToken("background_general", "#F8FAFC"),
    "surface": ColorToken("surface", "#FFFFFF"),
    "surface_subtle": ColorToken("surface_subtle", "#F1F5F9"),
    "field_background": ColorToken("field_background", "#FFFFFF"),
    "text_primary": ColorToken("text_primary", "#0F172A"),
    "text_secondary": ColorToken("text_secondary", "#475569"),
    "text_help": ColorToken("text_help", "#334155"),
    "text_placeholder": ColorToken("text_placeholder", "#64748B"),
    "text_on_primary": ColorToken("text_on_primary", "#FFFFFF"),
    "text_on_dark": ColorToken("text_on_dark", "#FFFFFF"),
    "border": ColorToken("border", "#64748B"),
    "border_subtle": ColorToken("border_subtle", "#CBD5E1"),
    "focus": ColorToken("focus", "#1D4ED8"),
    "disabled_background": ColorToken("disabled_background", "#E2E8F0"),
    "disabled_text": ColorToken("disabled_text", "#64748B"),
    "success": ColorToken("success", "#166534"),
    "success_background": ColorToken("success_background", "#DCFCE7"),
    "error": ColorToken("error", "#B91C1C"),
    "error_background": ColorToken("error_background", "#FEE2E2"),
    "warning": ColorToken("warning", "#92400E"),
    "warning_background": ColorToken("warning_background", "#FEF3C7"),
    "info": ColorToken("info", "#1E40AF"),
    "info_background": ColorToken("info_background", "#DBEAFE"),
    "overlay": ColorToken("overlay", "#0F172A", 0.48),
    "shadow": ColorToken("shadow", "#0F172A", 0.18),
    "empty": ColorToken("empty", "#64748B"),
    "account_active": ColorToken("account_active", "#166534"),
    "account_inactive": ColorToken("account_inactive", "#64748B"),
    "priority_high": ColorToken("priority_high", "#B91C1C"),
    "priority_standard": ColorToken("priority_standard", "#475569"),
    "ticket_registered": ColorToken("ticket_registered", "#1E40AF"),
    "ticket_validated": ColorToken("ticket_validated", "#0F766E"),
    "ticket_prioritized": ColorToken("ticket_prioritized", "#7C3AED"),
    "ticket_assigned": ColorToken("ticket_assigned", "#0369A1"),
    "ticket_in_progress": ColorToken("ticket_in_progress", "#B45309"),
    "ticket_blocked": ColorToken("ticket_blocked", "#B91C1C"),
    "ticket_pending_closure": ColorToken("ticket_pending_closure", "#92400E"),
    "ticket_resolved": ColorToken("ticket_resolved", "#166534"),
    "evidence_selected": ColorToken("evidence_selected", "#1D4ED8"),
    "evidence_unavailable": ColorToken("evidence_unavailable", "#64748B"),
    "notification_unread": ColorToken("notification_unread", "#B91C1C"),
}

COLORS: Mapping[str, ColorToken] = MappingProxyType(_COLOR_VALUES)

# Each entry names the semantic treatment of a component state.  Consumers
# should resolve these names through COLORS instead of adding local shades.
INTERACTION_MATRIX: Mapping[str, Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "button_primary": MappingProxyType(
            {
                "normal": MappingProxyType({"background": "primary", "text": "text_on_primary", "icon": "text_on_primary", "border": "primary"}),
                "hover": MappingProxyType({"background": "primary_dark", "text": "text_on_dark", "icon": "text_on_dark", "border": "primary_dark"}),
                "pressed": MappingProxyType({"background": "primary_dark", "text": "text_on_dark", "icon": "text_on_dark", "border": "primary_dark"}),
                "focus": MappingProxyType({"background": "primary", "text": "text_on_primary", "icon": "text_on_primary", "border": "focus"}),
                "disabled": MappingProxyType({"background": "disabled_background", "text": "disabled_text", "icon": "disabled_text", "border": "border_subtle"}),
            }
        ),
        "text_field": MappingProxyType(
            {
                "normal": MappingProxyType({"background": "field_background", "text": "text_primary", "icon": "text_secondary", "border": "border_subtle"}),
                "focus": MappingProxyType({"background": "field_background", "text": "text_primary", "icon": "focus", "border": "focus"}),
                "invalid": MappingProxyType({"background": "error_background", "text": "text_primary", "icon": "error", "border": "error"}),
                "disabled": MappingProxyType({"background": "disabled_background", "text": "disabled_text", "icon": "disabled_text", "border": "border_subtle"}),
                "read_only": MappingProxyType({"background": "surface_subtle", "text": "text_primary", "icon": "text_secondary", "border": "border_subtle"}),
            }
        ),
        "message": MappingProxyType(
            {
                "success": MappingProxyType({"background": "success_background", "text": "success", "icon": "success", "border": "success"}),
                "error": MappingProxyType({"background": "error_background", "text": "error", "icon": "error", "border": "error"}),
                "warning": MappingProxyType({"background": "warning_background", "text": "warning", "icon": "warning", "border": "warning"}),
                "info": MappingProxyType({"background": "info_background", "text": "info", "icon": "info", "border": "info"}),
            }
        ),
    }
)

ALLOWED_TEXT_PAIRS = (
    ("text_primary", "background_general", 4.5),
    ("text_primary", "surface", 4.5),
    ("text_secondary", "surface", 4.5),
    ("text_on_primary", "primary", 4.5),
    ("text_on_dark", "primary_dark", 4.5),
    ("error", "error_background", 4.5),
    ("success", "success_background", 4.5),
    ("warning", "warning_background", 4.5),
    ("info", "info_background", 4.5),
)


def contrast_ratio(foreground: str | ColorToken, background: str | ColorToken) -> float:
    """Calculate the WCAG relative-luminance contrast ratio."""

    foreground_rgb = _rgb(foreground)
    background_rgb = _rgb(background)
    foreground_luminance = _luminance(foreground_rgb)
    background_luminance = _luminance(background_rgb)
    lighter, darker = max(foreground_luminance, background_luminance), min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def validate_palette() -> tuple[tuple[str, str, float], ...]:
    """Return configured text pairs that do not meet their WCAG threshold."""

    return tuple(
        (foreground, background, contrast_ratio(COLORS[foreground], COLORS[background]))
        for foreground, background, minimum in ALLOWED_TEXT_PAIRS
        if contrast_ratio(COLORS[foreground], COLORS[background]) < minimum
    )


def _rgb(value: str | ColorToken) -> tuple[int, int, int]:
    hex_value = value.hex if isinstance(value, ColorToken) else value
    normalized = hex_value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError("colors must use six-digit hexadecimal values")
    try:
        return tuple(int(normalized[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("invalid hexadecimal color") from exc


def _luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for channel in rgb:
        normalized = channel / 255
        channels.append(normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


__all__ = [
    "ALLOWED_TEXT_PAIRS",
    "COLORS",
    "ColorToken",
    "INTERACTION_MATRIX",
    "contrast_ratio",
    "validate_palette",
]
