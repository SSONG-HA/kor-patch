using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace PoBKR
{
    internal sealed class CliOptions
    {
        public bool Apply;
        public bool Restore;
        public bool Check;
        public bool Info;
        public bool Help;
        public bool NoUpdate;
        public bool Force;
        public string Dir = "";

        public bool IsCommand
        {
            get { return Apply || Restore || Check || Info || Help; }
        }
    }

    /// <summary>--apply / --restore / --check / --info (테스트·자동화·고급 사용자용).</summary>
    internal static class Cli
    {
        public static CliOptions Parse(string[] args)
        {
            var o = new CliOptions();
            for (var i = 0; i < args.Length; i++)
            {
                var a = (args[i] ?? "").Trim();
                switch (a.ToLowerInvariant())
                {
                    case "--apply": o.Apply = true; break;
                    case "--restore": o.Restore = true; break;
                    case "--check": o.Check = true; break;
                    case "--info": o.Info = true; break;
                    case "--no-update": o.NoUpdate = true; break;
                    case "--force": o.Force = true; break;
                    case "--help":
                    case "-h":
                    case "/?":
                        o.Help = true;
                        break;
                    case "--dir":
                        if (i + 1 < args.Length) o.Dir = args[++i];
                        break;
                    default:
                        if (a.StartsWith("--dir=", StringComparison.OrdinalIgnoreCase))
                            o.Dir = a.Substring(6).Trim('"');
                        break;
                }
            }
            return o;
        }

        public static void PrintHelp()
        {
            Console.WriteLine("PoB 한글 패처 " + AppInfo.AppVersion + " — " + AppInfo.ProjectUrl);
            Console.WriteLine();
            Console.WriteLine("  (인수 없이 실행)      화면(GUI)으로 실행 — 더블클릭과 같습니다");
            Console.WriteLine("  --apply [--dir 폴더]  한글 패치 적용/재적용");
            Console.WriteLine("  --restore [--dir 폴더] 영문 원본으로 복구");
            Console.WriteLine("  --check               최신 릴리스(시즌 데이터) 확인");
            Console.WriteLine("  --info                내장 데이터/설치 상태 출력");
            Console.WriteLine("  --no-update           최신 시즌 데이터 확인 없이 내장 데이터만 사용");
            Console.WriteLine("  --force               설치된 데이터가 더 최신이어도 덮어쓰기");
            Console.WriteLine();
            Console.WriteLine("  종료 코드: 0 성공, 1 오류, 2 PoB 폴더를 찾지 못함, 3 PoB 실행 중");
        }

        private static void Say(string text)
        {
            Console.WriteLine("  " + text);
        }

        public static int Run(string[] args)
        {
            try
            {
                Console.OutputEncoding = new UTF8Encoding(false);
            }
            catch
            {
            }

            var o = Parse(args);
            if (o.Help) { PrintHelp(); return 0; }
            if (o.Info) return Info(o);
            if (o.Check) return Check();
            if (o.Restore) return Restore(o);
            if (o.Apply) return Apply(o);
            PrintHelp();
            return 0;
        }

        private static bool ResolveTarget(CliOptions o, out string target)
        {
            target = null;
            if (!string.IsNullOrEmpty(o.Dir))
            {
                if (!Installer.IsPoB(o.Dir))
                {
                    Say("[실패] Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + o.Dir);
                    return false;
                }
                target = o.Dir;
                return true;
            }
            target = Installer.FindPoB(null);
            if (target == null)
            {
                Say("[실패] Path of Building 폴더를 자동으로 찾지 못했습니다. --dir 로 폴더를 지정해 주세요.");
                return false;
            }
            return true;
        }

        private static int Info(CliOptions o)
        {
            var embed = AppInfo.Embedded;
            Say("패처 버전 : " + AppInfo.AppVersion);
            Say("내장 데이터: " + embed.Pretty + "  (파일 " + embed.Files + "개)");
            string target;
            if (ResolveTarget(o, out target))
            {
                Say("PoB 폴더  : " + target);
                Say("설치 상태 : " + (Installer.HasData(target) ? "한글 데이터 있음" : "한글 데이터 없음")
                    + (Installer.HasMarker(target) ? " / Main.lua 패치됨" : " / Main.lua 원본"));
                Say("설치 버전 : " + (Installer.InstalledVersion(target) ?? "없음"));
            }
            return 0;
        }

        private static int Check()
        {
            var rel = Updater.GetLatest(Say);
            if (rel == null) return 1;
            Say("최신 릴리스 : " + rel.Version + (string.IsNullOrEmpty(rel.Season) ? "" : " (PoE1 " + rel.Season + ")"));
            Say("데이터 주소 : " + rel.DataUrl);
            if (!string.IsNullOrEmpty(rel.DataSha256)) Say("sha256     : " + rel.DataSha256);
            if (VersionUtil.IsNewer(rel.Version, AppInfo.Embedded.Version))
                Say("→ 내장 데이터(" + AppInfo.Embedded.Version + ")보다 최신입니다.");
            else
                Say("→ 내장 데이터(" + AppInfo.Embedded.Version + ")가 최신입니다.");
            return 0;
        }

        private static int Apply(CliOptions o)
        {
            string target;
            if (!ResolveTarget(o, out target)) return 2;
            if (Installer.IsPoBRunning())
            {
                Say("[중지] Path of Building 이 실행 중입니다. 닫고 다시 실행해 주세요.");
                return 3;
            }
            Say("Path of Building: " + target);

            var embed = AppInfo.Embedded;
            var data = embed;
            byte[] payload = null;
            var installed = Installer.InstalledVersion(target);
            Say("내장 데이터: " + embed.Pretty + " / 설치됨: " + (installed ?? "없음"));

            if (!o.NoUpdate)
            {
                var rel = Updater.GetLatest(Say);
                if (rel != null && VersionUtil.IsNewer(rel.Version, embed.Version))
                {
                    try
                    {
                        payload = Updater.DownloadData(rel, Say);
                        data = rel.ToBuildInfo();
                    }
                    catch (Exception ex)
                    {
                        Say("시즌 데이터를 받지 못해 내장 데이터로 진행합니다: " + ex.Message);
                        payload = null;
                        data = embed;
                    }
                }
            }

            if (!o.Force && installed != null && VersionUtil.IsNewer(installed, data.Version))
            {
                Say("설치된 데이터(" + installed + ")가 더 최신입니다. 덮어쓰지 않았습니다. (--force 로 강제)");
                return 0;
            }

            if (payload == null) payload = AppInfo.EmbeddedPayload();
            var r = Installer.Apply(target, payload, data);
            if (!r.Ok)
            {
                Say("[실패] " + r.Error);
                return 1;
            }
            Say("한글 패치 적용 완료: " + r.VersionText);
            if (r.AlreadyPatched) Say("Modules\\Main.lua 는 이미 패치되어 있었습니다 (데이터만 갱신).");
            if (r.BackedUp) Say("원본 백업: KR\\_설치기록\\Main.lua.orig");
            Say("Path of Building 을 실행하세요. 게임 안에서는 F2 로 한/영 전환이 됩니다.");
            return 0;
        }

        private static int Restore(CliOptions o)
        {
            string target;
            if (!ResolveTarget(o, out target)) return 2;
            if (Installer.IsPoBRunning())
            {
                Say("[중지] Path of Building 이 실행 중입니다. 닫고 다시 실행해 주세요.");
                return 3;
            }
            Say("Path of Building: " + target);
            var r = Installer.Restore(target);
            if (!r.Ok)
            {
                Say("[실패] " + (string.IsNullOrEmpty(r.Error) ? "복구를 확인하지 못했습니다." : r.Error));
                return 1;
            }
            if (r.RestoredFromBackup) Say("Modules\\Main.lua 를 백업본으로 되돌렸습니다.");
            else if (r.RemovedLoader) Say("로더 줄을 제거했습니다.");
            else Say("이미 영문 원본 상태였습니다.");
            if (r.KrRemoved) Say("KR 폴더를 삭제했습니다.");
            return 0;
        }
    }
}
