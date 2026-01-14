Set WshShell = CreateObject("WScript.Shell")
' 0 表示隐藏窗口，False 表示不等待脚本结束直接返回
WshShell.Run chr(34) & "start.bat" & Chr(34), 0
Set WshShell = Nothing