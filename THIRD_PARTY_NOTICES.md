# Third-Party Notices（第三方开源组件声明）

本文件汇总了本项目运行时依赖的第三方开源软件包信息（名称/版本/许可证/主页）。  
数据来源：当前 `requirements.txt` + 本机 Python 环境元信息（`importlib.metadata`）。  
注意：部分包在元信息中未显式填写 `License` 字段，因此许可证以 `License Classifier` 推断为主，建议在正式发布前再人工核对一次。

## Python 运行时依赖

| 包名 | 版本 | 许可证（元信息） | 许可证（Classifier） | 主页/项目链接（元信息） |
|---|---:|---|---|---|
| annotated-types | 0.7.0 |  | MIT | Homepage, https://github.com/annotated-types/annotated-types |
| anyio | 4.13.0 |  |  | Documentation, https://anyio.readthedocs.io/en/latest/ |
| blinker | 1.9.0 |  | MIT | Chat, https://discord.gg/pallets |
| certifi | 2026.2.25 | MPL-2.0 | MPL-2.0 | https://github.com/certifi/python-certifi |
| charset-normalizer | 3.4.6 | MIT |  | Changelog, https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md |
| click | 8.3.1 |  |  | Changes, https://click.palletsprojects.com/page/changes/ |
| colorama | 0.4.6 |  | BSD | Homepage, https://github.com/tartley/colorama |
| distro | 1.9.0 | Apache License, Version 2.0 | Apache-2.0 | https://github.com/python-distro/distro |
| exceptiongroup | 1.3.1 |  | MIT | Changelog, https://github.com/agronholm/exceptiongroup/blob/main/CHANGES.rst |
| Flask | 3.1.3 |  |  | Changes, https://flask.palletsprojects.com/page/changes/ |
| flask-cors | 6.0.2 |  |  | Homepage, https://corydolphin.github.io/flask-cors/ |
| h11 | 0.16.0 | MIT | MIT | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 |  | BSD | Documentation, https://www.encode.io/httpcore |
| httpx | 0.28.1 | BSD-3-Clause | BSD | Changelog, https://github.com/encode/httpx/blob/master/CHANGELOG.md |
| idna | 3.11 |  |  | Changelog, https://github.com/kjd/idna/blob/master/HISTORY.rst |
| itsdangerous | 2.2.0 |  | BSD | Changes, https://itsdangerous.palletsprojects.com/changes/ |
| Jinja2 | 3.1.6 |  | BSD | Changes, https://jinja.palletsprojects.com/changes/ |
| jiter | 0.13.0 |  | MIT | https://github.com/pydantic/jiter/ |
| MarkupSafe | 3.0.3 |  |  | Donate, https://palletsprojects.com/donate |
| openai | 2.30.0 | Apache-2.0 | Apache-2.0 | Homepage, https://github.com/openai/openai-python |
| pydantic | 2.12.5 |  |  | Homepage, https://github.com/pydantic/pydantic |
| pydantic_core | 2.41.5 |  |  | https://github.com/pydantic/pydantic-core |
| python-dotenv | 1.2.2 | BSD-3-Clause |  | Source, https://github.com/theskumar/python-dotenv |
| requests | 2.33.0 | Apache-2.0 | Apache-2.0 | Documentation, https://requests.readthedocs.io |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | MIT / Apache-2.0 | Homepage, https://github.com/python-trio/sniffio |
| tqdm | 4.67.3 | MPL-2.0 AND MIT |  | homepage, https://tqdm.github.io |
| typing-inspection | 0.4.2 |  |  | Homepage, https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.15.0 |  |  | Bug Tracker, https://github.com/python/typing_extensions/issues |
| urllib3 | 2.6.3 |  |  | Changelog, https://github.com/urllib3/urllib3/blob/main/CHANGES.rst |
| Werkzeug | 3.1.7 |  |  | Changes, https://werkzeug.palletsprojects.com/page/changes/ |

## 前端说明

当前 `frontend/index.html` 为静态 HTML/CSS/JavaScript，并未检测到通过 CDN 引入的第三方前端库脚本标签。  
仓库中存在 `frontend/script.js`（包含 `echarts.init(...)` 的调用痕迹），但是否实际被页面引用需以最终发布的前端入口文件为准。

## 打包工具（构建依赖）

本项目常用 **PyInstaller** 进行 Windows 打包（构建阶段依赖，不一定属于运行时依赖）。若你对外发布 exe，建议同时在发布说明中列出构建工具版本以便复现构建。

