import win32gui,win32con,winerror,win32api,win32event
import sys, os



WINDOW_TITLE = "AI工作区"
isvisible = True   # 判断窗口是否可见

"工作路径设置及相关文件初始化"
work_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(work_dir, "userdata\\")
config_path = os.path.join(data_dir, "config.ini")
context1_path = os.path.join(data_dir, "context1.txt")



# 文件检验
if not os.path.exists(config_path):
    open(config_path, 'a',encoding="utf-8").close()
if not os.path.exists(context1_path):
    open(context1_path, 'a',encoding="utf-8").close()

def read_api_key():
    key=None
    with open(config_path, 'r', encoding="utf-8") as f:
        key=f.readline()
    return key

def write_api_key(key):
    with open(config_path, 'w', encoding="utf-8") as f:
        f.write(key)

global api_key
global context_path
api_key=read_api_key()
context_path=context1_path

def set_api_key(key):
    global api_key  # 必须声明全局变量，否则会创建一个局部变量随后销毁，无法修改全局api-key
    api_key=key

def main():
    mutex_name="Global\\MyAIWindowMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_err = win32api.GetLastError()
    if last_err == winerror.ERROR_ALREADY_EXISTS:
        # 已存在窗口
        hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
        sys.exit()
    else:
        # 窗口不存在
            
        from PySide6.QtWidgets import QApplication, QWidget, QGridLayout,QPushButton, QLineEdit, QTextEdit,QLabel
        from PySide6.QtCore import Qt, QThread, Signal, QObject
        from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon, PushButton, LineEdit, TextEdit, Theme, setTheme
        from openai import OpenAI

        class AIObject(QObject):
            text_signal = Signal(str)
            finished = Signal()
            err_signal = Signal()
            def __init__(self, api_key, text, context_path=None):
                super().__init__()
                self.client=OpenAI(api_key=api_key,
                              base_url="https://api.deepseek.com")
                self.text=text

            def interactive(self):
                try:
                    # 读取上下文
                    print("执行1")
                    context = None
                    temp_output=""
                    with open(context_path, 'r', encoding="utf-8") as c:
                        context = c.read()
                    with open(context_path, 'a', encoding="utf-8") as c:
                        c.write(f"用户：{self.text}\n")

                    print("执行2")
                    print(f"You are a helpful assistant.The following is the previous chat history. If there is none, please ignore it:{context}")
                    stream = self.client.chat.completions.create(
                        model="deepseek-v4-flash",                       # 指定模型
                        messages=[
                            {"role": "system", "content": f"You are a helpful assistant.The following is the previous chat history. If there is none, please ignore it:{context}"},
                            {"role": "user", "content": f"{self.text}"}
                        ],
                        stream=True,
                    )
                    print("执行3")
                    with open(context_path, 'a+', encoding="utf-8") as c:
                        c.write("助理：")
                        for chunk in stream:
                            if chunk.choices[0].delta.content is not None:
                                self.text_signal.emit(chunk.choices[0].delta.content)
                                # c.write(chunk.choices[0].delta.content)
                                temp_output += chunk.choices[0].delta.content
                        c.write(temp_output)
                        c.write('\n')
                except Exception as e:
                    # 通知主线程，出现错误
                    print(f"错误类型: {type(e).__name__}")
                    print(f"错误信息: {str(e)}")
                    print(f"完整错误: {repr(e)}")
                    self.err_signal.emit()
                self.finished.emit()


        class HomePage(QWidget):
            def __init__(self):
                "主页UI"
                super().__init__()
                self.setObjectName("homePage")
                layout = QGridLayout()
                self.inputbox = LineEdit()
                self.button1 = PushButton("发送")
                self.flush_button = PushButton("清除上下文")
                self.outputbox = TextEdit()
                self.outputbox.setReadOnly(True)
                layout.addWidget(self.inputbox,1,0,1,2)
                layout.addWidget(self.button1,2,1,1,1)
                layout.addWidget(self.flush_button,2,0,1,1)
                layout.addWidget(self.outputbox,0,0,1,2 )
                self.setLayout(layout)

                # 控件事件
                self.inputbox.returnPressed.connect(self.send_contect)
                self.button1.clicked.connect(self.send_contect)
                self.flush_button.clicked.connect(self.flush_context)

                # 线程相关
                self.thread = None
                self.worker = None

            def update_texteditor(self,delta):
                "用于更新输出内容"
                self.outputbox.insertPlainText(delta)
                # 自动滚动到底部
                cursor = self.outputbox.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.outputbox.setTextCursor(cursor)

            def after_finished(self):
                # 完成输出后恢复控件状态
                self.inputbox.setEnabled(True)
                self.button1.setEnabled(True)
                pass

            def send_contect(self):
                "获取用户输入的内容"
                if self.thread and self.thread.isRunning():
                    self.thread.quit()
                    self.thread.wait()
                    self.thread = None
                text=self.inputbox.text().strip()
                if not text:
                    return
                # 为输出框换行
                self.outputbox.insertPlainText('\n')
                self.outputbox.insertPlainText(f"用户：{text}\n\n助手：")
                cursor = self.outputbox.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.outputbox.setTextCursor(cursor)
                # 发送信息前检查API_KEY是否填写
                if api_key:
                    # 锁定控件，避免重复点击
                    self.inputbox.setEnabled(False)
                    self.button1.setEnabled(False)
                    self.flush_button.setEnabled(False)
                    # 启动工作线程
                    self.thread = QThread()
                    self.worker = AIObject(api_key=api_key, text=text)
                    self.worker.moveToThread(self.thread)
                    # 将函数连接到信号
                    self.worker.text_signal.connect(self.update_texteditor)
                    self.worker.finished.connect(self.after_finished)
                    self.worker.err_signal.connect(self.ai_error)
                    # 工作线程（即总交互方法）的连接和清理
                    self.thread.started.connect(self.worker.interactive)
                    self.thread.finished.connect(self.worker.deleteLater)
                    self.thread.finished.connect(self.thread.deleteLater)
                
                    self.thread.start()
                else:
                    self.outputbox.clear()
                    self.outputbox.insertPlainText("未填写api，请检查")

            def ai_error(self):
                "用于处理AI交互模块返回错误的情况"
                self.outputbox.insertPlainText("出现错误，请重试\n")

            def flush_context(self):
                with open(context_path, 'w', encoding="utf-8") as c:
                    c.write('')
                self.outputbox.setText('')

        class SettingPage(QWidget):
            def __init__(self):
                super().__init__()
                self.setObjectName("选项")
                layout=QGridLayout()
                self.label1= QLabel("你的API-Key")
                self.label1.setStyleSheet("color:white;font-size:16px;")
                self.api_key_input = LineEdit()
                self.button1 = PushButton("确定")
                self.exit_button=PushButton("退出")

                layout.addWidget(self.label1, 0,0,1,4)
                layout.addWidget(self.api_key_input, 1,0,1,3)
                layout.addWidget(self.button1, 1,3,1,1)
                layout.addWidget(self.exit_button, 3,0,1,4)
                layout.setRowStretch(2,1)

                # 控件事件
                self.exit_button.clicked.connect(self.exit_app)
                self.button1.clicked.connect(self.get_api_key)
                if api_key:
                    self.api_key_input.setText(api_key)

                self.setLayout(layout)

            def exit_app(self):
                QApplication.quit()

            def get_api_key(self):
                temp_var=self.api_key_input.text()
                write_api_key(temp_var)
                set_api_key(temp_var)
                print('成功')
            
                
            
        class WorkWindow(FluentWindow):
            def __init__(self):
                super().__init__()
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self.setWindowTitle(WINDOW_TITLE)
                self.resize(800,600)
                self.titleBar.hide()
                self.setWindowFlags(
                    Qt.WindowType.WindowStaysOnTopHint       # 置顶
                )
                # 定位到左下角
                screen = QApplication.primaryScreen().availableGeometry()
                x = 0
                y = screen.height() - self.height()
                self.move(x, y)

                self.addSubInterface(HomePage(), FluentIcon.HOME, "首页")
                self.addSubInterface(SettingPage(), FluentIcon.SETTING, "选项")

                

                app = QApplication.instance()
                app.focusChanged.connect(self.on_focus_changed) # 监听焦点变化
                self._hwnd_ = None


            def showEvent(self, event):
                if not self._hwnd_:
                    self._hwnd_=win32gui.FindWindow(None, WINDOW_TITLE)
                super().showEvent(event)

            def on_focus_changed(self,old,new):
                if old is not None and self.isAncestorOf(old):  # 旧焦点在窗口内
                    if new is None or not self.isAncestorOf(new):   # 新焦点不在窗口内
                        win32gui.ShowWindow(self._hwnd_, win32con.SW_HIDE)
                        isvisible = False

        
                

        app = QApplication(sys.argv)
        setTheme(Theme.DARK)
        window = WorkWindow()
        window.show()
        sys.exit(app.exec())

main()
