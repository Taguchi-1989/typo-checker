using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace TypoChecker.WpfApp;

/// <summary>処理中インジケータ（画面上部に「✍ 補正中…」を即時表示。Python版 processing_indicator.py 相当）。</summary>
public sealed class ProcessingIndicator
{
    private Window? _win;
    private TextBlock? _label;
    private DispatcherTimer? _timer;
    private int _phase;
    private DateTime _start;
    private int _active; // 実行中件数（参照カウント）

    public void Begin()
    {
        _active++;
        if (_win != null) return;

        _start = DateTime.Now;
        _label = new TextBlock
        {
            Text = "✍ 補正中…",
            Foreground = Brushes.White,
            FontWeight = FontWeights.Bold,
            FontSize = 14,
        };
        _win = new Window
        {
            WindowStyle = WindowStyle.None,
            AllowsTransparency = true,
            Background = new SolidColorBrush(Color.FromRgb(0x1F, 0x6F, 0xEB)),
            Topmost = true,
            ShowInTaskbar = false,
            ResizeMode = ResizeMode.NoResize,
            SizeToContent = SizeToContent.WidthAndHeight,
            WindowStartupLocation = WindowStartupLocation.Manual,
            Content = new Border { Padding = new Thickness(16, 8, 16, 8), Child = _label },
        };
        _win.Loaded += (_, _) =>
        {
            _win.Left = (SystemParameters.PrimaryScreenWidth - _win.ActualWidth) / 2;
            _win.Top = 60;
        };
        _win.Show();

        _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(300) };
        _timer.Tick += (_, _) =>
        {
            _phase = (_phase + 1) % 4;
            var dots = new string('.', _phase);
            var sec = (int)(DateTime.Now - _start).TotalSeconds;
            var count = _active > 1 ? $"  {_active}件" : "";
            _label!.Text = $"✍ 補正中{dots}{count}   {sec}秒";
        };
        _timer.Start();
    }

    public void End()
    {
        if (_active > 0) _active--;
        if (_active > 0) return;
        _timer?.Stop();
        _timer = null;
        _win?.Close();
        _win = null;
        _label = null;
    }
}
