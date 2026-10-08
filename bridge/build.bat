@echo off
rem Builds the 32-bit bridge DLL (build\sc3kbridge.dll) - or, with "plug", the optional GZCOM plugin stub
rem (build\sc3kplug.dll) - with MSVC: Visual Studio 2017 or later, or the Build Tools, with the C++ x86/x64
rem toolset. Run from any shell:  bridge\build.bat [plug]
rem In a Developer Command Prompt for x86 (VSCMD_ARG_TGT_ARCH=x86) the compiler already set up is used.
setlocal
if /i "%VSCMD_ARG_TGT_ARCH%"=="x86" goto build
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" goto find
echo vswhere.exe not found: install Visual Studio or the Build Tools with "Desktop development with C++".
exit /b 1
:find
set "VSDIR="
for /f "usebackq delims=" %%i in (`call "%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%i"
if defined VSDIR goto vcvars
echo No Visual Studio with the C++ x86/x64 toolset was found.
exit /b 1
:vcvars
call "%VSDIR%\VC\Auxiliary\Build\vcvarsall.bat" x64_x86 >nul 2>&1
if errorlevel 1 (
  echo vcvarsall.bat x64_x86 failed for the Visual Studio in "%VSDIR%".
  exit /b 1
)
:build
cd /d "%~dp0"
if not exist build mkdir build
rem sc3kplug.dll is the stable stub installed in Apps\PlugIn (locked while the game runs)
if /i "%~1"=="plug" goto plug
cl /nologo /LD /MT /O2 /W3 /GS- /GR- /EHs-c- /DNDEBUG sc3kbridge.cpp /Fobuild\ /Fe:build\sc3kbridge.dll /link /DYNAMICBASE:NO user32.lib kernel32.lib
exit /b %ERRORLEVEL%
:plug
cl /nologo /LD /MT /O2 /W3 /GS- /GR- /EHs-c- /DNDEBUG sc3kplug.cpp /Fobuild\ /Fe:build\sc3kplug.dll /link /DYNAMICBASE:NO user32.lib kernel32.lib
exit /b %ERRORLEVEL%
