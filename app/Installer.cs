using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
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
            return DataDir(pobDir, Targets.Poe1);
        }

        /// <summary>게임별 데이터 폴더 (PoE1: KR, PoE2: KR2).</summary>
        public static string DataDir(string pobDir, GameTarget target)
        {
            return Path.Combine(pobDir, (target ?? Targets.Poe1).DataDir);
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
            return FindPoB(startTarget, Targets.Poe1);
        }

        public static string FindPoB(string startTarget, GameTarget target)
        {
            if (target != null && target.IsPoe2)
            {
                var foundPoe2 = FindPoe2(startTarget);
                if (foundPoe2 != null) return foundPoe2;
            }
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

        /// <summary>PoE2 PoB 폴더 탐색 (폴더 이름·실행 파일 이름이 다르다).</summary>
        private static string FindPoe2(string startTarget)
        {
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
                AppInfo.ExeDir,
                ParentOrNull(AppInfo.ExeDir),
                Environment.CurrentDirectory,
                Path.Combine(local, "Programs", "Path of Building Community (PoE2)"),
                Path.Combine(local, "Programs", "Path of Building PoE2"),
                Path.Combine(local, "Programs", "Path of Building Community"),
                Path.Combine(local, "Programs", "Path of Building"),
                @"C:\Program Files\Path of Building Community (PoE2)",
                @"C:\Program Files\Path of Building PoE2",
                @"C:\Program Files (x86)\Path of Building Community (PoE2)",
                Path.Combine(roaming, "Path of Building PoE2")
            });
            foreach (var c in candidates)
            {
                if (IsPoB(c) && HasPoe2Exe(c)) return Clean(c);
            }
            var bases = new List<string>
            {
                ParentOrNull(AppInfo.ExeDir),
                Environment.CurrentDirectory,
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")
            };
            foreach (var b in bases)
            {
                if (string.IsNullOrEmpty(b)) continue;
                var found = ScanChildrenPoe2(b, 3);
                if (found != null) return found;
            }
            return null;
        }

        private static bool HasPoe2Exe(string dir)
        {
            foreach (var name in Targets.Poe2.ExeNames)
            {
                if (name.IndexOf("PoE2", StringComparison.OrdinalIgnoreCase) < 0) continue;
                try
                {
                    if (File.Exists(Path.Combine(dir, name))) return true;
                }
                catch
                {
                }
            }
            return false;
        }

        private static string ScanChildrenPoe2(string baseDir, int depth)
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
                if (IsPoB(s) && HasPoe2Exe(s)) return Clean(s);
            }
            foreach (var s in subs)
            {
                var deeper = ScanChildrenPoe2(s, depth - 1);
                if (deeper != null) return deeper;
            }
            return null;
        }

        public static string Clean(string dir)
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

        /// <summary>PoB 폴더의 실행 파일 (Path of Building.exe / PathOfBuildingCommunity.exe 등).</summary>
        public static string FindPoBExe(string pobDir)
        {
            return FindPoBExe(pobDir, Targets.Poe1);
        }

        public static string FindPoBExe(string pobDir, GameTarget target)
        {
            if (string.IsNullOrEmpty(pobDir)) return null;
            try
            {
                if (!Directory.Exists(pobDir)) return null;
                foreach (var name in (target ?? Targets.Poe1).ExeNames)
                {
                    var p = Path.Combine(pobDir, name);
                    if (File.Exists(p)) return p;
                }
                string best = null;
                foreach (var f in Directory.GetFiles(pobDir, "*.exe", SearchOption.TopDirectoryOnly))
                {
                    var name = Path.GetFileNameWithoutExtension(f) ?? "";
                    if (name.IndexOf("unins", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                    if (name.IndexOf("updat", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                    if (name.IndexOf("Path of Building", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        name.IndexOf("PathOfBuilding", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        best = f;
                        break;
                    }
                }
                return best;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>지금 실행 중인 Path of Building 의 폴더. 찾지 못하면 null.</summary>
        public static string FindRunningPoBFolder()
        {
            foreach (var name in new[] { "Path of Building", "PathOfBuilding", "PathOfBuildingCommunity" })
            {
                Process[] procs = null;
                try
                {
                    procs = Process.GetProcessesByName(name);
                }
                catch
                {
                    procs = null;
                }
                if (procs == null) continue;
                try
                {
                    foreach (var p in procs)
                    {
                        try
                        {
                            var file = p.MainModule == null ? "" : p.MainModule.FileName;
                            if (string.IsNullOrEmpty(file)) continue;
                            var dir = Path.GetDirectoryName(file);
                            if (IsPoB(dir)) return Clean(dir);
                            var parent = ParentOrNull(dir);
                            if (IsPoB(parent)) return Clean(parent);
                        }
                        catch
                        {
                        }
                    }
                }
                finally
                {
                    foreach (var p in procs) p.Dispose();
                }
            }
            return null;
        }

        /// <summary>Modules\Main.lua 의 마지막 수정 시각 (없으면 DateTime.MinValue).</summary>
        public static DateTime MainLuaTime(string pobDir)
        {
            if (string.IsNullOrEmpty(pobDir)) return DateTime.MinValue;
            try
            {
                var path = MainLuaPath(pobDir);
                return File.Exists(path) ? File.GetLastWriteTimeUtc(path) : DateTime.MinValue;
            }
            catch
            {
                return DateTime.MinValue;
            }
        }

        /// <summary>설치 위치·바탕화면·다운로드 등에서 찾은 PoB 폴더 목록 (Main.lua 가 최신인 순).</summary>
        public static List<string> FindPoBCandidates(int depth)
        {
            var found = new List<string>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);

            var standard = new[]
            {
                AppInfo.ExeDir,
                ParentOrNull(AppInfo.ExeDir),
                Environment.CurrentDirectory,
                Path.Combine(local, "Programs", "Path of Building Community"),
                Path.Combine(local, "Programs", "Path of Building"),
                @"C:\Program Files\Path of Building Community",
                @"C:\Program Files\Path of Building",
                @"C:\Program Files (x86)\Path of Building Community",
                @"C:\Program Files (x86)\Path of Building",
                Path.Combine(roaming, "Path of Building")
            };
            foreach (var s in standard)
            {
                if (string.IsNullOrEmpty(s)) continue;
                if (IsPoB(s) && seen.Add(Clean(s))) found.Add(Clean(s));
            }

            var bases = new[]
            {
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")
            };
            foreach (var b in bases)
            {
                if (string.IsNullOrEmpty(b)) continue;
                CollectCandidates(b, depth, seen, found);
            }

            found.Sort(delegate(string a, string b) { return MainLuaTime(b).CompareTo(MainLuaTime(a)); });
            return found;
        }

        private static void CollectCandidates(string baseDir, int depth, HashSet<string> seen, List<string> found)
        {
            if (string.IsNullOrEmpty(baseDir) || depth <= 0) return;
            string[] subs;
            try
            {
                if (!Directory.Exists(baseDir)) return;
                subs = Directory.GetDirectories(baseDir);
            }
            catch
            {
                return;
            }
            foreach (var s in subs)
            {
                if (!IsPoB(s)) continue;
                var c = Clean(s);
                if (seen.Add(c)) found.Add(c);
            }
            foreach (var s in subs)
            {
                var name = Path.GetFileName(s) ?? "";
                if (name.IndexOf("path of building", StringComparison.OrdinalIgnoreCase) < 0 &&
                    name.IndexOf("PathOfBuilding", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    continue;
                }
                CollectCandidates(s, depth - 1, seen, found);
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
            return HasMarker(pobDir, Targets.Poe1);
        }

        public static bool HasMarker(string pobDir, GameTarget target)
        {
            try
            {
                var path = MainLuaPath(pobDir);
                if (!File.Exists(path)) return false;
                var marker = (target ?? Targets.Poe1).Marker;
                if (target != null && target.IsPoe2)
                {
                    // "-- [PoB-KR]" 는 "-- [PoB-KR2]" 의 앞부분이므로 정확히 비교한다
                    return ReadText(path).IndexOf(marker, StringComparison.Ordinal) >= 0;
                }
                return ReadText(path).IndexOf(marker, StringComparison.Ordinal) >= 0;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>설치된 데이터 버전(KR\version.txt 첫 토큰). 없으면 null.</summary>
        public static string InstalledVersion(string pobDir)
        {
            return InstalledVersion(pobDir, Targets.Poe1);
        }

        public static string InstalledVersion(string pobDir, GameTarget target)
        {
            try
            {
                var path = Path.Combine(DataDir(pobDir, target), "version.txt");
                if (!File.Exists(path)) return HasMarker(pobDir, target) ? "0.0.0" : null;
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
            return HasData(pobDir, Targets.Poe1);
        }

        public static bool HasData(string pobDir, GameTarget target)
        {
            try
            {
                return File.Exists(Path.Combine(DataDir(pobDir, target), "init.lua"));
            }
            catch
            {
                return false;
            }
        }

        /// <summary>KR 폴더에 payload zip 을 푼다 (기존 파일 덮어쓰기).</summary>
        public static int ExtractPayload(byte[] zip, string pobDir)
        {
            return ExtractPayload(zip, pobDir, Targets.Poe1);
        }

        public static int ExtractPayload(byte[] zip, string pobDir, GameTarget target)
        {
            var data = DataDir(pobDir, target);
            Directory.CreateDirectory(data);
            return ExtractZipTo(zip, data);
        }

        /// <summary>zip 을 지정한 폴더에 푼다.</summary>
        public static int ExtractZipTo(byte[] zip, string destDir)
        {
            Directory.CreateDirectory(destDir);
            var krFull = Path.GetFullPath(destDir).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var count = 0;
            using (var ms = new MemoryStream(zip, false))
            using (var archive = new ZipArchive(ms, ZipArchiveMode.Read))
            {
                foreach (var entry in archive.Entries)
                {
                    if (string.IsNullOrEmpty(entry.Name) && entry.FullName.EndsWith("/", StringComparison.Ordinal)) continue;
                    var rel = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    var dest = Path.GetFullPath(Path.Combine(destDir, rel));
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
            return Apply(pobDir, payload, data, Targets.Poe1);
        }

        public static ApplyResult Apply(string pobDir, byte[] payload, BuildInfo data, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            var result = new ApplyResult { Target = pobDir, VersionText = AppInfo.VersionLine(data) };
            try
            {
                if (!IsPoB(pobDir))
                {
                    result.Error = "Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + pobDir;
                    return result;
                }

                ExtractPayload(payload, pobDir, target);
                File.WriteAllText(Path.Combine(DataDir(pobDir, target), "version.txt"),
                    AppInfo.VersionLine(data) + "\r\n", AppInfo.Utf8NoBom);

                var mainPath = MainLuaPath(pobDir);
                var backupDir = Path.Combine(DataDir(pobDir, target), "_설치기록");
                var backupPath = Path.Combine(backupDir, "Main.lua.orig");

                var content = ReadText(mainPath);
                if (content.IndexOf(target.Marker, StringComparison.Ordinal) < 0)
                {
                    Directory.CreateDirectory(backupDir);
                    if (!File.Exists(backupPath))
                    {
                        File.Copy(mainPath, backupPath, true);
                        result.BackedUp = true;
                    }
                    WriteText(mainPath, target.Loader + content);
                }
                else
                {
                    result.AlreadyPatched = true;
                }

                result.Ok = HasMarker(pobDir, target);
                if (!result.Ok) result.Error = "Modules\\Main.lua 수정을 확인하지 못했습니다.";
                if (result.Ok) OnPatched(pobDir, AppInfo.VersionLine(data), target);
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

        /// <summary>패치 성공 후: 마지막 폴더 저장, 런처 사본 준비(자동 업데이트용), 미리 받아 둔 업데이트 정리.</summary>
        private static void OnPatched(string pobDir, string versionLine, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            try
            {
                var settings = Settings.Load();
                if (!string.Equals(settings.GetLastTarget(target.Id), pobDir, StringComparison.OrdinalIgnoreCase))
                {
                    settings.SetLastTarget(target.Id, pobDir);
                    settings.Save();
                }
            }
            catch
            {
            }
            // KR\init.lua 가 자동 업데이트를 부를 때 쓰는 고정 경로 확보
            Shortcut.EnsureLauncherCopy();
            ClearStaged(pobDir, target);
        }

        /// <summary>Modules\Main.lua 가 PoB 업데이트로 덮어써졌을 때 로더만 다시 넣는다 (KR 데이터는 그대로).</summary>
        public static bool EnsureLoader(string pobDir)
        {
            return EnsureLoader(pobDir, Targets.Poe1);
        }

        public static bool EnsureLoader(string pobDir, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            try
            {
                if (!IsPoB(pobDir)) return false;
                var mainPath = MainLuaPath(pobDir);
                var content = ReadText(mainPath);
                if (content.IndexOf(target.Marker, StringComparison.Ordinal) >= 0) return true;

                var backupDir = Path.Combine(DataDir(pobDir, target), "_설치기록");
                var backupPath = Path.Combine(backupDir, "Main.lua.orig");
                Directory.CreateDirectory(backupDir);
                if (!File.Exists(backupPath)) File.Copy(mainPath, backupPath, true);
                WriteText(mainPath, target.Loader + content);
                return HasMarker(pobDir, target);
            }
            catch
            {
                return false;
            }
        }

        // ── 미리 받아 두기(스테이징) ──────────────────────────────────────────
        // PoB 가 실행 중일 때는 살아 있는 KR 파일을 건드리지 않고 KR\_update 에 넣어 둔다.
        // 다음 PoB 실행 때 init.lua 가 (데이터를 읽기 전에) 이 폴더를 반영한다.

        public static string UpdateDir(string pobDir)
        {
            return UpdateDir(pobDir, Targets.Poe1);
        }

        public static string UpdateDir(string pobDir, GameTarget target)
        {
            return Path.Combine(DataDir(pobDir, target), "_update");
        }

        private static string PendingFile(string pobDir)
        {
            return PendingFile(pobDir, Targets.Poe1);
        }

        private static string PendingFile(string pobDir, GameTarget target)
        {
            return Path.Combine(UpdateDir(pobDir, target), "pending.txt");
        }

        public static bool HasPending(string pobDir)
        {
            return HasPending(pobDir, Targets.Poe1);
        }

        public static bool HasPending(string pobDir, GameTarget target)
        {
            try
            {
                return File.Exists(PendingFile(pobDir, target));
            }
            catch
            {
                return false;
            }
        }

        /// <summary>내려받은 payload 를 KR\_update\data 에 풀고 pending.txt 를 남긴다.</summary>
        public static bool Stage(string pobDir, byte[] payload, string versionLine)
        {
            return Stage(pobDir, payload, versionLine, Targets.Poe1);
        }

        public static bool Stage(string pobDir, byte[] payload, string versionLine, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            try
            {
                if (!IsPoB(pobDir)) return false;
                ClearStaged(pobDir, target);
                var stageRoot = Path.Combine(UpdateDir(pobDir, target), "data");
                ExtractZipTo(payload, stageRoot);
                File.WriteAllText(PendingFile(pobDir, target), versionLine + "\r\n", AppInfo.Utf8NoBom);
                return HasPending(pobDir, target);
            }
            catch
            {
                return false;
            }
        }

        /// <summary>KR\_update\data 를 KR 로 옮긴다. PoB 가 실행 중이 아니거나, 시작 직후(데이터 로드 전)에만 호출한다.</summary>
        public static bool ApplyStaged(string pobDir, out string versionLine)
        {
            return ApplyStaged(pobDir, out versionLine, Targets.Poe1);
        }

        public static bool ApplyStaged(string pobDir, out string versionLine, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            versionLine = "";
            try
            {
                if (!IsPoB(pobDir) || !HasPending(pobDir, target)) return false;
                var pending = File.ReadAllText(PendingFile(pobDir, target), Encoding.UTF8).Trim();
                var stageRoot = Path.Combine(UpdateDir(pobDir, target), "data");
                var kr = DataDir(pobDir, target);
                if (!Directory.Exists(stageRoot))
                {
                    // 받아 둔 파일이 없으면 pending 만 남기지 않는다 (다음에 다시 받는다).
                    ClearStaged(pobDir, target);
                    return false;
                }
                var count = 0;
                foreach (var src in Directory.GetFiles(stageRoot, "*", SearchOption.AllDirectories))
                {
                    var rel = src.Substring(stageRoot.Length).TrimStart(Path.DirectorySeparatorChar);
                    var dest = Path.Combine(kr, rel);
                    var dir = Path.GetDirectoryName(dest);
                    if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                    File.Copy(src, dest, true);
                    count++;
                }
                if (count == 0) return false;
                if (pending.Length > 0)
                    File.WriteAllText(Path.Combine(kr, "version.txt"), pending + "\r\n", AppInfo.Utf8NoBom);
                versionLine = pending;
                ClearStaged(pobDir, target);
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>스테이징 폴더를 비운다 (lastcheck.txt 는 남긴다).</summary>
        public static void ClearStaged(string pobDir)
        {
            ClearStaged(pobDir, Targets.Poe1);
        }

        public static void ClearStaged(string pobDir, GameTarget target)
        {
            try
            {
                var dir = UpdateDir(pobDir, target);
                if (!Directory.Exists(dir)) return;
                var data = Path.Combine(dir, "data");
                if (Directory.Exists(data)) Directory.Delete(data, true);
                var pending = PendingFile(pobDir, target);
                if (File.Exists(pending)) File.Delete(pending);
            }
            catch
            {
            }
        }

        private static string LastCheckFile(string pobDir, GameTarget target)
        {
            return Path.Combine(UpdateDir(pobDir, target), "lastcheck.txt");
        }

        public static void WriteLastCheck(string pobDir, long unixSeconds)
        {
            WriteLastCheck(pobDir, unixSeconds, Targets.Poe1);
        }

        public static void WriteLastCheck(string pobDir, long unixSeconds, GameTarget target)
        {
            try
            {
                Directory.CreateDirectory(UpdateDir(pobDir, target));
                File.WriteAllText(LastCheckFile(pobDir, target), unixSeconds.ToString(CultureInfo.InvariantCulture) + "\r\n", AppInfo.Utf8NoBom);
            }
            catch
            {
            }
        }

        public static long NowUnix()
        {
            return (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        }

        public static RestoreResult Restore(string pobDir)
        {
            return Restore(pobDir, Targets.Poe1);
        }

        public static RestoreResult Restore(string pobDir, GameTarget target)
        {
            target = target ?? Targets.Poe1;
            var result = new RestoreResult();
            try
            {
                if (!IsPoB(pobDir))
                {
                    result.Error = "Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + pobDir;
                    return result;
                }
                var mainPath = MainLuaPath(pobDir);
                var kr = DataDir(pobDir, target);
                var backupPath = Path.Combine(kr, "_설치기록", "Main.lua.orig");
                result.WasPatched = HasMarker(pobDir, target);

                if (File.Exists(backupPath))
                {
                    File.Copy(backupPath, mainPath, true);
                    result.RestoredFromBackup = true;
                }
                else if (result.WasPatched)
                {
                    var content = ReadText(mainPath);
                    var lines = content.Replace("\r\n", "\n").Split('\n')
                        .Where(l => l.IndexOf(target.Marker, StringComparison.Ordinal) < 0
                                    && l.IndexOf(target.DataDir + "/init.lua", StringComparison.Ordinal) < 0
                                    && l.IndexOf("KR_ROOT", StringComparison.Ordinal) < 0)
                        .ToArray();
                    WriteText(mainPath, string.Join("\r\n", lines));
                    result.RemovedLoader = true;
                }

                if (Directory.Exists(kr))
                {
                    Directory.Delete(kr, true);
                    result.KrRemoved = true;
                }
                result.Ok = !HasMarker(pobDir, target) && !Directory.Exists(kr);
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
