import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


#ui目录下的主窗口模块main_windows.py
from ui.main_window import MainWindow
#处理数据的模块
from model import datamodel
#控制器
from controllers.main_controller import MainController




def main():

    app = QApplication(sys.argv)


    model = datamodel()

    window = MainWindow()#主窗口
    app.setStyleSheet(window.style)
    
    controller = MainController(model, window)

    window.show()#生成窗口

    sys.exit(app.exec_())#循环体


if __name__ == "__main__":
    main()