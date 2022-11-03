# epub-reader
用PySide2编写的epub阅读器

## 常规使用
文件输入框内输入epub文件路径然后回车，或者直接用鼠标把epub文件拖到窗口内（包括文件输入框），就能打开文件了。

## 快捷键
- <kbd>Ctrl</kbd> + <kbd>S</kbd>: 切换风格 (S: Style)
- <kbd>Ctrl</kbd> + <kbd>PgUp</kbd>: 上一章
- <kbd>Ctrl</kbd> + <kbd>PgDn</kbd>: 下一章

## 特殊功能：AI朗读
> 开发当时正好流行二次元角色AI语音合成，我觉得很好玩就加了，局限挺大的，效果也比较一般，如要使用请先看看下面的说明。

对文字按下右键，在菜单中选择 "从这句开始朗读" 触发，朗读同时会自动调整滚动条。

如果想在本地进行语音合成，需要下载 [MoeGoe](https://github.com/CjangCjengh/MoeGoe) 并配置一些参数（在 `config.json` 里）。

或者也可以在 `config.json` 里配置在线语音合成。

本地合成是通过 `asyncio.subprocess` 以子程序的方式调用 [MoeGoe](https://github.com/CjangCjengh/MoeGoe) ，难免会不太稳定，所以首先说一下我用的是 MoeGeo2 ，模型用的是 [这个](https://github.com/CjangCjengh/TTSModels#nene--nanami--rong--tang) ，使用其他MoeGoe版本或其他模型不一定还能起效，如果使用时报错了，请修改 `speak.py` 中的 `_generate_wav` 方法。

在线合成本质上就是爬虫，比本地合成稳定，但问题是我没有测试的环境……代码不一定无错，请自行权衡。

### 注意
- 如果遇到了音频卡顿的情况，安装 `K-Lite` 解码器可能会好很多（至少我是这样）。
- [MoeGoe](https://github.com/CjangCjengh/MoeGoe) 输入文本需要用语言标签做标注（如 `[ZH]中文[ZH][EN]English[EN]` 这样，目前我这里只支持中文和英文的标签），我在 `utils.py` 里实现了**两种处理方法**：（具体可以看这些函数的注释）
  - `clean_text_simple` : 如果模型不支持英文就用这个，会把英文也放入中文标签中，因此英文单词会被逐字母朗读。
  - `clean_text` : 把中文和英文分开，各自放各自的标签里。理论上模型如果支持英文可以用这个，但我还没测试过……
