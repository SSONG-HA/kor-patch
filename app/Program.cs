using System;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace PoBKR
{
    internal static class Program
    {
        [DllImport("kernel32.dll")]
        private static extern IntPtr GetConsoleWindow();

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            }
            catch
            {
            }

            var initialTarget = "";
            if (args != null && args.Length > 0)
            {
                var first = (args[0] ?? "").Trim().Trim('"');
                if (IsLaunchMode(first)) return Launcher.Run(args);
                if (first.StartsWith("--", StringComparison.Ordinal) || first.StartsWith("/?", StringComparison.Ordinal))
                    return Cli.Run(args);
                if (Directory.Exists(first)) initialTarget = first;
            }

            HideConsole();
            MakeDpiAware();

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(initialTarget));
            return 0;
        }

        private static bool IsLaunchMode(string first)
        {
            return string.Equals(first, "--launch", StringComparison.OrdinalIgnoreCase)
                || string.Equals(first, "--bg-update", StringComparison.OrdinalIgnoreCase)
                || string.Equals(first, "--apply-staged", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>콘솔 창을 바로 숨긴다 (GUI·런처 모드).</summary>
        internal static void HideConsole()
        {
            try
            {
                var handle = GetConsoleWindow();
                if (handle != IntPtr.Zero) ShowWindow(handle, 0);
            }
            catch
            {
            }
        }

        internal static void MakeDpiAware()
        {
            try
            {
                SetProcessDPIAware();
            }
            catch
            {
            }
        }
    }
}
