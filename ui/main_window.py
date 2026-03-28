class MainWindow:
    def __init__(self):
        super().__init__()
        self.setup_ui()          # 创建界面控件
        self.setWindowTitle("Tree")
        self.resize(1280, 1280)
        self.style = STYLE

#全局样式style:在这里更改ui风格：
STYLE = """
QWidget {
    background-color: #f5f5f5;
    font-family: "Microsoft YaHei";
    font-size: 12px;
}
QLabel {
    color: #333;
    padding: 4px;
}
QLineEdit {
    border: 1px solid #ccc;
    border-radius: 3px;
    padding: 5px;
    selection-background-color: #3498db;
}
QLineEdit:focus {
    border: 1px solid #3498db;
}
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 6px 12px;
    min-width: 70px;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1c6ea4;
}
QPushButton#cancel_btn {
    background-color: #95a5a6;
}
QPushButton#cancel_btn:hover {
    background-color: #7f8c8d;
}
"""

def setup_ui(self):
    #@KZAgent 生成一个基本的UI界面，左侧有一个300*800的窗口，中间有一个图形界面用于自定义，下方是1300*300的用户交互界面
    