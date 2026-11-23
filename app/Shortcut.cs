using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace PoBKR
{
    internal sealed class ShortcutResult
    {
        public bool Ok;
        public readonly List<string> Paths = new List<string>();
        public string LinkPath = "";
        public string TargetExe = "";
        public string Arguments = "";
        public string IconPath = "";
        public string Error = "";
    }

    /// <summary>
    /// "Path of Building (한글)" 바로가기를 만든다.
    /// 기본 위치는 ① 패치한 PoB 폴더 안 ② 시작 메뉴(Programs) — 사용자가 PoB 를 어디에 두든
    /// 그 폴더에서, 또는 윈도우 키 검색으로 바로 실행할 수 있다. 바탕화면은 옵션(기본 꺼짐).
    /// WScript.Shell / PowerShell 없이 IShellLink(ShellLink COM) 만 쓴다.
    /// </summary>
    internal static class Shortcut
    {
        public const string DisplayName = "Path of Building (한글)";

        /// <summary>%LOCALAPPDATA%\PoB-KR-Patcher — 런처 사본을 두는 곳 (KR\init.lua 도 이 경로로 부른다).</summary>
        public static string InstallDir
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "PoB-KR-Patcher");
            }
        }

        public static string InstalledExe
        {
            get { return Path.Combine(InstallDir, "PoB-KR-Patcher.exe"); }
        }

        public static string DesktopLinkPath()
        {
            return DesktopLinkPath(Targets.Poe1);
        }

        public static string DesktopLinkPath(GameTarget target)
        {
            var desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            if (string.IsNullOrEmpty(desktop))
                desktop = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Desktop");
            return Path.Combine(desktop, (target ?? Targets.Poe1).ShortcutName + ".lnk");
        }

        public static string StartMenuLinkPath()
        {
            return StartMenuLinkPath(Targets.Poe1);
        }

        public static string StartMenuLinkPath(GameTarget target)
        {
            var programs = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
            if (string.IsNullOrEmpty(programs))
                programs = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    @"Microsoft\Windows\Start Menu\Programs");
            return Path.Combine(programs, (target ?? Targets.Poe1).ShortcutName + ".lnk");
        }

        public static string PoBFolderLinkPath(string pobDir)
        {
            return PoBFolderLinkPath(pobDir, Targets.Poe1);
        }

        public static string PoBFolderLinkPath(string pobDir, GameTarget target)
        {
            if (string.IsNullOrEmpty(pobDir)) return "";
            return Path.Combine(pobDir, (target ?? Targets.Poe1).ShortcutName + ".lnk");
        }

        /// <summary>현재 실행 중인 exe 경로.</summary>
        private static string SelfExe()
        {
            try
            {
                var module = Process.GetCurrentProcess().MainModule;
                if (module != null && !string.IsNullOrEmpty(module.FileName)) return module.FileName;
            }
            catch
            {
            }
            try
            {
                var loc = Assembly.GetExecutingAssembly().Location;
                if (!string.IsNullOrEmpty(loc)) return loc;
            }
            catch
            {
            }
            return Path.Combine(AppInfo.ExeDir, "PoB-KR-Patcher.exe");
        }

        /// <summary>
        /// 런처를 %LOCALAPPDATA%\PoB-KR-Patcher 에 복사해 고정 경로를 만든다.
        /// (내려받은 exe 를 지우거나 옮겨도 바로가기가 깨지지 않고, KR\init.lua 의 자동 업데이트도 이 경로를 쓴다.)
        /// </summary>
        public static string EnsureLauncherCopy()
        {
            var self = SelfExe();
            try
            {
                if (string.IsNullOrEmpty(self) || !File.Exists(self)) return self;
                var dest = InstalledExe;
                if (string.Equals(Path.GetFullPath(self), Path.GetFullPath(dest), StringComparison.OrdinalIgnoreCase))
                    return dest;
                Directory.CreateDirectory(InstallDir);
                File.Copy(self, dest, true);
                return dest;
            }
            catch
            {
                return self;
            }
        }

        /// <summary>
        /// 바로가기를 만든다. pobDir 안 + 시작 메뉴(+(desktop) 바탕화면). 실패해도 예외를 던지지 않는다.
        /// </summary>
        public static ShortcutResult Create(string pobDir, bool desktop)
        {
            return Create(pobDir, desktop, Targets.Poe1);
        }

        public static ShortcutResult Create(string pobDir, bool desktop, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            var result = new ShortcutResult();
            try
            {
                var launcher = EnsureLauncherCopy();
                if (string.IsNullOrEmpty(launcher) || !File.Exists(launcher))
                {
                    result.Error = "런처 실행 파일을 찾지 못했습니다.";
                    return result;
                }

                var targetDir = string.IsNullOrEmpty(pobDir) ? "" : pobDir.TrimEnd(Path.DirectorySeparatorChar);
                var exe = Installer.FindPoBExe(targetDir, target);
                result.TargetExe = launcher;
                var gameArg = target.IsPoe2 ? " --game poe2" : "";
                result.Arguments = (targetDir.Length == 0 ? "--launch" : "--launch \"" + targetDir + "\"") + gameArg;
                result.IconPath = string.IsNullOrEmpty(exe) ? launcher : exe;
                var workDir = Path.GetDirectoryName(launcher);
                var description = target.ShortcutName + " — 실행할 때마다 한글 패치를 확인·적용한 뒤 PoB 를 엽니다.";

                var wanted = new List<string>();
                var inFolder = PoBFolderLinkPath(targetDir, target);
                if (inFolder.Length > 0) wanted.Add(inFolder);
                wanted.Add(StartMenuLinkPath(target));
                if (desktop) wanted.Add(DesktopLinkPath(target));

                var errors = new List<string>();
                foreach (var link in wanted)
                {
                    try
                    {
                        var dir = Path.GetDirectoryName(link);
                        if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                        CreateLink(link, launcher, result.Arguments, workDir, result.IconPath, description);
                        if (File.Exists(link))
                        {
                            result.Paths.Add(link);
                            if (result.LinkPath.Length == 0) result.LinkPath = link;
                        }
                        else
                        {
                            errors.Add(link);
                        }
                    }
                    catch (Exception ex)
                    {
                        errors.Add(link + " (" + Short(ex) + ")");
                    }
                }

                result.Ok = result.Paths.Count > 0;
                if (!result.Ok)
                    result.Error = errors.Count > 0 ? string.Join("\n", errors.ToArray()) : "바로가기 파일이 만들어지지 않았습니다.";
                else if (errors.Count > 0)
                    result.Error = "일부 바로가기는 만들지 못했습니다: " + string.Join(", ", errors.ToArray());
            }
            catch (Exception ex)
            {
                result.Error = Short(ex);
            }
            return result;
        }

        private static string Short(Exception ex)
        {
            var e = ex;
            while (e.InnerException != null) e = e.InnerException;
            return e.Message;
        }

        private static void CreateLink(string linkPath, string targetExe, string arguments,
                                       string workingDir, string iconPath, string description)
        {
            var link = (IShellLinkW)new ShellLinkCoClass();
            link.SetPath(targetExe);
            link.SetArguments(arguments);
            if (!string.IsNullOrEmpty(workingDir)) link.SetWorkingDirectory(workingDir);
            if (!string.IsNullOrEmpty(iconPath)) link.SetIconLocation(iconPath, 0);
            link.SetDescription(description);
            ((IPersistFile)link).Save(linkPath, true);
        }

        // ── ShellLink COM (shlobj.h) ───────────────────────────────────────────
        // 메서드 순서가 COM vtable 순서와 같아야 한다. 중간에 빼거나 순서를 바꾸면 안 된다.

        [ComImport]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [Guid("000214F9-0000-0000-C000-000000000046")]
        internal interface IShellLinkW
        {
            void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszFile, int cch, IntPtr pfd, uint fFlags);
            void GetIDList(out IntPtr ppidl);
            void SetIDList(IntPtr pidl);
            void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszName, int cch);
            void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszDir, int cch);
            void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
            void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszArgs, int cch);
            void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
            void GetHotkey(out short pwHotkey);
            void SetHotkey(short wHotkey);
            void GetShowCmd(out int piShowCmd);
            void SetShowCmd(int iShowCmd);
            void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszIconPath, int cch, out int piIcon);
            void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
            void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, uint dwReserved);
            void Resolve(IntPtr hwnd, uint fFlags);
            void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
        }

        [ComImport]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [Guid("0000010b-0000-0000-C000-000000000046")]
        internal interface IPersistFile
        {
            void GetClassID(out Guid pClassID);
            [PreserveSig] int IsDirty();
            void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
            void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
            void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
            void GetCurFile(out IntPtr ppszFileName);
        }
    }

    /// <summary>ShellLink COM 클래스 (CLSID_ShellLink). new 로 만들면 COM 개체가 생성된다.</summary>
    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    internal class ShellLinkCoClass
    {
    }
}
