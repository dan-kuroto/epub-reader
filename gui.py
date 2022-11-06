import os
import sys
from typing import List, Optional

from PySide2.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QLineEdit, QAction, QMenu, QFileDialog
from PySide2.QtGui import QFont, QPixmap, QImage, QKeyEvent, QContextMenuEvent, QCloseEvent, QResizeEvent
from PySide2.QtCore import Qt, QTimer
from qtmodern.styles import dark as dark_style, light as light_style

import epub
from utils import FileDragable, singleton, ScrollArea
from speak import Speaker


@singleton
class Data:
    """单例的数据类"""
    def __init__(self):
        self._styles = [light_style, dark_style]
        self._style_id = 0
        self._path = ''
        self._nav_id = 0

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, path: str):
        self._path = path

        main = MainWindow()
        main.epub = epub.Epub(path)
        menu = Menu()
        menu.clearWidgets()
        for nav in main.epub.navs:
            menu.addWidget(MenuButton(nav))
        self.nav_id = 0

    @property
    def nav_id(self) -> int:
        return self._nav_id

    @nav_id.setter
    def nav_id(self, nav_id: int):
        if TextContextMenu().speak_loaded:
            Speaker().stop()

        main = MainWindow()
        menu = Menu()
        content = EpubContent()

        if not main.epub or not 0 <= nav_id < len(main.epub.navs):
            return

        menu_btns = menu.get_btns()
        if self.nav_id < len(menu_btns):
            menu_btns[self.nav_id].setEnabled(True)
        self._nav_id = nav_id
        menu_btns[self.nav_id].setEnabled(False)

        max_width = content.width() - 50
        content.clearWidgets()
        for item in main.epub.get_content(nav_id):
            if type(item) is epub.Image:
                label = None
                try:
                    label = Image(item, max_width)
                except KeyError as ke:
                    label = Text(epub.Text(repr(ke)))
            elif type(item) is epub.Text:
                label = Text(item)
            else:  # 只可能是在`get_content`里自己加了新的类型，然而却没在这里更新相关的处理，所以是抛出异常
                raise TypeError(f'尚未支持的类型 {type(item)}')
            content.addWidget(label)

        main.setWindowTitle(f'{main.epub.navs[nav_id].text} - {os.path.basename(self.path)[:-5]} - EpubReader')

    @property
    def styles(self):
        return self._styles

    @property
    def style_id(self) -> int:
        return self._style_id

    @style_id.setter
    def style_id(self, style_id: int):
        self._style_id = style_id % len(self.styles)
        self.styles[self.style_id](QApplication.instance())

    def __str__(self) -> str:
        str_max_length = 10

        path = f'path="{self.path}"' if len(self.path) <= str_max_length else f'path="{self.path[:str_max_length]}..."'

        return f'Data({path})'


@singleton
class ImageContextMenu(QMenu):
    def __init__(self):
        super().__init__()
        self.image_id = 0
        self.save_action = QAction('保存图片')
        self.save_action.triggered.connect(self.save_image)
        self.addAction(self.save_action)

    def save_image(self):
        src = EpubContent().images[self.image_id].src
        path, _ = QFileDialog.getSaveFileName(None, '保存图片', os.path.basename(src), f'图片文件 (*{os.path.splitext(src)[-1]})')
        if not path:
            return
        with open(path, 'wb') as f:
            f.write(MainWindow().epub.read(src))


@singleton
class TextContextMenu(QMenu):
    def __init__(self):
        super().__init__()
        self.text_id = 0
        self.speak_loaded = False  # 因为这里的Speaker类是打算尽量不创建的
        self.speak_start_action = QAction('从这句开始朗读')
        self.speak_start_action.triggered.connect(self.speak_start)
        self.speak_stop_action = QAction('停止朗读')
        self.speak_stop_action.triggered.connect(self.speak_stop)
        self.addAction(self.speak_start_action)
        self.addAction(self.speak_stop_action)

    def speak_start(self):
        speaker = Speaker()

        if not self.speak_loaded:
            speaker.scroll_signal.connect(lambda height: EpubContent().verticalScrollBar().setValue(height))
        self.speak_loaded = True

        speaker.init(self.text_id, EpubContent().texts)
        speaker.start()

    def speak_stop(self):
        if self.speak_loaded:
            Speaker().stop()

    def show(self) -> None:
        if self.speak_loaded:
            if Speaker().stopped():
                self.speak_start_action.setEnabled(True)
                self.speak_stop_action.setEnabled(False)
            else:
                self.speak_start_action.setEnabled(False)
                self.speak_stop_action.setEnabled(True)
        else:
            self.speak_stop_action.setEnabled(False)
        return super().show()


class Image(QLabel):
    def __init__(self, image: epub.Image, max_width: int):
        super().__init__()
        self.idx = 0
        self.src = image.src
        self.init_image(max_width)

    def init_image(self, max_width: int):
        """初始化图片，主要是为了以后能随着窗口大小的变化而缩放图片"""
        main = MainWindow()
        pixmap = QPixmap.fromImage(QImage.fromData(main.epub.read(self.src)))
        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width, Qt.SmoothTransformation)
        self.setPixmap(pixmap)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = ImageContextMenu()
        menu.image_id = self.idx
        menu.move(event.globalPos())
        menu.show()


class Text(QLabel):
    def __init__(self, text: epub.Text) -> None:
        super().__init__(text.text)
        self.idx = 0
        self.setWordWrap(True)

        font = self.font()
        if text.header_level != epub.Text.HeaderLevel.none:
            font.setPointSize(14 + 2 * (4 - text.header_level))
        if text.strong:
            font.setBold(True)
        self.setFont(font)
        del font
        if text.align == epub.Text.Align.center:
            self.setAlignment(Qt.AlignCenter)
        elif text.align == epub.Text.Align.right:
            self.setAlignment(Qt.AlignRight)
        if text.color:
            self.setStyleSheet(f'color: {text.color};')

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = TextContextMenu()
        menu.text_id = self.idx
        menu.move(event.globalPos())
        menu.show()


@singleton
class EpubContent(ScrollArea):
    """放置epub文件内容的控件"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.texts: List[Text] = []
        self.images: List[Image] = []
        self._resize_finished = False

    def addWidget(self, widget: QLabel):
        if type(widget) is Text:
            widget.idx = len(self.texts)
            self.texts.append(widget)
        elif type(widget) is Image:
            widget.idx = len(self.images)
            self.images.append(widget)
        return super().addWidget(widget)

    def clearWidgets(self):
        self.texts = []
        self.images = []
        return super().clearWidgets()

    def resizeEvent(self, event: QResizeEvent) -> None:
        if not self._resize_finished:
            self._resize_finished = True
            max_width = event.size().width() - 50
            for image in self.images:
                image.init_image(max_width)
            for text in self.texts:
                text.setFixedWidth(max_width)  # 裁剪掉无法换行的长串英文字符，反正通常都是一个超长的破折号或者等号或者链接之类的
            QTimer.singleShot(100, lambda: setattr(self, '_resize_finished', False))  # 为了防止resizeEvent被多次触发，这里延迟一下
        return super().resizeEvent(event)


class MenuButton(QPushButton):
    def __init__(self, nav: epub.Nav) -> None:
        super().__init__(nav.text)
        self.nav_id = nav.index
        self.setStyleSheet('text-align: left; padding-left: 10px')
        self.clicked.connect(self.nav_shift)

    def nav_shift(self):
        Data().nav_id = self.nav_id


@singleton
class Menu(ScrollArea):
    """目录"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)
        self.btns: List[MenuButton] = []

    def addWidget(self, widget: MenuButton):
        self.btns.append(widget)
        return super().addWidget(widget)

    def clearWidgets(self):
        self.btns = []
        return super().clearWidgets()

    def get_btns(self) -> List[MenuButton]:
        """获取所有按钮"""
        return self.btns


@singleton
class FileInput(QLineEdit):
    """选择文件"""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.returnPressed.connect(self.enter_handler)

    def enter_handler(self):
        path = self.text()
        if os.path.exists(path) and os.path.isfile(path) and path.lower().endswith('.epub'):
            Data().path = path
        else:
            self.setText(Data().path)


@singleton
class MainWindow(FileDragable):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EpubReader')
        self.resize(700, 500)
        self.setMinimumSize(300, 300)

        self.epub: Optional[epub.Epub] = None

        self.file_input = FileInput(self)
        self.file_input.hide()
        self.menu = Menu(self)
        self.epub_content = EpubContent(self)

        layout = QVBoxLayout()
        layout.addWidget(self.file_input)
        body = QSplitter()
        body.addWidget(self.menu)
        body.addWidget(self.epub_content)
        body.setSizes([200, 400])
        layout.addWidget(body)
        self.setLayout(layout)

    def check_dragged_file_path(self, path: str) -> bool:
        return os.path.isfile(path) and path.lower().endswith('.epub')

    def after_file_dragged(self, path: str):
        self.file_input.setText(path)
        Data().path = path

    def keyPressEvent(self, event: QKeyEvent) -> None:
        ctrl: bool = event.modifiers() & Qt.ControlModifier != 0
        key = event.key()
        if ctrl and key == Qt.Key_S:
            Data().style_id += 1
        elif ctrl and key == Qt.Key_I:
            self.file_input.setVisible(not self.file_input.isVisible())
        elif ctrl and key == Qt.Key_N:
            self.menu.setVisible(not self.menu.isVisible())
        elif ctrl and key == Qt.Key_PageUp:
            Data().nav_id -= 1
        elif ctrl and key == Qt.Key_PageDown:
            Data().nav_id += 1

    def closeEvent(self, event: QCloseEvent) -> None:
        if TextContextMenu().speak_loaded:
            speaker = Speaker()
            speaker.stop()
            if speaker.process:
                speaker.process.kill()


if __name__ == '__main__':
    os.chdir(os.path.split(os.path.realpath(__file__))[0])

    app = QApplication(sys.argv)
    Data().style_id = 0
    app.setFont(QFont('Microsoft Yahei', 14))
    MainWindow().show()
    sys.exit(app.exec_())
