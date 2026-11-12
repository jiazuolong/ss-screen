"""Central icon helpers for the SS-Screen desktop GUI."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle


SP = QStyle.StandardPixmap


# 通用操作图标
_ICON_SPECS = {
    "new_project": ("folder-new", SP.SP_FileDialogNewFolder),
    "open_project": ("document-open", SP.SP_DialogOpenButton),
    "open_project_file": ("document-import", SP.SP_FileIcon),
    "save_project_file": ("document-save", SP.SP_DialogSaveButton),
    "initialize": ("view-refresh", SP.SP_BrowserReload),
    "open_directory": ("folder-open", SP.SP_DirOpenIcon),
    "remove": ("edit-delete", SP.SP_TrashIcon),
    "stop": ("media-playback-stop", SP.SP_MediaStop),

    "run": ("media-playback-start", SP.SP_MediaPlay),
    "refresh": ("view-refresh", SP.SP_BrowserReload),
    "reset": ("edit-undo", SP.SP_DialogResetButton),
    "copy": ("edit-copy", SP.SP_FileIcon),

    "project": ("folder", SP.SP_DirIcon),
    "dashboard": ("view-dashboard", SP.SP_ComputerIcon),
    "group": ("folder", SP.SP_DirClosedIcon),
    "files": ("folder-documents", SP.SP_DirOpenIcon),
    "logs": ("text-x-generic", SP.SP_FileDialogDetailedView),
    "dataset": ("drive-harddisk", SP.SP_DriveHDIcon),
}


# 科研阶段（Stage 13 为GUI候选材料评价，不启动额外科研计算）
_STAGE_ICON_SPECS = {
    "01": ("drive-harddisk", SP.SP_DriveHDIcon),
    "02": ("applications-science", SP.SP_ComputerIcon),
    "03": ("view-filter", SP.SP_FileDialogDetailedView),
    "04": ("view-list-tree", SP.SP_FileDialogListView),
    "05": ("insert-link", SP.SP_FileLinkIcon),
    "06": ("office-chart-line", SP.SP_FileDialogInfoView),
    "07": ("applications-science", SP.SP_ComputerIcon),
    "08": ("system-run", SP.SP_MediaPlay),
    "09": ("emblem-default", SP.SP_DialogApplyButton),
    "10": ("audio-x-generic", SP.SP_MediaPlay),
    "11": ("office-chart-pie", SP.SP_FileDialogDetailedView),
    "12": ("document-preview", SP.SP_FileDialogInfoView),
    "13": ("office-chart-line", SP.SP_FileDialogInfoView),
}


def _icon(theme_name: str, fallback: QStyle.StandardPixmap) -> QIcon:
    """Use desktop theme icon when available, otherwise Qt built-in icon."""
    themed = QIcon.fromTheme(theme_name)
    if not themed.isNull():
        return themed

    return QApplication.style().standardIcon(fallback)


def app_icon(name: str) -> QIcon:
    """Return a common SS-Screen GUI icon."""
    theme_name, fallback = _ICON_SPECS[name]
    return _icon(theme_name, fallback)


def stage_icon(stage_id: str) -> QIcon:
    """Return an icon for one SS-Screen workflow stage."""
    theme_name, fallback = _STAGE_ICON_SPECS.get(
        stage_id,
        ("text-x-generic", SP.SP_FileIcon),
    )
    return _icon(theme_name, fallback)
