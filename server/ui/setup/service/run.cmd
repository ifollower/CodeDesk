@echo off
%~d0
cd "%~dp0"
set nssm="%cd%\nssm"
cd ..

%nssm% install %1 "%cd%\bin\%2.exe"

%nssm% set %1 DisplayName %1
%nssm% set %1 Description CodeDesk %1 server
%nssm% set %1 Start SERVICE_AUTO_START

%nssm% set %1 ObjectName LocalSystem
%nssm% set %1 Type SERVICE_WIN32_OWN_PROCESS

%nssm% set %1 AppThrottle 1000
%nssm% set %1 AppExit Default Restart
%nssm% set %1 AppRestartDelay 0

%nssm% set %1 AppStdout "%cd%\logs\%2.out"
%nssm% set %1 AppStderr "%cd%\logs\%2.err"

%nssm% start %1
