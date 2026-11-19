using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;

namespace PoBKR
{
    internal sealed class ApplyResult
    {
        public bool Ok;
        public bool AlreadyPatched;
        public bool BackedUp;
        public string Target = "";
        public string VersionText = "";
        public string Error = "";
    }

    internal sealed class RestoreResult
    {
        public bool Ok;
        public bool RestoredFromBackup;
        public bool RemovedLoader;
        public bool WasPatched;
        public bool KrRemoved;
        public string Error = "";
    }

    /// <summary>PoB 폴더 탐색 + KR 배포 + Modules\Main.lua 로더 삽입/복구 (install.ps1 / uninstall.ps1 과 동일한 결과).</summary>
    internal static class Installer
    {
        public static bool IsPoB(string dir)
        {
            if (string.IsNullOrEmpty(dir)) return false;
            try
            {
                return File.Exists(Path.Combine(dir, "Modules", "Main.lua"));
            }
            catch
            {
                return false;
            }
        }

        public static string MainLuaPath(string pobDir)
        {
            return Path.Combine(pobDir, "Modules", "Main.lua");
        }

        public static string KrDir(string pobDir)
        {
            return Path.Combine(pobDir, "KR");
        }

        private static string ParentOrNull(string dir)
        {
            if (string.IsNullOrEmpty(dir)) return null;
            try
            {
                var p = Path.GetDirectoryName(dir.TrimEnd(Path.DirectorySeparatorChar));
                return string.IsNullOrEmpty(p) ? null : p;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>설치 폴더 자동 탐색. 찾지 못하면 null.</summary>
        public static string FindPoB(string startTarget)
        {
            var exeDir = AppInfo.ExeDir;
            var p1 = ParentOrNull(exeDir);
            var p2 = ParentOrNull(p1);
            var cwd = Environment.CurrentDirectory;
            var cwdParent = ParentOrNull(cwd);
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);

            var candidates = new List<string>();
            if (!string.IsNullOrEmpty(startTarget))
            {
                candidates.Add(startTarget);
                candidates.Add(Path.Combine(startTarget, "lua"));
            }
            candidates.AddRange(new[]
            {
                exeDir,
                p1,
                p2,
                cwd,
                cwdParent,
                Path.Combine(local, "Programs", "Path of Building Community"),
                Path.Combine(local, "Programs", "Path of Building"),
                @"C:\Program Files\Path of Building Community",
                @"C:\Program Files\Path of Building",
                @"C:\Program Files (x86)\Path of Building Community",
                @"C:\Program Files (x86)\Path of Building",
                Path.Combine(roaming, "Path of Building")
            });

            foreach (var c in candidates)
            {
                if (IsPoB(c)) return Clean(c);
            }

            // 압축을 풀어 둔 포터블 폴더나 바탕화면/다운로드 폴더 안의 PoB 폴더.
            var bases = new List<string> { p1, cwd };
            var desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            var downloads = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
            bases.Add(desktop);
            bases.Add(downloads);

            foreach (var b in bases.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var found = ScanChildren(b, 2);
                if (found != null) return found;
            }
            return null;
        }

        private static string Clean(string dir)
        {
            try
            {
                return Path.GetFullPath(dir).TrimEnd(Path.DirectorySeparatorChar);
            }
            catch
            {
                return dir;
            }
        }

        private static string ScanChildren(string baseDir, int depth)
        {
            if (string.IsNullOrEmpty(baseDir) || depth <= 0) return null;
            string[] subs;
            try
            {
                if (!Directory.Exists(baseDir)) return null;
                subs = Directory.GetDirectories(baseDir);
            }
            catch
            {
                return null;
            }
            foreach (var s in subs)
            {
                if (IsPoB(s)) return Clean(s);
            }
            foreach (var s in subs)
            {
                var name = Path.GetFileName(s) ?? "";
                if (name.IndexOf("path of building", StringComparison.OrdinalIgnoreCase) < 0 &&
                    name.IndexOf("PathOfBuilding", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    continue;
                }
                var deeper = ScanChildren(s, depth - 1);
                if (deeper != null) return deeper;
            }
            return null;
        }

        /// <summary>PoB 가 실행 중이면 True (파일이 잠겨 패치가 실패하는 것을 미리 막는다).</summary>
        public static bool IsPoBRunning()
        {
            foreach (var name in new[] { "PathOfBuilding", "PathOfBuildingCommunity", "Path of Building" })
            {
                try
                {
                    var procs = Process.GetProcessesByName(name);
                    if (procs != null && procs.Length > 0)
                    {
                        foreach (var p in procs) p.Dispose();
                        return true;
                    }
                }
                catch
                {
                }
            }
            return false;
        }

        public static string ReadText(string path)
        {
            // BOM 이 있으면 자동으로 제거되고, 없으면 UTF-8 로 읽는다.
            return File.ReadAllText(path, Encoding.UTF8);
        }

        public static void WriteText(string path, string text)
        {
            File.WriteAllText(path, text, AppInfo.Utf8NoBom);
        }

        public static bool HasMarker(string pobDir)
        {
            try
            {
                var path = MainLuaPath(pobDir);
                if (!File.Exists(path)) return false;
                return ReadText(path).IndexOf(AppInfo.Marker, StringComparison.Ordinal) >= 0;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>설치된 데이터 버전(KR\version.txt 첫 토큰). 없으면 null.</summary>
        public static string InstalledVersion(string pobDir)
        {
            try
            {
                var path = Path.Combine(KrDir(pobDir), "version.txt");
                if (!File.Exists(path)) return HasMarker(pobDir) ? "0.0.0" : null;
                var text = ReadText(path).Trim();
                if (text.Length == 0) return "0.0.0";
                var i = text.IndexOf(' ');
                return i < 0 ? text : text.Substring(0, i);
            }
            catch
            {
                return null;
            }
        }

        public static bool HasData(string pobDir)
        {
            try
            {
                return File.Exists(Path.Combine(KrDir(pobDir), "init.lua"));
            }
            catch
            {
                return false;
            }
        }

        /// <summary>KR 폴더에 payload zip 을 푼다 (기존 파일 덮어쓰기).</summary>
        public static int ExtractPayload(byte[] zip, string pobDir)
        {
            var kr = KrDir(pobDir);
            Directory.CreateDirectory(kr);
            var krFull = Path.GetFullPath(kr).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var count = 0;
            using (var ms = new MemoryStream(zip, false))
            using (var archive = new ZipArchive(ms, ZipArchiveMode.Read))
            {
                foreach (var entry in archive.Entries)
                {
                    if (string.IsNullOrEmpty(entry.Name) && entry.FullName.EndsWith("/", StringComparison.Ordinal)) continue;
                    var rel = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    var dest = Path.GetFullPath(Path.Combine(kr, rel));
                    if (!dest.StartsWith(krFull, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("압축 파일 안에 잘못된 경로가 있습니다: " + entry.FullName);
                    var dir = Path.GetDirectoryName(dest);
                    if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                    entry.ExtractToFile(dest, true);
                    count++;
                }
            }
            return count;
        }

        public static ApplyResult Apply(string pobDir, byte[] payload, BuildInfo data)
        {
            var result = new ApplyResult { Target = pobDir, VersionText = AppInfo.VersionLine(data) };
            try
            {
                if (!IsPoB(pobDir))
                {
                    result.Error = "Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + pobDir;
                    return result;
                }

                ExtractPayload(payload, pobDir);
                File.WriteAllText(Path.Combine(KrDir(pobDir), "version.txt"),
                    AppInfo.VersionLine(data) + "\r\n", AppInfo.Utf8NoBom);

                var mainPath = MainLuaPath(pobDir);
                var backupDir = Path.Combine(KrDir(pobDir), "_설치기록");
                var backupPath = Path.Combine(backupDir, "Main.lua.orig");

                var content = ReadText(mainPath);
                if (content.IndexOf(AppInfo.Marker, StringComparison.Ordinal) < 0)
                {
                    Directory.CreateDirectory(backupDir);
                    if (!File.Exists(backupPath))
                    {
                        File.Copy(mainPath, backupPath, true);
                        result.BackedUp = true;
                    }
                    WriteText(mainPath, AppInfo.Loader + content);
                }
                else
                {
                    result.AlreadyPatched = true;
                }

                result.Ok = HasMarker(pobDir);
                if (!result.Ok) result.Error = "Modules\\Main.lua 수정을 확인하지 못했습니다.";
                return result;
            }
            catch (UnauthorizedAccessException ex)
            {
                result.Error = "파일 쓰기 권한이 없습니다. Path of Building 을 종료하고, 필요하면 관리자 권한으로 다시 실행해 주세요.\n" + ex.Message;
                return result;
            }
            catch (IOException ex)
            {
                result.Error = "파일을 쓰지 못했습니다. Path of Building 이 실행 중인지 확인해 주세요.\n" + ex.Message;
                return result;
            }
            catch (Exception ex)
            {
                result.Error = ex.Message;
                return result;
            }
        }

        public static RestoreResult Restore(string pobDir)
        {
            var result = new RestoreResult();
            try
            {
                if (!IsPoB(pobDir))
                {
                    result.Error = "Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + pobDir;
                    return result;
                }
                var mainPath = MainLuaPath(pobDir);
                var kr = KrDir(pobDir);
                var backupPath = Path.Combine(kr, "_설치기록", "Main.lua.orig");
                result.WasPatched = HasMarker(pobDir);

                if (File.Exists(backupPath))
                {
                    File.Copy(backupPath, mainPath, true);
                    result.RestoredFromBackup = true;
                }
                else if (result.WasPatched)
                {
                    var content = ReadText(mainPath);
                    var lines = content.Replace("\r\n", "\n").Split('\n')
                        .Where(l => l.IndexOf(AppInfo.Marker, StringComparison.Ordinal) < 0
                                    && l.IndexOf("KR/init.lua", StringComparison.Ordinal) < 0)
                        .ToArray();
                    WriteText(mainPath, string.Join("\r\n", lines));
                    result.RemovedLoader = true;
                }

                if (Directory.Exists(kr))
                {
                    Directory.Delete(kr, true);
                    result.KrRemoved = true;
                }
                result.Ok = !HasMarker(pobDir) && !Directory.Exists(kr);
                return result;
            }
            catch (Exception ex)
            {
                result.Error = ex.Message;
                return result;
            }
        }
    }
}
