using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace PoBKR
{
    internal sealed class ReleaseInfo
    {
        public string Version = "";
        public string Season = "";
        public string Pob = "";
        public string Notes = "";
        public string DataUrl = "";
        public long DataSize;
        public string DataSha256 = "";
        public string ExeUrl = "";
        public string Source = "";

        public BuildInfo ToBuildInfo()
        {
            return new BuildInfo
            {
                Version = Version,
                Season = Season,
                Pob = Pob,
                PayloadSize = DataSize,
                PayloadSha256 = DataSha256
            };
        }
    }

    /// <summary>릴리스(latest.json 또는 GitHub API) 확인 + 시즌 데이터 다운로드.</summary>
    internal static class Updater
    {
        private const int MaxDataBytes = 96 * 1024 * 1024;

        private static HttpClient NewClient(int timeoutSeconds)
        {
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            var client = new HttpClient { Timeout = TimeSpan.FromSeconds(timeoutSeconds) };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("PoB-KR-Patcher/" + AppInfo.AppVersion);
            client.DefaultRequestHeaders.Accept.ParseAdd("application/json");
            return client;
        }

        /// <summary>최신 릴리스 정보. 네트워크/릴리스가 없으면 null + log 에 이유.</summary>
        public static ReleaseInfo GetLatest(Action<string> log)
        {
            var fromJson = TryLatestJson(log);
            if (fromJson != null) return fromJson;
            var fromApi = TryApi(log);
            if (fromApi != null) return fromApi;
            if (log != null) log("최신 버전 정보를 받지 못했습니다. (인터넷 연결 또는 GitHub 상태 확인)");
            return null;
        }

        /// <summary>짧은 시간 안에 latest.json 만 확인한다 (API 대체 경로 없음). 실패하면 null.</summary>
        public static ReleaseInfo GetLatestQuiet(int timeoutSeconds)
        {
            return TryLatestJson(null, timeoutSeconds);
        }

        private static ReleaseInfo TryLatestJson(Action<string> log, int timeoutSeconds = 12)
        {
            try
            {
                if (timeoutSeconds <= 0) timeoutSeconds = 12;
                using (var client = NewClient(timeoutSeconds))
                {
                    var text = client.GetStringAsync(AppInfo.LatestJsonUrl).GetAwaiter().GetResult();
                    var d = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(text);
                    if (d == null || !d.ContainsKey("version")) return null;
                    var info = new ReleaseInfo
                    {
                        Version = Json.Str(d, "version", ""),
                        Season = Json.Str(d, "season", ""),
                        Pob = Json.Str(d, "pob", ""),
                        Notes = Json.Str(d, "notes", ""),
                        Source = "latest.json"
                    };
                    var data = Json.Obj(d, "data");
                    if (data != null)
                    {
                        info.DataUrl = Json.Str(data, "url", "");
                        info.DataSize = (long)Json.Num(data, "size", 0);
                        info.DataSha256 = Json.Str(data, "sha256", "");
                    }
                    var exe = Json.Obj(d, "exe");
                    if (exe != null) info.ExeUrl = Json.Str(exe, "url", "");
                    if (string.IsNullOrEmpty(info.Version)) return null;
                    if (string.IsNullOrEmpty(info.DataUrl))
                        info.DataUrl = AppInfo.ProjectUrl + "/releases/latest/download/KR-data.zip";
                    return info;
                }
            }
            catch (Exception ex)
            {
                if (log != null) log("latest.json 확인 실패: " + Short(ex));
                return null;
            }
        }

        private static ReleaseInfo TryApi(Action<string> log)
        {
            try
            {
                using (var client = NewClient(12))
                {
                    var text = client.GetStringAsync(AppInfo.ApiLatestUrl).GetAwaiter().GetResult();
                    var d = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(text);
                    var tag = Json.Str(d, "tag_name", "");
                    if (string.IsNullOrEmpty(tag)) return null;
                    var info = new ReleaseInfo
                    {
                        Version = tag.TrimStart('v', 'V'),
                        Notes = Json.Str(d, "body", ""),
                        Source = "GitHub API"
                    };
                    foreach (var item in Json.Arr(d, "assets"))
                    {
                        var a = item as Dictionary<string, object>;
                        if (a == null) continue;
                        var name = Json.Str(a, "name", "");
                        if (string.Equals(name, "KR-data.zip", StringComparison.OrdinalIgnoreCase))
                        {
                            info.DataUrl = Json.Str(a, "browser_download_url", "");
                            info.DataSize = (long)Json.Num(a, "size", 0);
                            var digest = Json.Str(a, "digest", "");
                            if (digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase))
                                info.DataSha256 = digest.Substring(7);
                        }
                        else if (string.Equals(name, "PoB-KR-Patcher.exe", StringComparison.OrdinalIgnoreCase))
                        {
                            info.ExeUrl = Json.Str(a, "browser_download_url", "");
                        }
                    }
                    return info;
                }
            }
            catch (Exception ex)
            {
                if (log != null) log("GitHub API 확인 실패: " + Short(ex));
                return null;
            }
        }

        /// <summary>KR-data.zip 다운로드 (+sha256 검증).</summary>
        public static byte[] DownloadData(ReleaseInfo release, Action<string> log)
        {
            if (release == null || string.IsNullOrEmpty(release.DataUrl))
                throw new InvalidOperationException("내려받을 시즌 데이터 주소가 없습니다.");
            if (log != null) log("시즌 데이터 내려받는 중: " + release.Version);

            byte[] bytes;
            using (var client = NewClient(120))
            {
                using (var resp = client.GetAsync(release.DataUrl, HttpCompletionOption.ResponseHeadersRead).GetAwaiter().GetResult())
                {
                    if (!resp.IsSuccessStatusCode)
                        throw new InvalidOperationException("내려받기 실패 (HTTP " + (int)resp.StatusCode + ")");
                    var length = resp.Content.Headers.ContentLength;
                    if (length.HasValue && length.Value > MaxDataBytes)
                        throw new InvalidOperationException("데이터가 너무 큽니다: " + length.Value + " bytes");
                    using (var stream = resp.Content.ReadAsStreamAsync().GetAwaiter().GetResult())
                    using (var ms = new MemoryStream())
                    {
                        var buffer = new byte[81920];
                        int read;
                        while ((read = stream.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            ms.Write(buffer, 0, read);
                            if (ms.Length > MaxDataBytes) throw new InvalidOperationException("데이터가 너무 큽니다.");
                        }
                        bytes = ms.ToArray();
                    }
                }
            }

            if (bytes.Length < 1024) throw new InvalidOperationException("받은 데이터가 비어 있습니다.");

            if (!string.IsNullOrEmpty(release.DataSha256))
            {
                var actual = Sha256Hex(bytes);
                if (!string.Equals(actual, release.DataSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("데이터 검증 실패 (sha256 불일치)");
            }
            if (log != null) log(string.Format(CultureInfo.InvariantCulture, "내려받음: {0:N0} bytes", bytes.Length));
            return bytes;
        }

        public static string Sha256Hex(byte[] bytes)
        {
            using (var sha = SHA256.Create())
            {
                var hash = sha.ComputeHash(bytes);
                var sb = new StringBuilder(hash.Length * 2);
                foreach (var b in hash) sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
                return sb.ToString();
            }
        }

        public static string Sha256File(string path)
        {
            using (var sha = SHA256.Create())
            using (var fs = File.OpenRead(path))
            {
                var hash = sha.ComputeHash(fs);
                var sb = new StringBuilder(hash.Length * 2);
                foreach (var b in hash) sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
                return sb.ToString();
            }
        }

        private static string Short(Exception ex)
        {
            var e = ex;
            while (e.InnerException != null) e = e.InnerException;
            return e.Message;
        }
    }
}
