import os
import sys
import streamlit.web.cli as stcli


def resolve_path(path):
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)


if __name__ == "__main__":
    # 强制设置环境变量，解决一些打包后的路径问题
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"  # 静默模式

    # 构造启动命令：streamlit run app.py
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        #"--global.developmentMode=true",
    ]

    sys.exit(stcli.main())