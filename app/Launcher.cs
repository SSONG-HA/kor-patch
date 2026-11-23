using System;
using System.Diagnostics;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace PoBKR
{
    /// <summary>--launch / --bg-update / --apply-staged 인수.</summary>
    internal sealed class LaunchOptions
    {
        public string Dir = "";
        public string GameId = "poe1";
        public bool NoUpdate;
        public bool NoStart;
        public bool Quiet;
        public bool Help;

        public GameTarget Game { get { return Targets.ById(GameId); } }

        private static string NormalizeGame(string value)
        {
            var v = (value ?? "").Trim().Trim('"').ToLowerInvariant();
            if (v == "poe2" || v == "2" || v == "pob2" || v == "pathofbuilding-poe2") return "poe2";
            return "poe1";
        }

        public static LaunchOptions Parse(string[] args)
        {
            var o = new LaunchOptions();
            if (args == null) return o;
            for (var i = 0; i < args.Length; i++)
            {
                var a = (args[i] ?? "").Trim();
                var low = a.ToLowerInvariant();
                if (low == "--launch" || low == "--bg-update" || low == "--apply-staged") continue;
                if (low == "--no-update") { o.NoUpdate = true; continue; }
                if (low == "--no-start" || low == "--dry-run") { o.NoStart = true; continue; }
                if (low == "--quiet" || low == "--silent") { o.Quiet = true; continue; }
                if (low == "--help" || low == "-h" || low == "/?") { o.Help = true; continue; }
                if (low == "--dir")
                {
                    if (i + 1 < args.Length) o.Dir = (args[++i] ?? "").Trim().Trim('"');
                    continue;
                }
                if (low == "--game")
                {
                    if (i + 1 < args.Length) o.GameId = NormalizeGame(args[++i]);
                    continue;
                }
                if (low.StartsWith("--game=", StringComparison.Ordinal))
                {
                    o.GameId = NormalizeGame(a.Substring("--game=".Length));
                    continue;
                }
                if (low.StartsWith("--dir=", StringComparison.Ordinal))
                {
                    o.Dir = a.Substring("--dir=".Length).Trim().Trim('"');
                    continue;
                }
                if (a.StartsWith("--", StringComparison.Ordinal)) continue;
                if (o.Dir.Length == 0) o.Dir = a.Trim('"');
            }
            return o;
        }
    }

    /// <summary>런처가 정한 PoB 폴더.</summary>
    internal sealed class LaunchPlan
    {
        public string Target = "";
        public string Error = "";
        public bool AlreadyRunning;
    }

    internal sealed class LaunchResult
    {
        public bool Ok;             // 실행 파일을 찾아 띄울 수 있는 상태
        public bool AlreadyRunning;
        public bool Patched;        // 이번 실행에서 데이터/로더를 갱신했는지
        public string Target = "";
        public string ExePath = "";
        public string VersionText = "";
        public string Error = "";
    }

    /// <summary>
    /// 세 가지 모드:
    ///  --launch       창 없이 빠르게 패치 확인·적용 후 PoB 실행 (바로가기가 부르는 모드)
    ///  --bg-update    PoB 가 직접 실행됐을 때 뒤에서 조용히 최신 패치를 받아 두기 (KR\init.lua 가 부름)
    ///  --apply-staged 미리 받아 둔 패치를 KR 에 반영 (다음 PoB 시작 때 init.lua 가 데이터 로드 전에 부름)
    /// </summary>
    internal static class Launcher
    {
        private const int FastTimeoutSeconds = 4;

        public static int Run(string[] args)
        {
            var mode = args != null && args.Length > 0 ? (args[0] ?? "").Trim().ToLowerInvariant() : "";
            if (mode == "--bg-update") return BackgroundUpdate(args);
            if (mode == "--apply-staged") return ApplyStagedMode(args);
            return LaunchMode(args);
        }

        // ── --launch ──────────────────────────────────────────────────────────
        private static int LaunchMode(string[] args)
        {
            var opts = LaunchOptions.Parse(args);

            if (opts.Help)
            {
                RaiseConsole();
                Console.WriteLine("PoB-KR-Patcher.exe --launch [\"PoB 폴더\"] [--no-update] [--no-start]");
                Console.WriteLine();
                Console.WriteLine("  --launch       새 한글 패치를 확인·적용한 뒤 Path of Building 을 실행합니다 (창 없음)");
                Console.WriteLine("  --bg-update    뒤에서 조용히 최신 패치를 미리 받아 둡니다 (PoB 실행 중에도 안전)");
                Console.WriteLine("  --apply-staged 미리 받아 둔 패치를 지금 반영합니다");
                Console.WriteLine("  --no-update    새 릴리스 확인 없이 지금 있는 데이터로만 확인·재패치");
                Console.WriteLine("  --no-start     패치까지만 하고 PoB 는 실행하지 않음 (테스트용)");
                Console.WriteLine("  종료 코드: 0 성공, 1 오류, 2 PoB 폴더를 찾지 못함");
                return 0;
            }

            if (opts.NoStart)
            {
                // 테스트/자동화: 콘솔에만 출력하고 창은 띄우지 않는다.
                var plan0 = Resolve(opts, null);
                if (plan0.AlreadyRunning)
                {
                    Console.WriteLine("  Path of Building 이 이미 실행 중입니다.");
                    return 0;
                }
                if (plan0.Error.Length > 0)
                {
                    Console.WriteLine("  [실패] " + plan0.Error);
                    return 2;
                }
                var done = Maintain(opts, plan0, Say);
                Report(done);
                return done.Ok ? 0 : 1;
            }

            Program.HideConsole();
            try
            {
                Program.MakeDpiAware();
            }
            catch
            {
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            LaunchResult result = null;
            using (var host = new LaunchHost(opts))
            {
                Application.Run(host);
                result = host.Result;
            }
            if (result == null) result = new LaunchResult { Error = "알 수 없는 오류로 중단되었습니다." };

            if (result.AlreadyRunning)
            {
                MessageBox.Show("Path of Building 이 이미 실행 중입니다.",
                    "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return 0;
            }

            if (!string.IsNullOrEmpty(result.Error))
            {
                var text = result.Error;
                if (result.Ok) text += "\n\nPath of Building 은 지금 상태(이전 한글 패치/영문)로 실행합니다.";
                MessageBox.Show(text, "PoB 한글 패처", MessageBoxButtons.OK,
                    result.Ok ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
            }

            if (result.Ok)
            {
                StartPoB(result);
                return 0;
            }
            return result.Target.Length == 0 ? 2 : 1;
        }

        // ── --bg-update : PoB 본체를 직접 실행했을 때 뒤에서 미리 받아 두기 ──────
        private static int BackgroundUpdate(string[] args)
        {
            Program.HideConsole();
            var opts = LaunchOptions.Parse(args);
            var game = opts.Game;
            var target = ResolveQuiet(opts);
            if (target.Length == 0) return 2;

            var checkedAt = Installer.NowUnix();
            var upToDate = true;

            try
            {
                if (Installer.IsPoBRunning())
                {
                    // PoB 가 KR 파일을 쓰고 있는 중 — 살아 있는 파일은 건드리지 않고 KR\_update 에 넣어 둔다.
                    var rel = Updater.GetLatestQuiet(FastTimeoutSeconds, game);
                    if (rel != null)
                    {
                        var installed = Installer.InstalledVersion(target, game) ?? "0.0.0";
                        var baseline = Higher(installed, AppInfo.EmbeddedFor(game).Version);
                        if (VersionUtil.IsNewer(rel.Version, baseline))
                        {
                            upToDate = false;
                            try
                            {
                                var payload = Updater.DownloadData(rel, null);
                                if (Installer.Stage(target, payload, AppInfo.VersionLine(rel.ToBuildInfo()), game))
                                    upToDate = true;
                            }
                            catch
                            {
                                // 느리거나 끊긴 연결 — 1시간 뒤에 다시 시도한다.
                            }
                        }
                    }
                    else
                    {
                        upToDate = false;
                    }
                }
                else
                {
                    // PoB 가 꺼져 있으면 바로 적용해도 안전하다.
                    var r = Maintain(opts, target, null);
                    upToDate = r.Ok && string.IsNullOrEmpty(r.Error);
                }
            }
            catch
            {
                upToDate = false;
            }

            // 다음 확인 시각을 남긴다 (정상: 6시간 뒤, 실패: 1시간 뒤).
            Installer.WriteLastCheck(target, upToDate ? checkedAt : checkedAt - (BackgroundIntervalHours - RetryHours) * 3600L, game);
            return upToDate ? 0 : 1;
        }

        // ── --apply-staged : 미리 받아 둔 패치를 지금 반영 ──────────────────────
        private static int ApplyStagedMode(string[] args)
        {
            Program.HideConsole();
            var opts = LaunchOptions.Parse(args);
            var game = opts.Game;
            var target = ResolveQuiet(opts);
            if (target.Length == 0) return 2;
            if (!Installer.HasPending(target, game)) return 0;

            string version;
            if (!Installer.ApplyStaged(target, out version, game)) return 1;
            if (!opts.Quiet) Console.WriteLine("  한글 패치 반영: " + version);
            return 0;
        }

        public const int BackgroundIntervalHours = 6;
        public const int RetryHours = 1;

        private static void RaiseConsole()
        {
            try
            {
                Console.OutputEncoding = new System.Text.UTF8Encoding(false);
            }
            catch
            {
            }
        }

        private static void Say(string line)
        {
            Console.WriteLine("  " + line);
        }

        private static void Report(LaunchResult r)
        {
            if (r.Patched) Say("한글 패치 준비 완료: " + (r.VersionText.Length == 0 ? "갱신됨" : r.VersionText));
            else if (r.VersionText.Length > 0) Say("이미 최신: " + r.VersionText);
            if (r.Ok) Say("실행 파일: " + r.ExePath);
            if (r.Error.Length > 0) Say("[안내] " + r.Error);
        }

        /// <summary>창 없이 쓸 PoB 폴더 결정: 실행 중인 PoB → 마지막 폴더 → 자동 탐색.</summary>
        private static string ResolveQuiet(LaunchOptions opts)
        {
            if (!string.IsNullOrEmpty(opts.Dir))
            {
                if (Installer.IsPoB(opts.Dir)) return Installer.Clean(opts.Dir);
                return "";
            }
            var running = Installer.FindRunningPoBFolder();
            if (running != null)
            {
                Remember(running, opts.Game);
                return running;
            }
            var settings = Settings.Load();
            var last = settings.GetLastTarget(opts.GameId);
            if (Installer.IsPoB(last)) return Installer.Clean(last);
            var found = Installer.FindPoB(null, opts.Game);
            return found ?? "";
        }

        private static void Remember(string target, GameTarget game)
        {
            try
            {
                var settings = Settings.Load();
                if (!string.Equals(settings.GetLastTarget(game.Id), target, StringComparison.OrdinalIgnoreCase))
                {
                    settings.SetLastTarget(game.Id, target);
                    settings.Save();
                }
            }
            catch
            {
            }
        }

        /// <summary>PoB 폴더 결정. last_target → (더 최신 폴더가 있으면 확인) → 자동 탐색.</summary>
        public static LaunchPlan Resolve(LaunchOptions opts, Func<string, bool> ask)
        {
            var plan = new LaunchPlan();
            if (!string.IsNullOrEmpty(opts.Dir))
            {
                if (Installer.IsPoB(opts.Dir))
                {
                    plan.Target = Installer.Clean(opts.Dir);
                    return plan;
                }
                plan.Error = "Path of Building 폴더가 아닙니다 (Modules\\Main.lua 없음): " + opts.Dir;
                return plan;
            }

            if (Installer.IsPoBRunning())
            {
                plan.AlreadyRunning = true;
                return plan;
            }

            var game = opts.Game;
            var settings = Settings.Load();
            var last = settings.GetLastTarget(game.Id) ?? "";
            if (last.Length > 0 && !Installer.IsPoB(last)) last = "";

            var newer = NewerCandidate(last, settings.GetIgnoredNewer(game.Id), game);
            if (last.Length > 0 && newer != null && ask != null)
            {
                var useNew = ask("새로 내려받은 Path of Building 폴더를 발견했습니다.\n\n" + newer
                    + "\n\n이 폴더를 앞으로 사용할까요?\n[아니오] 를 누르면 기존 폴더를 계속 씁니다.\n(" + last + ")");
                if (useNew)
                {
                    plan.Target = newer;
                }
                else
                {
                    plan.Target = last;
                    settings.SetIgnoredNewer(game.Id, newer);
                    settings.Save();
                }
            }
            else if (last.Length > 0)
            {
                plan.Target = last;
            }
            else if (newer != null)
            {
                plan.Target = newer;
            }

            if (plan.Target.Length == 0)
            {
                var found = Installer.FindPoB(null, game);
                if (found != null) plan.Target = found;
            }

            if (plan.Target.Length == 0)
            {
                plan.Error = "Path of Building 폴더를 찾지 못했습니다.\n\nPoB 를 설치했는지 확인해 주세요. "
                    + "설치 위치가 다르면 PoB-KR-Patcher.exe 를 실행해 [폴더 선택...] 으로 한 번만 지정하면 됩니다.";
                return plan;
            }

            if (!string.Equals(settings.GetLastTarget(game.Id), plan.Target, StringComparison.OrdinalIgnoreCase))
            {
                settings.SetLastTarget(game.Id, plan.Target);
                settings.Save();
            }
            return plan;
        }

        /// <summary>마지막으로 쓰던 폴더보다 확실히 더 최신인 PoB 폴더 (바탕화면·다운로드 등).</summary>
        private static string NewerCandidate(string lastTarget, string ignored, GameTarget game)
        {
            var candidates = Installer.FindPoBCandidates(2);
            if (candidates.Count == 0) return null;

            var lastTime = Installer.MainLuaTime(lastTarget);
            foreach (var c in candidates)
            {
                if (string.Equals(c, lastTarget, StringComparison.OrdinalIgnoreCase)) continue;
                if (!string.IsNullOrEmpty(ignored) && string.Equals(c, ignored, StringComparison.OrdinalIgnoreCase)) continue;
                var t = Installer.MainLuaTime(c);
                if (lastTime == DateTime.MinValue || t > lastTime.AddSeconds(45)) return c;
            }
            return null;
        }

        /// <summary>패치 확인·적용. 예외를 던지지 않고 결과로 알려 준다.</summary>
        public static LaunchResult Maintain(LaunchOptions opts, string target, Action<string> progress)
        {
            return Maintain(opts, new LaunchPlan { Target = target }, progress);
        }

        public static LaunchResult Maintain(LaunchOptions opts, LaunchPlan plan, Action<string> progress)
        {
            var result = new LaunchResult { Target = plan.Target ?? "" };
            var say = progress ?? delegate(string s) { };
            if (plan.AlreadyRunning)
            {
                result.AlreadyRunning = true;
                return result;
            }
            if (result.Target.Length == 0)
            {
                result.Error = plan.Error.Length > 0 ? plan.Error : "Path of Building 폴더를 찾지 못했습니다.";
                return result;
            }

            var game = opts.Game;
            try
            {
                var embed = AppInfo.EmbeddedFor(game);
                var installed = Installer.InstalledVersion(result.Target, game);
                var hasData = Installer.HasData(result.Target, game);
                result.VersionText = installed ?? "";

                // (0) 미리 받아 둔 패치가 있으면 먼저 반영한다. (PoB 는 아직 실행 전이다)
                if (Installer.HasPending(result.Target, game))
                {
                    say("받아 둔 한글 패치를 반영하는 중...");
                    string stagedVersion;
                    if (Installer.ApplyStaged(result.Target, out stagedVersion, game))
                    {
                        result.Patched = true;
                        result.VersionText = stagedVersion;
                        installed = stagedVersion.Length > 0 ? stagedVersion : installed;
                        hasData = Installer.HasData(result.Target, game);
                    }
                }

                byte[] payload = null;
                var data = embed;

                // (1) 새 패치 확인 (짧은 타임아웃)
                if (!opts.NoUpdate)
                {
                    try
                    {
                        say("새 한글 패치 확인 중...");
                        var rel = Updater.GetLatestQuiet(FastTimeoutSeconds, game);
                        var baseline = Higher(installed ?? "0.0.0", embed.Version);
                        if (rel != null && VersionUtil.IsNewer(rel.Version, baseline))
                        {
                            say("새 한글 패치 내려받는 중... (" + rel.Version + ")");
                            try
                            {
                                payload = Updater.DownloadData(rel, null);
                                data = rel.ToBuildInfo();
                            }
                            catch
                            {
                                // 느리거나 끊긴 연결 — 지금 있는 데이터로 그대로 진행한다.
                                payload = null;
                                data = embed;
                            }
                        }
                    }
                    catch
                    {
                        // 네트워크 확인 실패는 무시하고 로컬 패치로 진행한다.
                        payload = null;
                        data = embed;
                    }
                }

                // (2) 데이터가 아예 없으면 내장 데이터로 채운다.
                if (payload == null && !hasData)
                {
                    try
                    {
                        payload = AppInfo.EmbeddedPayloadFor(game);
                        data = embed;
                    }
                    catch (Exception ex)
                    {
                        result.Error = ex.Message;
                    }
                }

                // (3) 적용 또는 로더 재삽입
                if (payload != null)
                {
                    say("한글 패치 적용 중...");
                    var applied = Installer.Apply(result.Target, payload, data, game);
                    if (applied.Ok)
                    {
                        result.Patched = true;
                        result.VersionText = applied.VersionText;
                    }
                    else
                    {
                        result.Error = applied.Error;
                    }
                }
                else if (!Installer.HasMarker(result.Target, game))
                {
                    say("PoB 업데이트로 지워진 한글 로더를 다시 넣는 중...");
                    if (Installer.EnsureLoader(result.Target, game)) result.Patched = true;
                    else if (result.Error.Length == 0) result.Error = "Modules\\Main.lua 에 한글 로더를 넣지 못했습니다.";
                }

                if (!Installer.HasMarker(result.Target, game) && result.Error.Length == 0)
                    result.Error = "Modules\\Main.lua 에 한글 로더가 없습니다. 관리자 권한으로 한 번 실행해 주세요.";
            }
            catch (Exception ex)
            {
                result.Error = Short(ex);
            }

            var exe = Installer.FindPoBExe(result.Target, game);
            if (string.IsNullOrEmpty(exe))
            {
                if (result.Error.Length == 0) result.Error = "Path of Building 실행 파일을 찾지 못했습니다.\n(" + result.Target + ")";
            }
            else
            {
                result.ExePath = exe;
                result.Ok = true;
            }
            return result;
        }

        /// <summary>PoB 를 실행하고 런처는 끝난다.</summary>
        public static bool StartPoB(LaunchResult result)
        {
            try
            {
                var psi = new ProcessStartInfo(result.ExePath) { UseShellExecute = true };
                if (!string.IsNullOrEmpty(result.Target)) psi.WorkingDirectory = result.Target;
                Process.Start(psi);
                return true;
            }
            catch (Exception ex)
            {
                MessageBox.Show("Path of Building 을 실행하지 못했습니다.\n\n" + Short(ex),
                    "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
        }

        /// <summary>예/아니오 질문 (런처 진행 중 잠깐 뜨는 확인 창).</summary>
        public static bool AskQuestion(string message)
        {
            using (var owner = new Form
            {
                FormBorderStyle = FormBorderStyle.None,
                StartPosition = FormStartPosition.CenterScreen,
                Size = new Size(1, 1),
                ShowInTaskbar = false,
                TopMost = true,
                Opacity = 0
            })
            {
                owner.Show();
                owner.Activate();
                var answer = MessageBox.Show(owner, message, "PoB 한글 패처",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
                return answer == DialogResult.Yes;
            }
        }

        private static string Higher(string a, string b)
        {
            return VersionUtil.IsNewer(a, b) ? a : b;
        }

        private static string Short(Exception ex)
        {
            var e = ex;
            while (e.InnerException != null) e = e.InnerException;
            return e.Message;
        }

        /// <summary>
        /// 앱 본체(form)는 화면 밖 1x1 로 숨겨 두고, 실제 작업은 배경 스레드에서 한다.
        /// 작업이 1초를 넘기면 작은 알림 창을 띄워 진행 상황만 보여 준다.
        /// </summary>
        private sealed class LaunchHost : Form
        {
            private readonly LaunchOptions _opts;
            private readonly Timer _timer;
            private readonly Stopwatch _clock = new Stopwatch();
            private Task<LaunchResult> _task;
            private LaunchPlan _plan;
            private SplashForm _splash;
            private string _progressText = "한글 패치 확인 중...";

            public LaunchResult Result;

            public LaunchHost(LaunchOptions opts)
            {
                _opts = opts;
                Text = "PoB 한글 패처";
                FormBorderStyle = FormBorderStyle.None;
                StartPosition = FormStartPosition.Manual;
                Location = new Point(-4000, -4000);
                Size = new Size(1, 1);
                ShowInTaskbar = false;
                Opacity = 0;
                _timer = new Timer();
                _timer.Interval = 120;
                _timer.Tick += OnTick;
            }

            protected override void OnShown(EventArgs e)
            {
                base.OnShown(e);
                _clock.Start();
                try
                {
                    _plan = Launcher.Resolve(_opts, Ask);
                }
                catch (Exception ex)
                {
                    _plan = new LaunchPlan { Error = Short(ex) };
                }

                if (_plan.AlreadyRunning || _plan.Error.Length > 0)
                {
                    Result = new LaunchResult
                    {
                        AlreadyRunning = _plan.AlreadyRunning,
                        Error = _plan.Error,
                        Target = _plan.Target
                    };
                    BeginInvoke((Action)Close);
                    return;
                }

                _task = Task.Run(delegate { return Launcher.Maintain(_opts, _plan, Progress); });
                _timer.Start();
            }

            private bool Ask(string message)
            {
                if (IsDisposed) return false;
                try
                {
                    if (InvokeRequired) return (bool)Invoke((Func<string, bool>)AskQuestion, message);
                    return AskQuestion(message);
                }
                catch
                {
                    return false;
                }
            }

            private void Progress(string text)
            {
                if (string.IsNullOrEmpty(text)) return;
                _progressText = text;
                if (IsDisposed || !IsHandleCreated) return;
                try
                {
                    BeginInvoke((Action)delegate
                    {
                        if (_splash != null) _splash.SetText(_progressText);
                    });
                }
                catch
                {
                }
            }

            private void OnTick(object sender, EventArgs e)
            {
                if (_task == null) return;
                if (!_task.IsCompleted)
                {
                    if (_splash == null && _clock.ElapsedMilliseconds > 900) ShowSplash();
                    return;
                }
                _timer.Stop();
                try
                {
                    Result = _task.Result;
                }
                catch (Exception ex)
                {
                    Result = new LaunchResult
                    {
                        Target = _plan != null ? _plan.Target : "",
                        Error = Short(ex)
                    };
                }
                HideSplash();
                Close();
            }

            private void ShowSplash()
            {
                try
                {
                    _splash = new SplashForm(_progressText);
                    _splash.Show();
                }
                catch
                {
                    _splash = null;
                }
            }

            private void HideSplash()
            {
                if (_splash == null) return;
                try
                {
                    _splash.Close();
                }
                catch
                {
                }
                _splash = null;
            }
        }

        /// <summary>1~2초짜리 가벼운 진행 알림.</summary>
        private sealed class SplashForm : Form
        {
            private readonly Label _label;

            public SplashForm(string text)
            {
                FormBorderStyle = FormBorderStyle.None;
                StartPosition = FormStartPosition.CenterScreen;
                Size = new Size(340, 74);
                ShowInTaskbar = false;
                TopMost = true;
                BackColor = Color.FromArgb(34, 36, 42);
                _label = new Label
                {
                    Text = text,
                    ForeColor = Color.White,
                    Font = new Font("Malgun Gothic", 10f),
                    Dock = DockStyle.Fill,
                    TextAlign = ContentAlignment.MiddleCenter
                };
                Controls.Add(_label);
            }

            protected override void OnPaint(PaintEventArgs e)
            {
                base.OnPaint(e);
                using (var pen = new Pen(Color.FromArgb(62, 64, 72)))
                {
                    e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
                }
            }

            public void SetText(string text)
            {
                if (IsDisposed) return;
                _label.Text = text;
            }
        }
    }
}
