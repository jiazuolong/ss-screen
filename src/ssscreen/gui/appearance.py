"""Font preferences and font-aware geometry for the desktop workbench."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QWidget,
)

DEFAULT_FONT_SIZE = 10
MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 18
FONT_SETTINGS_KEY = "appearance/font_size_pt"
QT_MAX_SIZE = 16777215


def font_size(value: object) -> int:
    try:
        return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(value)))
    except (ValueError, TypeError, OverflowError):
        return DEFAULT_FONT_SIZE


def font_stylesheet(stylesheet: str, points: int) -> str:
    """Preserve heading hierarchy while replacing fixed pixel fonts with points."""
    return re.sub(
        r"font-size:\s*(\d+)px;",
        lambda match: f"font-size: {max(points - 1, int(match[1]) * points / 10):g}pt;",
        stylesheet,
    )


def adapt_font_layout(root: QWidget, points: int) -> None:
    """Scale text constraints from their original values, including late-created pages."""
    scale = points / DEFAULT_FONT_SIZE
    for form in root.findChildren(QFormLayout):
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    for widget in root.findChildren(QWidget):
        if isinstance(widget, QLabel) and widget.objectName() in {
            "pageDescription",
            "optionHelp",
            "breadcrumb",
            "commandName",
        }:
            widget.setWordWrap(True)

        if isinstance(widget, (QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QTableWidget)):
            baseline = widget.property("fontGeometryBaseline")
            if baseline is None:
                baseline = [widget.minimumHeight(), widget.maximumHeight(), widget.maximumWidth()]
                widget.setProperty("fontGeometryBaseline", baseline)
            minimum, maximum, width = baseline
            widget.setMinimumHeight(round(minimum * scale))
            if maximum < QT_MAX_SIZE:
                widget.setMaximumHeight(round(maximum * scale))
            if width < QT_MAX_SIZE:
                widget.setMaximumWidth(round(width * scale))

        if isinstance(widget, QTableWidget):
            row_height = max(28, widget.fontMetrics().height() + 14)
            header = widget.verticalHeader()
            header.setDefaultSectionSize(row_height)
            # ResizeToContents already follows font metrics. Forcing each row
            # repeatedly relays out the entire imported candidate table.
            if (
                widget.rowCount() < 100
                and header.sectionResizeMode(0) != QHeaderView.ResizeToContents
            ):
                for row in range(widget.rowCount()):
                    widget.setRowHeight(row, row_height)
            widths = widget.property("fontColumnBaseline")
            if widths is None:
                widths = [widget.columnWidth(column) for column in range(widget.columnCount())]
                widget.setProperty("fontColumnBaseline", widths)
            for column, width in enumerate(widths):
                widget.setColumnWidth(column, round(width * scale))
        widget.updateGeometry()
