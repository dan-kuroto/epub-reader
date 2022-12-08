# epub-reader
用PySide2编写的epub阅读器 （我主要用这玩意看轻小说）

## 常规使用
- **打开文件**：文件输入框内输入epub文件路径然后回车，或者直接用鼠标把epub文件拖到窗口内（包括文件输入框）
- **保存图片**：右键图片，选择保存
- **其他格式**：除epub外也支持了txt文件，但目前还有很多问题，比如仅支持utf-8编码，还有对txt采取一口气加载整本书的逻辑导致花费时间较长，因此并不建议使用

## 快捷键
- <kbd>Ctrl</kbd> + <kbd>S</kbd>: 切换风格 (S: Style)
- <kbd>Ctrl</kbd> + <kbd>I</kbd>: 显示/隐藏文件输入框 (I: Input)
- <kbd>Ctrl</kbd> + <kbd>N</kbd>: 显示/隐藏侧边导航栏 (N: Navigator)
- <kbd>Ctrl</kbd> + <kbd>PgUp</kbd>: 上一章
- <kbd>Ctrl</kbd> + <kbd>PgDn</kbd>: 下一章

## 特殊功能：AI朗读
> 开发当时正好流行二次元角色AI语音合成，我觉得很好玩就加了，不过局限挺大的，如要使用请先看看下面的说明。

对文字按下右键，在菜单中选择 "从这句开始朗读" 触发，朗读同时会自动调整滚动条。

如果想在本地进行语音合成，需要下载 [MoeGoe](https://github.com/CjangCjengh/MoeGoe) 并配置一些参数（在 `config.json` 里）。

或者也可以在 `config.json` 里配置在线语音合成。

本地合成是通过 `asyncio.subprocess` 以子程序的方式调用 [MoeGoe](https://github.com/CjangCjengh/MoeGoe) ，难免会不太稳定，所以首先说一下我用的是 MoeGeo2 ，模型用的是 [这个](https://github.com/CjangCjengh/TTSModels#nene--nanami--rong--tang) ，使用其他MoeGoe版本或其他模型不一定还能起效，如果使用时报错了，请修改 `speak.py` 中的 `_generate_wav` 方法。

在线合成本质上就是爬虫，理论上应该比本地合成稳定，但问题是我没有测试的环境……不敢保证代码没有问题，还请自行权衡。

### 注意
- 如果遇到了音频卡顿的情况，安装 `K-Lite` 解码器可能会好很多（至少我是这样）。
- [MoeGoe](https://github.com/CjangCjengh/MoeGoe) 输入文本需要用语言标签做标注（如 `[ZH]中文[ZH][EN]English[EN]` 这样，目前我这里只支持中文和英文的标签），我在 `utils.py` 里实现了**两种处理方法**：（具体可以看这些函数的注释）
  - `clean_text_simple` : 如果模型不支持英文就用这个，会把英文也放入中文标签中，因此英文单词会被逐字母朗读。
  - `clean_text` : 把中文和英文分开，各自放各自的标签里。理论上模型如果支持英文可以用这个，但我手上没有支持英文的模型所以还没测试过……
