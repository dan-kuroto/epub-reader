import os
from string import printable, whitespace
from typing import List, Type, Optional, Generator

from PySide2.QtWidgets import QWidget, QScrollArea, QFormLayout
from PySide2.QtGui import QDragEnterEvent, QDropEvent
from PySide2.QtCore import QUrl
from PySide2.QtMultimedia import QMediaPlayer, QMediaContent


whitespace_set = set(whitespace)
printable_set = set(printable)
punctuation_set = set(',.:!?[]"\'，。：！？—「」『』《》【】〖〗〝〞‘’“”')


def singleton(cls: Type):
    """
    单例模式
    - 低级实现，会在高并发创建请求时出错，但这个项目里没这种情景所以无所谓
    - 会导致被装饰的类变得不能直接用类名来继承
    - 必须把有默认值的参数放在后面
    - 从第二次调用开始就不再需要给参数（无效了，也很难再给），最好所有的参数都有默认值
    """
    _instance = {}
    def _singleton(*args, **kwargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kwargs)
        return _instance[cls]
    return _singleton


def clean_text_simple(text: str) -> str:
    """
    为了给MoeGoe使用，需要对文本进行简单处理，即用语言标签包裹起来。\n
    由于我使用的模型似乎不支持英文标签(会直接跳过不读？反而中文里混字母可以)，故这里的策略是只有一个中文标签，将所有英文字母后面加上逗号(字母紧贴着的话发音会连起来,空格间隔太短)，而对换行等符号的处理是一律转成句号。
    - e.g. '假面骑士的末日到了' => '[ZH]假面骑士的末日到了[ZH]'
    - e.g. '你是世界首例感染Bugster病毒的男人啊！' => '[ZH]你是世界首例感染B，u，g，s，t，e，r，病毒的男人啊！[ZH]'
    """
    text = text.strip()
    lst: List[str] = ['[ZH]']
    for ch in text:
        if ch in whitespace_set:
            lst.append('。')
        else:
            lst.append(ch)
            if 'a' <= ch <= 'z' or 'A' <= ch <= 'Z':
                lst.append('，')
    lst.append('[ZH]')
    return ''.join(lst)


def clean_text(text: str) -> str:
    """
    为了给MoeGoe使用，需要对文本进行简单处理，即用语言标签包裹起来。\n
    目前只支持中文(ZH)和英文(EN)，对换行等符号的处理是一律转成句号。
    - e.g. '假面骑士的末日到了' => '[ZH]假面骑士的末日到了[ZH]'
    - e.g. '你是世界首例感染Bugster病毒的男人啊！' => '[ZH]你是世界首例感染[ZH][EN]Bugster[EN][ZH]病毒的男人啊！[ZH]'
    """
    text = text.strip()
    lst: List[str] = []
    en_mode = False
    for ch in text:
        if not en_mode:
            if 'a' <= ch <= 'z' or 'A' <= ch <= 'Z':  # 进入英文模式
                en_mode = True
                if lst:
                    lst.append('[ZH]')  # 中文结束
                lst.append('[EN]')  # 英文开始
                if ch in whitespace_set:
                    ch = '. '
                lst.append(ch)
            else:  # 保持中文模式
                if not lst:
                    lst.append('[ZH]')  # 中文开始
                if ch in whitespace_set:
                    ch = '。'
                lst.append(ch)
        else:
            if ch not in printable_set:  # 进入中文模式
                en_mode = False
                lst.append('[EN]')  # 英文结束
                lst.append('[ZH]')  # 中文开始
                if ch in whitespace_set:
                    ch = '。'
                lst.append(ch)
            else:  # 保持英文模式
                if ch != ' ' and ch in whitespace_set:
                    ch = '. '
                lst.append(ch)
    if lst:
        lst.append('[EN]' if en_mode else '[ZH]')
    return ''.join(lst)


def split_long_text(text: str, max_len: int = 25) -> Generator[str, None, None]:
    """
    若文本长度超过最大长度，则从这里开始往后寻找最近的标点符号(比如句号)，进行分割
    """
    length = len(text)
    if length <= max_len:  # 不需要分割
        yield text
    else:
        start = 0
        while start < length:
            end = start + max_len
            if end >= length:  # 分完了
                yield text[start:]
                break
            else:  # 还没分完
                while end < length and text[end - 1] not in punctuation_set:
                    end += 1  # 向后找最近的标点符号, 但是不能超过总长度
                yield text[start: end]  # 分割
                start = end


class ScrollArea(QScrollArea):
    """滚动区域"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._widget = QWidget()
        self._layout = QFormLayout(self._widget)  # 用QVBoxLayout内容不够会拉开距离/居中
        self._widget.setLayout(self._layout)
        self.setWidget(self._widget)
        self.setWidgetResizable(True)  # 否则内容不够的时候不会填满

    def addWidget(self, widget: QWidget):
        """添加一行新的部件"""
        self._layout.addWidget(widget)

    def clearWidgets(self):
        """清空所有部件"""
        layout = self.widget().layout()
        for idx in range(layout.count() - 1, -1, -1):  # 倒着删除
            item = layout.itemAt(idx)
            if item.widget():
                item.widget().deleteLater()
            layout.removeItem(item)


class MediaPlayer(QMediaPlayer):
    def setMedia(self, path: str) -> None:
        """很神奇,如果文件名相同的话它似乎就不会重新加载,所以一定要随机名称"""
        return super().setMedia(QMediaContent(QUrl.fromLocalFile(path)))


class FileDragable(QWidget):
    """可拖入文件的QWidget"""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        event.acceptProposedAction()  # 不这样dropEvent就无法触发

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            url: QUrl
            path = url.toLocalFile()
            if self.check_dragged_file_path(path):
                self.after_file_dragged(path)
                return  # 只管一个

    def check_dragged_file_path(self, path: str) -> bool:
        """检查拖入文件路径"""
        return os.path.isfile(path)

    def after_file_dragged(self, path: str):
        """文件拖入后执行的操作"""
        print(path)


if __name__ == '__main__':
    while True:
        print(clean_text_simple(input('>> ')))
