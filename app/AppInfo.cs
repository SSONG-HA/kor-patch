using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

namespace PoBKR
{
    /// <summary>내장 데이터(build.json) 정보.</summary>
    internal sealed class BuildInfo
    {
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
                if (!string.IsNullOrEmpty(Season)) extra.Add("PoE1 " + Season);
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
                    return s;
                }
            }
            catch
            {
                // 설정 파일이 깨졌으면 기본값으로 동작한다.
            }
            return new Settings();
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
                    { "ignoredNewer", IgnoredNewer ?? "" }
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

        /// <summary>Modules\Main.lua 에 들어가는 표식 (install.ps1 과 동일).</summary>
        public const string Marker = "-- [PoB-KR]";

        /// <summary>install.ps1 이 넣는 로더 두 줄과 완전히 같은 문자열.</summary>
        public static readonly string Loader =
            "-- [PoB-KR] Korean patch loader (PoB-KR-Patcher)\r\n" +
            "pcall(function() local p = GetScriptPath and GetScriptPath() or \"\"; if p == \"\" then p = \".\" end; " +
            "KR_ROOT = p .. \"/KR\"; dofile(KR_ROOT .. \"/init.lua\") end)\r\n";

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

        public static BuildInfo Embedded
        {
            get
            {
                if (_embedded == null) _embedded = LoadBuildInfo();
                return _embedded;
            }
        }

        private static BuildInfo LoadBuildInfo()
        {
            var info = new BuildInfo { Version = AppVersion };
            try
            {
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("build.json"))
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

        public static byte[] EmbeddedPayload()
        {
            using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            {
                if (s == null) throw new InvalidOperationException("이 실행 파일에 한글 데이터가 들어 있지 않습니다. Releases 에서 다시 받아 주세요.");
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
            if (!string.IsNullOrEmpty(b.Season)) extra.Add("PoE1 " + b.Season);
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
