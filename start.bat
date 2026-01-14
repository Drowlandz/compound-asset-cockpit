@echo off
cd /d "%~dp0"

:: Step 1: 在后台启动一个计时器，2秒后强行打开浏览器
:: (这样可以确保 Streamlit 服务器启动好了再开网页)
start "" /b cmd /c "timeout /t 2 >nul & start http://localhost:8501"

:: Step 2: 启动 Streamlit
:: 这里我们依然保持 headless=true，防止 Streamlit 自己也弹一次窗，导致打开两个标签页
streamlit run app.py --server.headless true