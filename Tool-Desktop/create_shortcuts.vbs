Set WshShell = WScript.CreateObject("WScript.Shell")

' Get script directory (where install_app.bat is)
strDir = WshShell.CurrentDirectory

' Desktop shortcut
strDesktop = WshShell.SpecialFolders("Desktop")
Set link = WshShell.CreateShortcut(strDesktop & "\TaskReader.lnk")
link.TargetPath = strDir & "\start_bot.bat"
link.WorkingDirectory = strDir
link.IconLocation = "shell32.dll,13"
link.Save

' Start Menu shortcut
strStartMenu = WshShell.SpecialFolders("StartMenu")
Set link2 = WshShell.CreateShortcut(strStartMenu & "\TaskReader.lnk")
link2.TargetPath = strDir & "\start_bot.bat"
link2.WorkingDirectory = strDir
link2.IconLocation = "shell32.dll,13"
link2.Save

WScript.Echo "Shortcuts created successfully."
