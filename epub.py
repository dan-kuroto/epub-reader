import os
from typing import Dict, List, Union
from urllib.parse import unquote
from zipfile import ZipFile

from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString, Comment, Stylesheet
import xmltodict


class Nav:
    def __init__(self, tag: Tag, index: int) -> None:
        """tag: bs4.element.Tag"""
        self.index = index
        self.text: str = tag.find('navlabel').text.strip()
        self.src: str = tag.find('content').get('src')

    def __str__(self) -> str:
        return f'[{self.text}]({self.src})'


class Text:

    class HeaderLevel:
        none = 0x0
        h1 = 0x1
        h2 = 0x2
        h3 = 0x3

    class Align:
        left = 0x0
        center = 0x1
        right = 0x2

    def __init__(self, text: str) -> None:
        self.text = text
        self.header_level = Text.HeaderLevel.none
        self.strong = False
        self.align = Text.Align.left

    def set_align(self, align: str):
        if not align:
            return
        if align == 'left':
            self.align = Text.Align.left
        elif align == 'right':
            self.align = Text.Align.right
        elif align == 'center':
            self.align = Text.Align.center

    def __str__(self) -> str:
        return f'Text(text={self.text})'


class Image:
    def __init__(self, src: str) -> None:
        self.src = src

    def __str__(self) -> str:
        return f'Image(src={self.src})'


class Epub:
    def __init__(self, path: str):
        # 步骤
        # 1. 打开 "META-INF/container.xml", 找到 ['container']['rootfiles']['rootfile']['@full-path'], 应该是个opf文件
        # 2. 打开 .opf 文件, 找 ['package']['manifest']['item'] 应该是个列表, 找到 id=ncx 的 href, 应该是个ncx
        with ZipFile(path) as zip:
            name_set = set(zip.namelist())
            opf_path = xmltodict.parse(zip.read('META-INF/container.xml').decode())['container']['rootfiles']['rootfile']['@full-path']
            root_path: str = os.path.dirname(opf_path)
            ncx_path = ''
            for item in xmltodict.parse(zip.read(opf_path).decode())['package']['manifest']['item']:
                if item['@id'] == 'ncx':
                    ncx_path = Epub.path_join(root_path, item['@href'])
                    break
            ncx = BeautifulSoup(zip.read(ncx_path).decode(), features='lxml').find('ncx')
        doc_title = ncx.find('doctitle')
        doc_author = ncx.find('docauthor')
        self.epub_path = path
        self.root_path = root_path
        self.name_set = name_set
        self.title: str = doc_title.text.strip() if doc_title is not None else ''
        self.author: str = doc_author.text.strip() if doc_author is not None else ''
        self.navs: List[Nav] = [Nav(navpoint, i) for i, navpoint in enumerate(ncx.find('navmap').find_all('navpoint'))]

    def get_content(self, idx: int) -> List[Union[Text, Image]]:
        """根据navs的编号获取对应的所有内容"""
        path = Epub.path_join(self.root_path, self.navs[idx].src)
        if path not in self.name_set:
            return [Text(f'错误: 在epub文件中找不到 {path} !')]
        with ZipFile(self.epub_path) as zip:
            body = BeautifulSoup(zip.read(path).decode(), features='lxml').find('body')
        return Epub._dfs(body, os.path.dirname(path))

    def read(self, src: str) -> bytes:
        """
        epub里的html/xhtml等文件中src往往使用相对路径, 但这已经在`get_content`中处理过了, 因此这里的src同样必须使用绝对路径
        """
        if src not in self.name_set:
            raise KeyError(f'在epub文件中找不到 {src} !')
        with ZipFile(self.epub_path) as zip:
            return zip.read(src)

    @staticmethod
    def _dfs(tag: Tag, root: str) -> List[Union[Text, Image]]:
        """
        针对html/xhtml等文件中的树状结构，用深搜的方式顺序得到所有文本或图片内容
        :param root: 就是所读文件在epub文件内所处的目录，因为图片的src是基于该文件的相对路径，所以需要提供
        """
        contents: List[Union[Text, Image]] = []
        without_children = True
        for child in tag.children:
            if type(child) is Tag:
                without_children = False
                contents.extend(Epub._dfs(child, root))
            elif type(child) in { NavigableString, Comment, Stylesheet }:
                pass
            else:
                contents.append(Text(f'不支持的类型 {type(child)} , 值为 {child}。'))
        if without_children:
            if tag.name == 'img':
                src = tag.get('src')
                if not src.lower().startswith('http'):  # 就NM离谱，怎么会有网络图片的啦
                    src = Epub.path_join(root, src)
                contents.append(Image(src))
            else:
                # Text
                text = Text(tag.text.strip())
                # check name
                if tag.name in { 'h1', 'h2', 'h3' }:
                    text.header_level = int(tag.name[-1])
                elif tag.name == 'b':
                    text.strong = True
                # check style
                style = Epub.parse_style(tag)
                text.set_align(style.get('text-align', ''))
                del style
                # apend
                if tag.name not in { 'style', 'link' }:
                    contents.append(text)
        return contents

    @staticmethod
    def parse_style(tag: Tag) -> Dict[str, str]:
        style = tag.get('style')
        if style is None:
            return {}
        elif type(style) is list:  # style的话应该不会是List[str]
            print('stype为List[str]')
            return {}
        elif type(style) is str:
            styles = {}
            for kv in [_.strip().split(':') for _ in style.strip().split(';')]:
                if len(kv) != 2:
                    continue
                styles[kv[0].strip()] = kv[1].strip()
            return styles
        else:  # 理论上不存在的情况
            return {}

    @staticmethod
    def path_join(root: str, name: str) -> str:
        """代替os.path的路径拼接, 因为正反斜杠等各种符号问题"""
        # 处理name里包含..
        if name.startswith('../'):
            name = name[3:]
            root = os.path.dirname(root)
        # 处理正反斜杠问题
        s = os.path.join(root, name).replace('\\', '/')
        # 处理含有#的url
        sharp_idx = s.find('#')
        if sharp_idx != -1:
            s = s[:sharp_idx]
        # 处理url里的%XX
        return unquote(s)

    def __str__(self) -> str:
        return f'Epub(root_path={self.root_path}, title={self.title}, author={self.author})'
