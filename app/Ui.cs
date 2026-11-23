using System;
using System.Diagnostics;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace PoBKR
{
    internal sealed class MainForm : Form
    {
        private readonly Settings _settings;
        private readonly string _initialTarget;

        private TextBox _log;
        private Button _btnCheck;
        private CheckBox _auto;
        private CheckBox _shortcut;
        private Label _status;
        private ProgressBar _bar;
        private bool _busy;

        private readonly TargetSection _poe1;
        private readonly TargetSection _poe2;

        private sealed class TargetSection
        {
            public GameTarget Target;
            public TextBox Path;
            public Button Browse;
            public Button Apply;
            public Button Launch;
            public Button Restore;
            public Label Info;
        }

        public MainForm(string initialTarget)
        {
            _settings = Settings.Load();
            _initialTarget = initialTarget ?? "";
            _poe1 = new TargetSection { Target = Targets.Poe1 };
            _poe2 = new TargetSection { Target = Targets.Poe2 };
            BuildUi();
        }

        private void BuildUi()
        {
            Text = "PoB 한글 패처 (PoE1 · PoE2)";
            Font = new Font("Malgun Gothic", 9f);
            ClientSize = new Size(680, 720);
            MinimumSize = new Size(600, 660);
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;

            var title = new Label
            {
                Text = "PoB 한글 패처  v" + AppInfo.AppVersion,
                Font = new Font("Malgun Gothic", 13f, FontStyle.Bold),
                Location = new Point(16, 10),
                Size = new Size(640, 28)
            };
            Controls.Add(title);

            var sub = new Label
            {
                Text = "PoE1: " + AppInfo.Embedded.Pretty + "   ·   PoE2: " + AppInfo.EmbeddedPoe2.Pretty,
                ForeColor = Color.FromArgb(90, 90, 90),
                Location = new Point(16, 38),
                Size = new Size(648, 20)
            };
            Controls.Add(sub);

            var grp1 = BuildSection(_poe1, "PoE1 — Path of Building (Modules 폴더가 있는 곳)", 62);
            Controls.Add(grp1);
            var grp2 = BuildSection(_poe2, "PoE2 — Path of Building PoE2 (Modules 폴더가 있는 곳)", 210);
            Controls.Add(grp2);

            _btnCheck = new Button
            {
                Text = "최신 데이터 확인",
                Location = new Point(16, 360),
                Size = new Size(160, 30)
            };
            _btnCheck.Click += OnCheck;
            Controls.Add(_btnCheck);

            _shortcut = new CheckBox
            {
                Text = "바탕화면에도 바로가기 만들기",
                Location = new Point(190, 364),
                Size = new Size(300, 22),
                Checked = _settings.CreateShortcut
            };
            _shortcut.CheckedChanged += delegate
            {
                _settings.CreateShortcut = _shortcut.Checked;
                _settings.Save();
            };
            Controls.Add(_shortcut);

            _auto = new CheckBox
            {
                Text = "최신 데이터를 자동으로 확인합니다 (인터넷 필요)",
                Location = new Point(430, 364),
                Size = new Size(240, 22),
                Checked = _settings.AutoCheck
            };
            _auto.CheckedChanged += delegate
            {
                _settings.AutoCheck = _auto.Checked;
                _settings.Save();
            };
            Controls.Add(_auto);

            var logLabel = new Label
            {
                Text = "진행 상황",
                Location = new Point(16, 394),
                Size = new Size(200, 18),
                ForeColor = Color.FromArgb(90, 90, 90)
            };
            Controls.Add(logLabel);

            _log = new TextBox
            {
                Location = new Point(16, 414),
                Size = new Size(648, 250),
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.White,
                Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
            };
            Controls.Add(_log);

            _bar = new ProgressBar
            {
                Location = new Point(16, 672),
                Size = new Size(648, 12),
                Style = ProgressBarStyle.Blocks,
                Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
            };
            Controls.Add(_bar);

            _status = new Label
            {
                Text = "준비됨",
                Location = new Point(16, 690),
                Size = new Size(450, 20),
                ForeColor = Color.FromArgb(60, 60, 60),
                Anchor = AnchorStyles.Left | AnchorStyles.Bottom
            };
            Controls.Add(_status);

            var link = new LinkLabel
            {
                Text = "GitHub 저장소 (릴리스·사용법)",
                Location = new Point(470, 690),
                Size = new Size(194, 20),
                TextAlign = ContentAlignment.TopRight,
                Anchor = AnchorStyles.Right | AnchorStyles.Bottom
            };
            link.LinkClicked += delegate { OpenUrl(AppInfo.ProjectUrl + "#readme"); };
            Controls.Add(link);

            Load += OnFormLoad;
        }

        private GroupBox BuildSection(TargetSection sec, string title, int top)
        {
            var grp = new GroupBox
            {
                Text = title,
                Location = new Point(16, top),
                Size = new Size(648, 140)
            };

            sec.Path = new TextBox
            {
                Location = new Point(10, 24),
                Size = new Size(514, 23),
                ReadOnly = true,
                BackColor = Color.White
            };
            grp.Controls.Add(sec.Path);

            sec.Browse = new Button
            {
                Text = "폴더 선택...",
                Location = new Point(532, 23),
                Size = new Size(104, 26)
            };
            sec.Browse.Click += delegate { OnBrowse(sec); };
            grp.Controls.Add(sec.Browse);

            sec.Apply = new Button
            {
                Text = sec.Target.Display + " 패치 적용",
                Location = new Point(10, 58),
                Size = new Size(150, 32)
            };
            sec.Apply.Click += delegate { OnApply(sec, false); };
            grp.Controls.Add(sec.Apply);

            sec.Launch = new Button
            {
                Text = sec.Target.Display + " 패치 및 실행 ▶",
                Location = new Point(168, 58),
                Size = new Size(180, 32),
                Font = new Font("Malgun Gothic", 9f, FontStyle.Bold)
            };
            sec.Launch.Click += delegate { OnApply(sec, true); };
            grp.Controls.Add(sec.Launch);

            sec.Restore = new Button
            {
                Text = "영문 원본으로 복구",
                Location = new Point(356, 58),
                Size = new Size(150, 32)
            };
            sec.Restore.Click += delegate { OnRestore(sec, EventArgs.Empty); };
            grp.Controls.Add(sec.Restore);

            sec.Info = new Label
            {
                Text = "설치 상태: 확인 중...",
                Location = new Point(12, 100),
                Size = new Size(620, 30),
                ForeColor = Color.FromArgb(90, 90, 90)
            };
            grp.Controls.Add(sec.Info);
            return grp;
        }

        private void OnFormLoad(object sender, EventArgs e)
        {
            Log("PoB 한글 패처 v" + AppInfo.AppVersion);
            Log("PoE1 데이터: " + AppInfo.Embedded.Pretty + " / PoE2 데이터: " + AppInfo.EmbeddedPoe2.Pretty);
            Log("사용법: 원하는 게임의 [패치 및 실행] 을 누르면 확인·적용 후 PoB 가 열립니다. 게임 안에서 F2 로 한/영 전환.");

            InitSection(_poe1, _initialTarget);
            InitSection(_poe2, _initialTarget);

            if (_settings.AutoCheck)
            {
                Task.Run(delegate
                {
                    var rel1 = Updater.GetLatest(Targets.Poe1, null);
                    var rel2 = Updater.GetLatest(Targets.Poe2, null);
                    Post(delegate
                    {
                        Status("최신 릴리스 — PoE1 v" + (rel1 == null ? "?" : rel1.Version)
                            + " / PoE2 v" + (rel2 == null ? "?" : rel2.Version));
                    });
                });
            }
        }

        private void InitSection(TargetSection sec, string initial)
        {
            var target = "";
            if (!string.IsNullOrEmpty(initial) && Installer.IsPoB(initial))
                target = initial;
            if (string.IsNullOrEmpty(target))
            {
                var last = _settings.GetLastTarget(sec.Target.Id);
                if (!string.IsNullOrEmpty(last) && Installer.IsPoB(last)) target = last;
            }
            if (string.IsNullOrEmpty(target))
                target = Installer.FindPoB(null, sec.Target) ?? "";

            if (target.Length > 0)
            {
                SetTarget(sec, target);
                DescribeInstalled(sec);
            }
            else
            {
                sec.Info.Text = "설치 상태: Path of Building 폴더를 자동으로 찾지 못했습니다. [폴더 선택...] 으로 지정해 주세요.";
            }
        }

        private void DescribeInstalled(TargetSection sec)
        {
            var target = sec.Path.Text;
            if (!Installer.IsPoB(target))
            {
                sec.Info.Text = "설치 상태: 폴더가 지정되지 않았습니다";
                return;
            }
            var installed = Installer.InstalledVersion(target, sec.Target);
            var patched = Installer.HasMarker(target, sec.Target);
            sec.Info.Text = "설치 상태: " + (installed == null ? "한글 데이터 없음" : "한글 데이터 " + installed)
                + (patched ? " / Main.lua 패치됨" : " / Main.lua 원본") + "   (" + target + ")";
            Log(sec.Target.Display + " 폴더: " + target + " — "
                + (installed == null ? "한글 데이터 없음" : installed) + (patched ? " / 패치됨" : " / 원본"));
        }

        private void Post(Action action)
        {
            if (IsDisposed) return;
            try
            {
                if (IsHandleCreated && InvokeRequired) BeginInvoke(action);
                else action();
            }
            catch (ObjectDisposedException)
            {
            }
            catch (InvalidOperationException)
            {
            }
        }

        private void Log(string line)
        {
            Post(delegate
            {
                if (_log.TextLength > 60000) _log.Clear();
                _log.AppendText(line + "\r\n");
                _log.SelectionStart = _log.TextLength;
                _log.ScrollToCaret();
            });
        }

        private void Status(string text)
        {
            Post(delegate { _status.Text = text; });
        }

        private void SetBusy(bool busy)
        {
            _busy = busy;
            foreach (var sec in new[] { _poe1, _poe2 })
            {
                sec.Apply.Enabled = !busy;
                sec.Launch.Enabled = !busy;
                sec.Restore.Enabled = !busy;
                sec.Browse.Enabled = !busy;
            }
            _btnCheck.Enabled = !busy;
            _bar.Style = busy ? ProgressBarStyle.Marquee : ProgressBarStyle.Blocks;
            _bar.MarqueeAnimationSpeed = busy ? 30 : 0;
        }

        private void SetTarget(TargetSection sec, string path)
        {
            sec.Path.Text = path;
            if (!string.IsNullOrEmpty(path) && Installer.IsPoB(path))
            {
                _settings.SetLastTarget(sec.Target.Id, path);
                _settings.Save();
            }
        }

        private bool Confirm(string message)
        {
            return MessageBox.Show(this, message, "PoB 한글 패처",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button1) == DialogResult.Yes;
        }

        private void Info(string message)
        {
            Post(delegate { MessageBox.Show(this, message, "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Information); });
        }

        private void Warn(string message)
        {
            Post(delegate { MessageBox.Show(this, message, "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Warning); });
        }

        private void OpenUrl(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Log("링크를 열지 못했습니다: " + ex.Message);
            }
        }

        private void OnBrowse(TargetSection sec)
        {
            using (var dlg = new FolderBrowserDialog())
            {
                dlg.Description = sec.Target.Display + " Path of Building 폴더(Modules 폴더가 들어 있는 폴더)를 선택하세요";
                if (!string.IsNullOrEmpty(sec.Path.Text) && System.IO.Directory.Exists(sec.Path.Text))
                    dlg.SelectedPath = sec.Path.Text;
                if (dlg.ShowDialog(this) != DialogResult.OK) return;

                var picked = dlg.SelectedPath;
                if (!Installer.IsPoB(picked))
                {
                    var sub = Installer.FindPoB(picked, sec.Target);
                    if (sub != null && sub.StartsWith(picked, StringComparison.OrdinalIgnoreCase)) picked = sub;
                }
                if (!Installer.IsPoB(picked))
                {
                    Warn("선택한 폴더에서 Modules\\Main.lua 를 찾지 못했습니다.\n"
                        + "Path of Building 설치 폴더(Modules 폴더가 있는 곳)를 선택해 주세요.");
                    return;
                }
                SetTarget(sec, picked);
                DescribeInstalled(sec);
                Status(sec.Target.Display + " 폴더가 지정되었습니다");
            }
        }

        private string ResolveTarget(TargetSection sec)
        {
            if (Installer.IsPoB(sec.Path.Text)) return sec.Path.Text;
            var found = Installer.FindPoB(null, sec.Target);
            if (found != null)
            {
                SetTarget(sec, found);
                Log(sec.Target.Display + " 폴더: " + found);
                return found;
            }
            Warn(sec.Target.Display + " Path of Building 폴더를 찾지 못했습니다.\n[폴더 선택...] 으로 직접 지정해 주세요.");
            return null;
        }

        private bool GuardRunning()
        {
            if (!Installer.IsPoBRunning()) return true;
            Warn("Path of Building 이 실행 중입니다.\n창을 닫은 뒤 다시 시도해 주세요. (파일이 잠겨 있으면 패치가 실패합니다.)");
            return false;
        }

        private async void OnApply(TargetSection sec, bool launch)
        {
            if (_busy) return;
            var game = sec.Target;
            var target = ResolveTarget(sec);
            if (target == null || !GuardRunning()) return;
            SetBusy(true);
            try
            {
                ReleaseInfo rel = null;
                if (_settings.AutoCheck)
                {
                    Status(game.Display + " 최신 데이터 확인 중...");
                    rel = await Task.Run(delegate { return Updater.GetLatest(game, Log); });
                    var embed = AppInfo.EmbeddedFor(game);
                    if (rel != null && VersionUtil.IsNewer(rel.Version, embed.Version))
                    {
                        var go = Confirm(game.Display + " 새 데이터 v" + rel.Version
                            + (string.IsNullOrEmpty(rel.Season) ? "" : " (" + rel.Season + ")")
                            + " 이(가) 있습니다.\n지금 내려받아 적용할까요?\n\n[아니오] 를 누르면 이 실행 파일에 들어 있는 v"
                            + embed.Version + " 데이터로 패치합니다.");
                        if (!go) rel = null;
                    }
                    else
                    {
                        if (rel != null) Log("최신 릴리스 v" + rel.Version + " — 내장 데이터가 최신입니다.");
                        rel = null;
                    }
                }

                var applied = await Task.Run(delegate { return ApplyFlow(sec, target, rel); });
                if (applied == null || !applied.Ok) return;
                AnnounceApply(sec, target);

                if (launch)
                {
                    Status(game.Display + " 실행 준비 중...");
                    var opts = new LaunchOptions { NoUpdate = !_settings.AutoCheck, GameId = game.Id };
                    var result = await Task.Run(delegate { return Launcher.Maintain(opts, target, Log); });
                    if (result == null) return;
                    if (!string.IsNullOrEmpty(result.Error)) Log("[안내] " + result.Error);
                    if (!result.Ok)
                    {
                        Warn(game.Display + " Path of Building 을 실행할 수 없습니다.\n\n" + result.Error);
                        return;
                    }
                    Status(game.Display + " Path of Building 실행");
                    Launcher.StartPoB(result);
                }
            }
            catch (Exception ex)
            {
                Log("[오류] " + ex.Message);
                Status("오류가 발생했습니다");
            }
            finally
            {
                SetBusy(false);
            }
        }

        /// <summary>패치 적용 흐름. 배경 스레드에서 실행된다.</summary>
        private ApplyResult ApplyFlow(TargetSection sec, string target, ReleaseInfo rel)
        {
            var game = sec.Target;
            var embed = AppInfo.EmbeddedFor(game);
            var installed = Installer.InstalledVersion(target, game);
            Log("— " + game.Display + " 패치 시작 —");
            Log("설치 폴더: " + target);
            Log("내장 데이터: " + embed.Pretty);
            Log("설치된 데이터: " + (installed ?? "없음"));

            byte[] payload = null;
            var data = embed;

            if (rel != null)
            {
                try
                {
                    payload = Updater.DownloadData(rel, Log);
                    data = rel.ToBuildInfo();
                    Log("데이터 v" + data.Version + " 준비 완료");
                }
                catch (Exception ex)
                {
                    Log("데이터를 받지 못했습니다: " + ex.Message);
                    Log("이 실행 파일에 들어 있는 데이터로 패치합니다.");
                    payload = null;
                    data = embed;
                }
            }

            if (payload == null) payload = AppInfo.EmbeddedPayloadFor(game);

            if (installed != null && VersionUtil.IsNewer(installed, data.Version))
            {
                Log("설치된 데이터(" + installed + ")가 더 최신입니다. 덮어쓰지 않았습니다.");
                Status("이미 최신입니다");
                return null;
            }

            Log("한글 데이터와 폰트를 복사하는 중...");
            var r = Installer.Apply(target, payload, data, game);
            if (!r.Ok)
            {
                Log("[실패] " + r.Error);
                Status("패치 실패");
                Warn("패치에 실패했습니다.\n\n" + r.Error);
                return r;
            }

            Log("한글 패치 완료: " + r.VersionText);
            if (r.AlreadyPatched) Log("Modules\\Main.lua 는 이미 패치되어 있었습니다 (데이터만 갱신).");
            if (r.BackedUp) Log("원본 백업: " + game.DataDir + "\\_설치기록\\Main.lua.orig");
            Status("패치 완료 (" + r.VersionText + ")");
            return r;
        }

        private void AnnounceApply(TargetSection sec, string target)
        {
            var game = sec.Target;
            var text = new System.Text.StringBuilder();
            text.Append(game.Display + " 한글 패치가 끝났습니다.\n\n");

            var sc = Shortcut.Create(target, _settings.CreateShortcut, game);
            if (sc.Ok)
            {
                text.Append("· 바로가기를 만들었습니다.\n");
                foreach (var p in sc.Paths)
                {
                    text.Append("   " + p + "\n");
                    Log("바로가기: " + p);
                }
                text.Append("\n· 이 아이콘(또는 윈도우 키 검색에서 \"" + game.ShortcutName + "\")으로 실행하면\n");
                text.Append("  매번 최신 한글 패치를 확인·적용한 뒤 PoB 가 열립니다.\n\n");
                Status("패치 완료 — 바로가기 생성됨");
            }
            else
            {
                Log("바로가기를 만들지 못했습니다: " + sc.Error);
            }

            text.Append("· PoB 를 직접 실행해도 다음 실행 때 최신 패치를 미리 받아 둡니다.\n");
            text.Append("· 게임 안에서 F2 를 누르면 한글/영문 표시가 즉시 바뀝니다.\n");
            text.Append("· 영문으로 되돌리려면 [영문 원본으로 복구] 를 누르세요.");
            Info(text.ToString());
            DescribeInstalled(sec);
        }

        private async void OnCheck(object sender, EventArgs e)
        {
            if (_busy) return;
            SetBusy(true);
            Status("최신 릴리스 확인 중...");
            try
            {
                var rel1 = await Task.Run(delegate { return Updater.GetLatest(Targets.Poe1, Log); });
                var rel2 = await Task.Run(delegate { return Updater.GetLatest(Targets.Poe2, Log); });
                Status("최신 릴리스 — PoE1 v" + (rel1 == null ? "?" : rel1.Version)
                    + " / PoE2 v" + (rel2 == null ? "?" : rel2.Version));
                if (rel1 == null && rel2 == null)
                {
                    Warn("최신 릴리스 정보를 받지 못했습니다.\n인터넷 연결을 확인하거나 잠시 후 다시 시도해 주세요.");
                    return;
                }
                Info("이 실행 파일의 내장 데이터\n"
                    + "· PoE1: v" + AppInfo.Embedded.Version + "\n"
                    + "· PoE2: v" + AppInfo.EmbeddedPoe2.Version + "\n\n"
                    + "GitHub 최신 릴리스\n"
                    + "· PoE1: v" + (rel1 == null ? "확인 실패" : rel1.Version) + "\n"
                    + "· PoE2: v" + (rel2 == null ? "확인 실패" : rel2.Version)
                    + "\n\n[패치 적용] 을 누르면 최신 데이터를 내려받아 적용합니다.");
            }
            catch (Exception ex)
            {
                Log("[오류] " + ex.Message);
                Status("오류가 발생했습니다");
            }
            finally
            {
                SetBusy(false);
            }
        }

        private async void OnRestore(TargetSection sec, EventArgs e)
        {
            if (_busy) return;
            var game = sec.Target;
            var target = ResolveTarget(sec);
            if (target == null || !GuardRunning()) return;
            if (!Confirm("Modules\\Main.lua 를 원본으로 되돌리고 " + game.DataDir + " 폴더를 삭제합니다.\n계속할까요?")) return;

            SetBusy(true);
            try
            {
                var r = await Task.Run(delegate { return Installer.Restore(target, game); });
                if (!r.Ok)
                {
                    Log("[실패] " + (string.IsNullOrEmpty(r.Error) ? "복구를 확인하지 못했습니다." : r.Error));
                    Status("복구 실패");
                    Warn("복구에 실패했습니다.\n\n" + r.Error);
                    return;
                }
                if (r.RestoredFromBackup) Log("Modules\\Main.lua 를 백업본으로 되돌렸습니다.");
                else if (r.RemovedLoader) Log("로더 줄을 제거했습니다.");
                else Log("이미 영문 원본 상태였습니다.");
                if (r.KrRemoved) Log(game.DataDir + " 폴더를 삭제했습니다.");
                Status(game.Display + " 영문 원본으로 복구되었습니다");
                Info(game.Display + " 영문 원본으로 복구되었습니다.\nPath of Building 을 실행하면 영문으로 보입니다.");
                DescribeInstalled(sec);
            }
            catch (Exception ex)
            {
                Log("[오류] " + ex.Message);
                Status("오류가 발생했습니다");
            }
            finally
            {
                SetBusy(false);
            }
        }
    }
}
