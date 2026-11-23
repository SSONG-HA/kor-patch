using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

namespace PoBKR
{
    /// <summary>패치 대상 게임(PoE1 / PoE2)의 차이를 한 곳에 모은 것.</summary>
    internal sealed class GameTarget
    {
        public readonly string Id;          // "poe1" / "poe2"
        public readonly string Display;     // 화면에 보이는 이름
        public readonly string DataDir;     // PoB 폴더 안 데이터 폴더 (KR / KR2)
        public readonly string Marker;      // Modules\Main.lua 에 넣는 표식
        public readonly string Loader;      // Modules\Main.lua 맨 앞에 붙이는 두 줄
        public readonly string DataAsset;   // 릴리스 자산 이름 (KR-data.zip / KR-data-poe2.zip)
        public readonly string ShortcutName;// 바로가기 이름
        public readonly string ExeFolderHint; // 자동 탐색 시 폴더 이름 힌트
        public readonly string[] ExeNames;  // PoB 실행 파일 후보

        public GameTarget(string id, string display, string dataDir, string marker, string loader,
            string dataAsset, string shortcutName, string exeFolderHint, string[] exeNames)
        {
            Id = id;
            Display = display;
            DataDir = dataDir;
            Marker = marker;
            Loader = loader;
            DataAsset = dataAsset;
            ShortcutName = shortcutName;
            ExeFolderHint = exeFolderHint;
            ExeNames = exeNames;
        }

        public bool IsPoe2 { get { return Id == "poe2"; } }

        public static string LoaderFor(string dataDir, string marker)
        {
            return marker + " Korean patch loader (PoB-KR-Patcher)\r\n" +
                "pcall(function() local p = GetScriptPath and GetScriptPath() or \"\"; if p == \"\" then p = \".\" end; " +
                "KR_ROOT = p .. \"/" + dataDir + "\"; dofile(KR_ROOT .. \"/init.lua\") end)\r\n";
        }
    }

    internal static class Targets
    {
        public static readonly GameTarget Poe1 = new GameTarget(
            "poe1", "PoE1", "KR", "-- [PoB-KR]",
            GameTarget.LoaderFor("KR", "-- [PoB-KR]"),
            "KR-data.zip", "Path of Building (한글)", "Path of Building Community",
            new[]
            {
                "Path of Building.exe", "PathOfBuilding.exe", "Path of Building Community.exe",
                "PathOfBuildingCommunity.exe", "Path of Building (Community Fork).exe"
            });

        public static readonly GameTarget Poe2 = new GameTarget(
            "poe2", "PoE2", "KR2", "-- [PoB-KR2]",
            GameTarget.LoaderFor("KR2", "-- [PoB-KR2]"),
            "KR-data-poe2.zip", "Path of Building PoE2 (한글)", "Path of Building Community PoE2",
            new[]
            {
                "Path of Building-PoE2.exe", "PathOfBuilding-PoE2.exe",
                "Path of Building PoE2.exe", "PathOfBuildingPoE2.exe",
                "Path of Building (PoE2).exe", "PathOfBuilding2.exe",
                "Path of Building Community (PoE2).exe", "Path of Building.exe"
            });

        public static GameTarget ById(string id)
        {
            return string.Equals(id, "poe2", StringComparison.OrdinalIgnoreCase) ? Poe2 : Poe1;
        }
    }

    /// <summary>내장 데이터(build.json / build-poe2.json) 정보.</summary>
    internal sealed class BuildInfo
    {
        public string Game = "poe1";
        public string Version = "0.0.0";
        public string Season = "";
        public string Pob = "";
        public int Files;
        public long PayloadSize;
        public string PayloadSha256 = "";

        public string Pretty
        {
            get
            {
                var extra = new List<string>();
                if (!string.IsNullOrEmpty(Pob)) extra.Add("PoB " + Pob);
                if (!string.IsNullOrEmpty(Season)) extra.Add((Game == "poe2" ? "PoE2 " : "PoE1 ") + Season);
                return extra.Count == 0 ? Version : Version + " (" + string.Join(" · ", extra.ToArray()) + ")";
            }
        }
    }

    /// <summary>사용자 설정 (%LOCALAPPDATA%\PoB-KR-Patcher\settings.json).</summary>
    internal sealed class Settings
    {
        public bool AutoCheck = true;
        public bool CreateShortcut;
        public string LastTarget = "";
        public string IgnoredNewer = "";
        public string LastTargetPoe2 = "";
        public string IgnoredNewerPoe2 = "";

        private static string Dir
        {
            get
            {
                var root = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return Path.Combine(root, "PoB-KR-Patcher");
            }
        }

        private static string PathFile { get { return Path.Combine(Dir, "settings.json"); } }

        public static Settings Load()
        {
            try
            {
                if (File.Exists(PathFile))
                {
                    var json = File.ReadAllText(PathFile, Encoding.UTF8);
                    var d = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(json);
                    var s = new Settings();
                    if (d.ContainsKey("autoCheck")) s.AutoCheck = Convert.ToBoolean(d["autoCheck"], CultureInfo.InvariantCulture);
                    if (d.ContainsKey("createShortcut")) s.CreateShortcut = Convert.ToBoolean(d["createShortcut"], CultureInfo.InvariantCulture);
                    if (d.ContainsKey("lastTarget")) s.LastTarget = Convert.ToString(d["lastTarget"], CultureInfo.InvariantCulture) ?? "";
                    if (d.ContainsKey("ignoredNewer")) s.IgnoredNewer = Convert.ToString(d["ignoredNewer"], CultureInfo.InvariantCulture) ?? "";
                    if (d.ContainsKey("lastTargetPoe2")) s.LastTargetPoe2 = Convert.ToString(d["lastTargetPoe2"], CultureInfo.InvariantCulture) ?? "";
                    if (d.ContainsKey("ignoredNewerPoe2")) s.IgnoredNewerPoe2 = Convert.ToString(d["ignoredNewerPoe2"], CultureInfo.InvariantCulture) ?? "";
                    return s;
                }
            }
            catch
            {
                // 설정 파일이 깨졌으면 기본값으로 동작한다.
            }
            return new Settings();
        }

        public string GetLastTarget(string gameId)
        {
            return string.Equals(gameId, "poe2", StringComparison.OrdinalIgnoreCase) ? LastTargetPoe2 : LastTarget;
        }

        public string GetIgnoredNewer(string gameId)
        {
            return string.Equals(gameId, "poe2", StringComparison.OrdinalIgnoreCase) ? IgnoredNewerPoe2 : IgnoredNewer;
        }

        public void SetLastTarget(string gameId, string path)
        {
            if (string.Equals(gameId, "poe2", StringComparison.OrdinalIgnoreCase)) LastTargetPoe2 = path ?? "";
            else LastTarget = path ?? "";
        }

        public void SetIgnoredNewer(string gameId, string path)
        {
            if (string.Equals(gameId, "poe2", StringComparison.OrdinalIgnoreCase)) IgnoredNewerPoe2 = path ?? "";
            else IgnoredNewer = path ?? "";
        }

        public void Save()
        {
            try
            {
                Directory.CreateDirectory(Dir);
                var d = new Dictionary<string, object>
                {
                    { "autoCheck", AutoCheck },
                    { "createShortcut", CreateShortcut },
                    { "lastTarget", LastTarget ?? "" },
                    { "ignoredNewer", IgnoredNewer ?? "" },
                    { "lastTargetPoe2", LastTargetPoe2 ?? "" },
                    { "ignoredNewerPoe2", IgnoredNewerPoe2 ?? "" }
                };
                var json = new JavaScriptSerializer().Serialize(d);
                File.WriteAllText(PathFile, json, new UTF8Encoding(false));
            }
            catch
            {
                // 설정을 저장하지 못해도 패치 자체에는 영향이 없다.
            }
        }
    }

    internal static class AppInfo
    {
        public const string Owner = "SSONG-HA";
        public const string Repo = "kor-patch";
        public const string ProjectUrl = "https://github.com/SSONG-HA/kor-patch";

        public const string LatestJsonUrl =
            "https://github.com/SSONG-HA/kor-patch/releases/latest/download/latest.json";

        public const string ApiLatestUrl =
            "https://api.github.com/repos/SSONG-HA/kor-patch/releases/latest";

        /// <summary>PoE1 표식 (예전 버전과의 호환용).</summary>
        public const string Marker = "-- [PoB-KR]";

        /// <summary>PoE1 로더 두 줄 (예전 install.ps1 과 동일).</summary>
        public static readonly string Loader = Targets.Poe1.Loader;

        public static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        public static string AppVersion
        {
            get
            {
                var v = Assembly.GetExecutingAssembly().GetName().Version;
                if (v == null) return "0.0.0";
                return string.Format(CultureInfo.InvariantCulture, "{0}.{1}.{2}", v.Major, v.Minor, Math.Max(0, v.Build));
            }
        }

        public static string ExeDir
        {
            get
            {
                try
                {
                    var loc = Assembly.GetExecutingAssembly().Location;
                    if (!string.IsNullOrEmpty(loc)) return Path.GetDirectoryName(loc);
                }
                catch
                {
                }
                return Environment.CurrentDirectory;
            }
        }

        private static BuildInfo _embedded;
        private static BuildInfo _embeddedPoe2;

        public static BuildInfo Embedded { get { return EmbeddedFor(Targets.Poe1); } }
        public static BuildInfo EmbeddedPoe2 { get { return EmbeddedFor(Targets.Poe2); } }

        public static BuildInfo EmbeddedFor(GameTarget target)
        {
            if (target.IsPoe2)
            {
                if (_embeddedPoe2 == null) _embeddedPoe2 = LoadBuildInfo("build-poe2.json", AppVersion);
                return _embeddedPoe2;
            }
            if (_embedded == null) _embedded = LoadBuildInfo("build.json", AppVersion);
            return _embedded;
        }

        private static BuildInfo LoadBuildInfo(string resource, string fallbackVersion)
        {
            var info = new BuildInfo { Version = fallbackVersion, Game = resource.Contains("poe2") ? "poe2" : "poe1" };
            try
            {
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
                {
                    if (s != null)
                    {
                        using (var r = new StreamReader(s, Encoding.UTF8))
                        {
                            var txt = r.ReadToEnd();
                            var d = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(txt);
                            info.Version = Json.Str(d, "version", info.Version);
                            info.Season = Json.Str(d, "season", "");
                            info.Pob = Json.Str(d, "pob", "");
                            info.Files = (int)Json.Num(d, "files", 0);
                            info.PayloadSize = (long)Json.Num(d, "payload_size", 0);
                            info.PayloadSha256 = Json.Str(d, "payload_sha256", "");
                        }
                    }
                }
            }
            catch
            {
                // build.json 이 없으면 어셈블리 버전으로 동작한다.
            }
            return info;
        }

        public static byte[] EmbeddedPayload() { return EmbeddedPayloadFor(Targets.Poe1); }

        public static byte[] EmbeddedPayloadFor(GameTarget target)
        {
            var name = target.IsPoe2 ? "payload-poe2.zip" : "payload.zip";
            using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (s == null)
                    throw new InvalidOperationException(
                        (target.IsPoe2 ? "PoE2 " : "PoE1 ") +
                        "한글 데이터가 이 실행 파일에 들어 있지 않습니다. Releases 에서 다시 받아 주세요.");
                using (var ms = new MemoryStream())
                {
                    s.CopyTo(ms);
                    return ms.ToArray();
                }
            }
        }

        public static string VersionLine(BuildInfo b)
        {
            var extra = new List<string>();
            if (!string.IsNullOrEmpty(b.Pob)) extra.Add("Path of Building " + b.Pob);
            if (!string.IsNullOrEmpty(b.Season)) extra.Add((b.Game == "poe2" ? "PoE2 " : "PoE1 ") + b.Season);
            return extra.Count == 0 ? b.Version : b.Version + " (" + string.Join(" · ", extra.ToArray()) + ")";
        }
    }

    /// <summary>가벼운 JSON 접근 도우미.</summary>
    internal static class Json
    {
        public static string Str(Dictionary<string, object> d, string key, string fallback)
        {
            if (d == null || !d.ContainsKey(key) || d[key] == null) return fallback;
            var s = d[key] as string;
            if (s != null) return s;
            return Convert.ToString(d[key], CultureInfo.InvariantCulture) ?? fallback;
        }

        public static double Num(Dictionary<string, object> d, string key, double fallback)
        {
            if (d == null || !d.ContainsKey(key) || d[key] == null) return fallback;
            try
            {
                return Convert.ToDouble(d[key], CultureInfo.InvariantCulture);
            }
            catch
            {
                return fallback;
            }
        }

        public static Dictionary<string, object> Obj(Dictionary<string, object> d, string key)
        {
            if (d == null || !d.ContainsKey(key)) return null;
            return d[key] as Dictionary<string, object>;
        }

        public static object[] Arr(Dictionary<string, object> d, string key)
        {
            if (d == null || !d.ContainsKey(key)) return new object[0];
            return d[key] as object[] ?? new object[0];
        }
    }

    /// <summary>버전 비교 (1.2.10 &gt; 1.2.9).</summary>
    internal static class VersionUtil
    {
        public static int[] Parse(string text)
        {
            if (string.IsNullOrEmpty(text)) return new[] { 0 };
            var s = text.Trim();
            if (s.StartsWith("v", StringComparison.OrdinalIgnoreCase)) s = s.Substring(1);
            var sb = new StringBuilder();
            foreach (var ch in s)
            {
                if ((ch >= '0' && ch <= '9') || ch == '.') sb.Append(ch);
                else break;
            }
            var parts = sb.ToString().Trim('.').Split('.');
            var list = new List<int>();
            foreach (var p in parts)
            {
                int n;
                if (int.TryParse(p, NumberStyles.Integer, CultureInfo.InvariantCulture, out n)) list.Add(n);
                else list.Add(0);
            }
            if (list.Count == 0) list.Add(0);
            return list.ToArray();
        }

        public static int Compare(string a, string b)
        {
            var x = Parse(a);
            var y = Parse(b);
            var len = Math.Max(x.Length, y.Length);
            for (var i = 0; i < len; i++)
            {
                var xi = i < x.Length ? x[i] : 0;
                var yi = i < y.Length ? y[i] : 0;
                if (xi != yi) return xi < yi ? -1 : 1;
            }
            return 0;
        }

        public static bool IsNewer(string candidate, string baseline)
        {
            return Compare(candidate, baseline) > 0;
        }
    }
}
