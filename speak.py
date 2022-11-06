import asyncio
import aiohttp
from hashlib import md5
import json
import math
import os
from time import time
from typing import List, Optional

from PySide2.QtWidgets import QLabel
from PySide2.QtCore import QThread, Signal

from utils import MediaPlayer, clean_text_simple, singleton


@singleton
class SpeakerData:
    def __init__(self) -> None:
        with open('config.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        self.local: bool = data['method']['name'] == 'local'
        self.online: bool = data['method']['name'] == 'online'
        self.moegoe: str = data['local']['MoeGoe']
        self.model: str = data['local']['model']
        self.config: str = data['local']['config']
        self.speaker: int = data['local']['speaker']
        self._url: str = data['online']['url']
        del data

    def __str__(self) -> str:
        if self.local:
            return f'SpeakerData(local, moegoe={self.moegoe}, model={self.model}, config={self.config})'
        elif self.online:
            return f'SpeakerData(online, url={self._url})'
        else:
            raise ValueError('method not in (local, online)')

    def url(self, text: str) -> str:
        return eval(f'f"{self._url}"')


@singleton
class Speaker(QThread):
    scroll_signal = Signal(int)

    def __init__(self):
        super().__init__()
        self.data = SpeakerData()
        self.texts: List[QLabel] = []
        self.text_id = 0
        self._looping = True
        self.tmp_path = os.path.abspath('tmp')
        self.player = MediaPlayer()
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self.err_msg = '与MoeGoe的交互出现了不认识的输出，请确认MoeGoe版本或是否报错'

    def generate_output_path(self, text: str):
        file_name = md5((str(time()) + text).encode()).hexdigest() + '.wav'
        return os.path.abspath(os.path.join(self.tmp_path, file_name))

    def stop(self):
        self._looping = False

    def stopped(self) -> bool:
        return not self._looping

    def init(self, text_start_id: int, texts: List[QLabel]):
        self.text_id = text_start_id
        self.texts = texts
        self._looping = True

    async def _download_wav(self, text: str):
        """从接口下载音频, 播放"""
        url = self.data.url(text)
        path = self.generate_output_path(text)
        if os.path.exists(self.tmp_path):
            for name in os.listdir(self.tmp_path):
                name = os.path.join(self.tmp_path, name)
                if os.path.isfile(name) and name.endswith('.wav'):
                    os.remove(name)
        else:
            os.mkdir(self.tmp_path)
        async with aiohttp.ClientSession() as session:
            res = await session.get(url)
            content = await res.read()
        with open(path, 'wb') as file:
            file.write(content)
        return await self._play(path)

    async def _generate_wav(self, text: str):
        """本地语音生成, 播放"""
        # prepare
        path = self.generate_output_path(text)
        if os.path.exists(self.tmp_path):
            for name in os.listdir(self.tmp_path):
                name = os.path.join(self.tmp_path, name)
                if os.path.isfile(name) and name.endswith('.wav'):
                    try:
                        os.remove(name)
                    except:
                        pass  # 有时候会出现文件被占用的情况，无所谓，下次会删
        else:
            os.mkdir(self.tmp_path)
        text = clean_text_simple(text)
        # MoeGoe相关
        if self.process is None:  # 初始化, 输入model和config
            print('正在创建与MoeGoe交互的子程序...')
            self.process = await asyncio.subprocess.create_subprocess_shell(
                f'"{SpeakerData().moegoe}"',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            print('开始初始化MoeGoe...')
            # Path of a VITS model: {model_path}
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'Path of a VITS model: ':
                raise RuntimeError(self.err_msg)
            print(self.data.model)
            self.process.stdin.write(f'{self.data.model}\n'.encode())
            await self.process.stdin.drain()
            # Path of a config file: {config_path}
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'Path of a config file: ':
                raise RuntimeError(self.err_msg)
            print(self.data.config)
            self.process.stdin.write(f'{self.data.config}\n'.encode())
            await self.process.stdin.drain()
            print('MoeGoe配置完成')
        else:  # Continue? (y/n): y
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'Continue? (y/n): ':
                raise RuntimeError(self.err_msg)
            print('y')
            self.process.stdin.write(f'y\n'.encode())
            await self.process.stdin.drain()
        if self.process is not None:  # 和MoeGoe的交互
            # TTS or VC? (t/v):t
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'TTS or VC? (t/v):':
                raise RuntimeError(self.err_msg)
            print('t')
            self.process.stdin.write(f't\n'.encode())
            await self.process.stdin.drain()
            # Text to read: {text}
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'Text to read: ':
                raise RuntimeError(self.err_msg)
            print(f'{text}')
            self.process.stdin.write(f'{text}\n'.encode('gbk', errors='ignore'))  # 唯一一个可能出现奇怪字符的地方，errors防止gbk不支持的字符导致报错
            await self.process.stdin.drain()
            # ID      Speaker\n0       綾地寧々\n...\nSpeaker ID: 2(这里麻烦的是speaker是分好几行的，长度也不确定)
            target = b'Speaker ID: '
            lst: List[bytes] = []
            cnt = 0
            while True:  # 只能1个1个探索了
                s = await self.process.stdout.read(1)
                cnt += 1
                lst.append(s)
                if b''.join(lst[-len(target):]) == target:
                    break
                if cnt > (4 << 20):  # 读了4M个字节了还没找到，总不能真就一直这么找下去吧，而且这也说明肯定出问题了啊
                    raise RuntimeError(self.err_msg)
            print(b''.join(lst).decode('gbk'), end='')
            del lst, target, cnt
            print(f'{self.data.speaker}')
            self.process.stdin.write(f'{self.data.speaker}\n'.encode())
            await self.process.stdin.drain()
            # Path to save: {output_path}
            s = await self.process.stdout.read(128)
            print(s.decode('gbk'), end='')
            if s != b'Path to save: ':
                raise RuntimeError(self.err_msg)
            print(f'{path}')
            self.process.stdin.write(f'{path}\n'.encode())
            await self.process.stdin.drain()
            # Successfully saved! (这里有回车,而且考虑到Continue在前面接收了,所以这里用readline)
            s = await self.process.stdout.readline()
            print(s.decode('gbk'), end='')
            if s.strip() != b'Successfully saved!':
                raise RuntimeError(self.err_msg)
        return await self._play(path)

    async def _play(self, path: str):
        """播放"""
        while self.player.state() == MediaPlayer.PlayingState and self._looping:
            await asyncio.sleep(0.1)  # 等待上一个播放结束
        if not self._looping:
            return
        self.player.setMedia(path)
        self.player.play()

    async def _main(self):
        while self._looping:
            # 移动
            text = self.texts[self.text_id]
            last_text = self.texts[self.text_id - 1 if self.text_id > 0 else 0]
            if last_text.y() >= 70:
                self.scroll_signal.emit(last_text.y() - 70)
            del last_text
            # 语音合成
            if text.text():
                if self.data.online:
                    await self._download_wav(text.text())
                elif self.data.local:
                    await self._generate_wav(text.text())
                else:
                    raise RuntimeError('未知的语音合成方式')
            # 看完后退出
            self.text_id += 1
            if self.text_id >= len(self.texts):
                break
        self.stop()

    def run(self):
        if self.event_loop is None:
            self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self._main())
