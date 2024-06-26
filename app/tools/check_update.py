from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qfluentwidgets import InfoBar, InfoBarPosition

from ..card.messagebox_custom import MessageBoxUpdate
from tasks.base.fastest_mirror import FastestMirror
from module.config import cfg

from packaging.version import parse
from enum import Enum
import subprocess
import markdown
import requests
import re
import os


class UpdateStatus(Enum):
    """更新状态枚举类，用于指示更新检查的结果状态。"""
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


class UpdateThread(QThread):
    """负责后台检查更新的线程类。"""
    updateSignal = pyqtSignal(UpdateStatus)

    def __init__(self, timeout, flag):
        super().__init__()
        self.timeout = timeout  # 超时时间
        self.flag = flag  # 标志位，用于控制是否执行更新检查

    def remove_images_from_markdown(self, markdown_content):
        """从Markdown内容中移除图片标记。"""
        img_pattern = re.compile(r'!\[.*?\]\(.*?\)')
        return img_pattern.sub('', markdown_content)

    def fetch_latest_release_info(self):
        """获取最新的发布信息。"""
        response = requests.get(
            FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", not cfg.update_prerelease_enable),
            timeout=10,
            headers=cfg.useragent
        )
        response.raise_for_status()
        return response.json()[0] if cfg.update_prerelease_enable else response.json()

    def get_download_url_from_assets(self, assets):
        """从发布信息中获取下载URL。"""
        for asset in assets:
            if (cfg.update_full_enable and "full" in asset["browser_download_url"]) or \
               (not cfg.update_full_enable and "full" not in asset["browser_download_url"]):
                return asset["browser_download_url"]
        return None

    def run(self):
        """执行更新检查逻辑。"""
        try:
            if self.flag and not cfg.check_update:
                return

            data = self.fetch_latest_release_info()
            version = data["tag_name"]
            content = self.remove_images_from_markdown(data["body"])
            assert_url = self.get_download_url_from_assets(data["assets"])

            if assert_url is None:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
                return

            if parse(version.lstrip('v')) > parse(cfg.version.lstrip('v')):
                self.title = f"发现新版本：{cfg.version} ——> {version}\n更新日志 |･ω･)"
                self.content = "<style>a {color: #f18cb9; font-weight: bold;}</style>" + markdown.markdown(content)
                self.assert_url = assert_url
                self.updateSignal.emit(UpdateStatus.UPDATE_AVAILABLE)
            else:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
        except Exception as e:
            print(e)
            self.updateSignal.emit(UpdateStatus.FAILURE)


def checkUpdate(self, timeout=5, flag=False):
    """检查更新，并根据更新状态显示不同的信息或执行更新操作。"""
    def handle_update(status):
        if status == UpdateStatus.UPDATE_AVAILABLE:
            # 显示更新对话框
            message_box = MessageBoxUpdate(
                self.update_thread.title,
                self.update_thread.content,
                self.window()
            )
            if message_box.exec():
                # 执行更新操作
                source_file = os.path.abspath("./Update.exe")
                assert_url = FastestMirror.get_github_mirror(self.update_thread.assert_url)
                subprocess.Popen([source_file, assert_url], creationflags=subprocess.DETACHED_PROCESS)
        elif status == UpdateStatus.SUCCESS:
            # 显示当前为最新版本的信息
            InfoBar.success(
                title=self.tr('当前是最新版本(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        else:
            # 显示检查更新失败的信息
            InfoBar.warning(
                title=self.tr('检测更新失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    self.update_thread = UpdateThread(timeout, flag)
    self.update_thread.updateSignal.connect(handle_update)
    self.update_thread.start()
