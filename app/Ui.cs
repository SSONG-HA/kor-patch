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

        private TextBox _target;
        private TextBox _log;
        private Button _btnApply;
        private Button _btnCheck;
        private Button _btnRestore;
        private Button _btnBrowse;
        private CheckBox _auto;
        private Label _status;
        private ProgressBar _bar;
        private bool _busy;

        public MainForm(string initialTarget)
        {
            _settings = Settings.Load();
            _initialTarget = initialTarget ?? "";
            BuildUi();
        }

        private void BuildUi()
        {
            Text = "PoB 한글 패처 (PoB-KR-Patcher)";
            Font = new Font("Malgun Gothic", 9f);
            ClientSize = new Size(660, 566);
            MinimumSize = new Size(560, 480);
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;

            var title = new Label
            {
                Text = "PoB 한글 패처  v" + AppInfo.AppVersion,
                Font = new Font("Malgun Gothic", 13f, FontStyle.Bold),
                Location = new Point(16, 12),
                Size = new Size(620, 28)
            };
            Controls.Add(title);

            var sub = new Label
            {
                Text = "내장 데이터: " + AppInfo.Embedded.Pretty + "   ·   Path of Building Community Fork 전용",
                ForeColor = Color.FromArgb(90, 90, 90),
                Location = new Point(16, 42),
                Size = new Size(628, 20)
            };
            Controls.Add(sub);

            var grp = new GroupBox
            {
                Text = "Path of Building 폴더 (Modules 폴더가 있는 곳)",
                Location = new Point(16, 68),
                Size = new Size(628, 64)
            };
            _target = new TextBox
            {
                Location = new Point(10, 26),
                Size = new Size(494, 23),
                ReadOnly = true,
                BackColor = Color.White
            };
            grp.Controls.Add(_target);
            _btnBrowse = new Button
            {
                Text = "폴더 선택...",
                Location = new Point(512, 25),
                Size = new Size(104, 26)
            };
            _btnBrowse.Click += OnBrowse;
            grp.Controls.Add(_btnBrowse);
            Controls.Add(grp);

            _btnApply = new Button
            {
                Text = "한글 패치 적용 / 업데이트",
                Location = new Point(16, 144),
                Size = new Size(232, 40),
                Font = new Font("Malgun Gothic", 9f, FontStyle.Bold)
            };
            _btnApply.Click += OnApply;
            Controls.Add(_btnApply);

            _btnCheck = new Button
            {
                Text = "최신 시즌 확인",
                Location = new Point(258, 144),
                Size = new Size(160, 40)
            };
            _btnCheck.Click += OnCheck;
            Controls.Add(_btnCheck);

            _btnRestore = new Button
            {
                Text = "영문 원본으로 복구",
                Location = new Point(428, 144),
                Size = new Size(216, 40)
            };
            _btnRestore.Click += OnRestore;
            Controls.Add(_btnRestore);

            _auto = new CheckBox
            {
                Text = "최신 시즌 데이터를 자동으로 확인합니다 (인터넷 필요)",
                Location = new Point(18, 192),
                Size = new Size(560, 22),
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
                Location = new Point(16, 218),
                Size = new Size(200, 18),
                ForeColor = Color.FromArgb(90, 90, 90)
            };
            Controls.Add(logLabel);

            _log = new TextBox
            {
                Location = new Point(16, 238),
                Size = new Size(628, 258),
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.White,
                Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
            };
            Controls.Add(_log);

            _bar = new ProgressBar
            {
                Location = new Point(16, 502),
                Size = new Size(628, 12),
                Style = ProgressBarStyle.Blocks,
                Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
            };
            Controls.Add(_bar);

            _status = new Label
            {
                Text = "준비됨",
                Location = new Point(16, 520),
                Size = new Size(430, 20),
                ForeColor = Color.FromArgb(60, 60, 60),
                Anchor = AnchorStyles.Left | AnchorStyles.Bottom
            };
            Controls.Add(_status);

            var link = new LinkLabel
            {
                Text = "GitHub 저장소 (릴리스·사용법)",
                Location = new Point(452, 520),
                Size = new Size(192, 20),
                TextAlign = ContentAlignment.TopRight,
                Anchor = AnchorStyles.Right | AnchorStyles.Bottom
            };
            link.LinkClicked += delegate { OpenUrl(AppInfo.ProjectUrl + "#readme"); };
            Controls.Add(link);

            Load += OnFormLoad;
        }

        private void OnFormLoad(object sender, EventArgs e)
        {
            Log("PoB 한글 패처 v" + AppInfo.AppVersion + " — 내장 데이터 " + AppInfo.Embedded.Pretty);
            Log("사용법: [한글 패치 적용] 누르면 끝입니다. 게임 안에서 F2 로 한/영 전환.");

            var target = "";
            if (!string.IsNullOrEmpty(_initialTarget) && Installer.IsPoB(_initialTarget))
                target = _initialTarget;
            if (string.IsNullOrEmpty(target) && !string.IsNullOrEmpty(_settings.LastTarget) && Installer.IsPoB(_settings.LastTarget))
                target = _settings.LastTarget;
            if (string.IsNullOrEmpty(target))
                target = Installer.FindPoB(null) ?? "";

            if (target.Length > 0)
            {
                SetTarget(target);
                Log("Path of Building 폴더를 찾았습니다: " + target);
                DescribeInstalled(target);
            }
            else
            {
                Log("Path of Building 폴더를 자동으로 찾지 못했습니다. [폴더 선택...] 으로 지정해 주세요.");
                Status("Path of Building 폴더를 선택해 주세요");
            }

            if (_settings.AutoCheck)
            {
                Task.Run(() =>
                {
                    var rel = Updater.GetLatest(null);
                    if (rel == null) return;
                    Post(() =>
                    {
                        if (VersionUtil.IsNewer(rel.Version, AppInfo.Embedded.Version))
                            Status("새 시즌 데이터 v" + rel.Version + " 이(가) 있습니다 — [한글 패치 적용] 으로 받을 수 있습니다");
                        else
                            Status("최신 상태입니다 (릴리스 v" + rel.Version + ")");
                    });
                    Log("최신 릴리스: v" + rel.Version + (string.IsNullOrEmpty(rel.Season) ? "" : " (PoE1 " + rel.Season + ")"));
                });
            }
        }

        private void DescribeInstalled(string target)
        {
            var installed = Installer.InstalledVersion(target);
            var patched = Installer.HasMarker(target);
            Log("설치 상태: " + (installed == null ? "한글 데이터 없음" : "한글 데이터 " + installed)
                + (patched ? " / Main.lua 패치됨" : " / Main.lua 원본"));
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
            _btnApply.Enabled = !busy;
            _btnCheck.Enabled = !busy;
            _btnRestore.Enabled = !busy;
            _btnBrowse.Enabled = !busy;
            _bar.Style = busy ? ProgressBarStyle.Marquee : ProgressBarStyle.Blocks;
            _bar.MarqueeAnimationSpeed = busy ? 30 : 0;
        }

        private void SetTarget(string path)
        {
            _target.Text = path;
            if (!string.IsNullOrEmpty(path) && Installer.IsPoB(path))
            {
                _settings.LastTarget = path;
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

        private void OnBrowse(object sender, EventArgs e)
        {
            using (var dlg = new FolderBrowserDialog())
            {
                dlg.Description = "Path of Building 폴더(Modules 폴더가 들어 있는 폴더)를 선택하세요";
                if (!string.IsNullOrEmpty(_target.Text) && System.IO.Directory.Exists(_target.Text))
                    dlg.SelectedPath = _target.Text;
                if (dlg.ShowDialog(this) != DialogResult.OK) return;

                var picked = dlg.SelectedPath;
                if (!Installer.IsPoB(picked))
                {
                    // 선택한 폴더의 하위 1단계에서 PoB 폴더를 찾아 준다.
                    var sub = Installer.FindPoB(picked);
                    if (sub != null && sub.StartsWith(picked, StringComparison.OrdinalIgnoreCase)) picked = sub;
                }
                if (!Installer.IsPoB(picked))
                {
                    MessageBox.Show(this,
                        "선택한 폴더에서 Modules\\Main.lua 를 찾지 못했습니다.\n" +
                        "Path of Building 설치 폴더(Modules 폴더가 있는 곳)를 선택해 주세요.",
                        "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                SetTarget(picked);
                DescribeInstalled(picked);
                Status("폴더가 지정되었습니다");
            }
        }

        private string ResolveTarget()
        {
            if (Installer.IsPoB(_target.Text)) return _target.Text;
            var found = Installer.FindPoB(null);
            if (found != null)
            {
                SetTarget(found);
                Log("Path of Building 폴더: " + found);
                return found;
            }
            MessageBox.Show(this,
                "Path of Building 폴더를 찾지 못했습니다.\n[폴더 선택...] 으로 직접 지정해 주세요.",
                "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }

        private bool GuardRunning()
        {
            if (!Installer.IsPoBRunning()) return true;
            MessageBox.Show(this,
                "Path of Building 이 실행 중입니다.\n창을 닫은 뒤 다시 시도해 주세요. (파일이 잠겨 있으면 패치가 실패합니다.)",
                "PoB 한글 패처", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return false;
        }

        private async void OnApply(object sender, EventArgs e)
        {
            if (_busy) return;
            var target = ResolveTarget();
            if (target == null || !GuardRunning()) return;
            SetBusy(true);
            try
            {
                ReleaseInfo rel = null;
                if (_settings.AutoCheck)
                {
                    Status("최신 릴리스 확인 중...");
                    rel = await Task.Run(delegate { return Updater.GetLatest(Log); });
                    if (rel != null && VersionUtil.IsNewer(rel.Version, AppInfo.Embedded.Version))
                    {
                        var go = Confirm("새 시즌 데이터 v" + rel.Version
                            + (string.IsNullOrEmpty(rel.Season) ? "" : " (PoE1 " + rel.Season + ")")
                            + " 이(가) 있습니다.\n지금 내려받아 적용할까요?\n\n[아니오] 를 누르면 이 실행 파일에 들어 있는 v"
                            + AppInfo.Embedded.Version + " 데이터로 패치합니다.");
                        if (!go) rel = null;
                    }
                    else
                    {
                        if (rel != null) Log("최신 릴리스 v" + rel.Version + " — 내장 데이터가 최신입니다.");
                        rel = null;
                    }
                }
                await Task.Run(delegate { ApplyFlow(target, rel); });
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

        /// <summary>패치 적용 흐름. 배경 스레드에서 실행된다. rel 이 있으면 그 시즌 데이터를 먼저 받는다.</summary>
        private void ApplyFlow(string target, ReleaseInfo rel)
        {
            var embed = AppInfo.Embedded;
            var installed = Installer.InstalledVersion(target);
            Log("— 패치 시작 —");
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
                    Log("시즌 데이터 v" + data.Version + " 준비 완료");
                }
                catch (Exception ex)
                {
                    Log("시즌 데이터를 받지 못했습니다: " + ex.Message);
                    Log("이 실행 파일에 들어 있는 데이터로 패치합니다.");
                    payload = null;
                    data = embed;
                }
            }

            if (payload == null) payload = AppInfo.EmbeddedPayload();

            if (installed != null && VersionUtil.IsNewer(installed, data.Version))
            {
                Log("설치된 데이터(" + installed + ")가 더 최신입니다. 덮어쓰지 않았습니다.");
                Status("이미 최신입니다");
                return;
            }

            Log("한글 데이터와 폰트를 복사하는 중...");
            var r = Installer.Apply(target, payload, data);
            if (!r.Ok)
            {
                Log("[실패] " + r.Error);
                Status("패치 실패");
                Info("패치에 실패했습니다.\n\n" + r.Error);
                return;
            }

            Log("한글 패치 완료: " + r.VersionText);
            if (r.AlreadyPatched) Log("Modules\\Main.lua 는 이미 패치되어 있었습니다 (데이터만 갱신).");
            if (r.BackedUp) Log("원본 백업: KR\\_설치기록\\Main.lua.orig");
            Status("패치 완료 (" + r.VersionText + ")");
            Info("한글 패치가 끝났습니다. (" + r.VersionText + ")\n\n"
                + "· Path of Building 을 실행하세요.\n"
                + "· 게임 안에서 F2 키를 누르면 한글/영문 표시가 즉시 바뀝니다.\n"
                + "· PoB 를 업데이트한 뒤에는 이 프로그램을 다시 한 번 실행하면 됩니다.\n"
                + "· 영문으로 되돌리려면 [영문 원본으로 복구] 를 누르세요.");
        }

        private async void OnCheck(object sender, EventArgs e)
        {
            if (_busy) return;
            SetBusy(true);
            Status("최신 릴리스 확인 중...");
            try
            {
                var rel = await Task.Run(delegate { return Updater.GetLatest(Log); });
                if (rel == null)
                {
                    Status("확인 실패");
                    Info("최신 릴리스 정보를 받지 못했습니다.\n인터넷 연결을 확인하거나 잠시 후 다시 시도해 주세요.");
                    return;
                }
                Log("최신 릴리스: v" + rel.Version + (string.IsNullOrEmpty(rel.Season) ? "" : " / PoE1 " + rel.Season));
                if (!string.IsNullOrEmpty(rel.Notes)) Log("릴리스 노트: " + rel.Notes);

                if (!VersionUtil.IsNewer(rel.Version, AppInfo.Embedded.Version))
                {
                    Status("최신 상태입니다 (v" + rel.Version + ")");
                    Info("이미 최신입니다.\n\n실행 파일 내장 데이터: v" + AppInfo.Embedded.Version
                        + "\nGitHub 최신 릴리스: v" + rel.Version);
                    return;
                }

                var target = ResolveTarget();
                if (target == null || !GuardRunning()) return;
                var ask = "새 시즌 데이터 v" + rel.Version
                    + (string.IsNullOrEmpty(rel.Season) ? "" : " (PoE1 " + rel.Season + ")")
                    + " 이(가) 있습니다.\n지금 내려받아 적용할까요?";
                if (!Confirm(ask)) { Status("취소되었습니다"); return; }

                SetBusy(true);
                await Task.Run(delegate { ApplyFlow(target, rel); });
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

        private async void OnRestore(object sender, EventArgs e)
        {
            if (_busy) return;
            var target = ResolveTarget();
            if (target == null || !GuardRunning()) return;
            if (!Confirm("Modules\\Main.lua 를 원본으로 되돌리고 KR 폴더를 삭제합니다.\n계속할까요?")) return;

            SetBusy(true);
            try
            {
                var r = await Task.Run(delegate { return Installer.Restore(target); });
                if (!r.Ok)
                {
                    Log("[실패] " + (string.IsNullOrEmpty(r.Error) ? "복구를 확인하지 못했습니다." : r.Error));
                    Status("복구 실패");
                    Info("복구에 실패했습니다.\n\n" + r.Error);
                    return;
                }
                if (r.RestoredFromBackup) Log("Modules\\Main.lua 를 백업본으로 되돌렸습니다.");
                else if (r.RemovedLoader) Log("로더 줄을 제거했습니다.");
                else Log("이미 영문 원본 상태였습니다.");
                if (r.KrRemoved) Log("KR 폴더를 삭제했습니다.");
                Status("영문 원본으로 복구되었습니다");
                Info("영문 원본으로 복구되었습니다.\nPath of Building 을 실행하면 영문으로 보입니다.");
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
