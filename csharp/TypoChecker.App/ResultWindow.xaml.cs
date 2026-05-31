using System.Windows;
using TypoChecker.Core;

namespace TypoChecker.WpfApp;

public partial class ResultWindow : Window
{
    private readonly Job _job;
    private readonly Action<string> _onCopy;
    private readonly Action<Job, bool, string> _onAccept;

    public ResultWindow(Job job, Action<string> onCopy, Action<Job, bool, string> onAccept)
    {
        InitializeComponent();
        _job = job;
        _onCopy = onCopy;
        _onAccept = onAccept;

        LblMode.Text = $"モード: {job.Mode.Label()}　作成: {job.CreatedAt:yyyy-MM-dd HH:mm:ss}";
        TxtSrc.Text = job.OriginalText;
        TxtGen.Text = job.ResultText ?? "";

        // 完了時に前面化（§6.3）
        Topmost = true;
        Loaded += (_, _) => { Activate(); Topmost = false; };
    }

    private void OnCopy(object sender, RoutedEventArgs e)
    {
        _onCopy(TxtGen.Text);
        LblStatus.Text = "生成結果をクリップボードにコピーしました。";
    }

    private void OnAcceptY(object sender, RoutedEventArgs e)
    {
        _onAccept(_job, true, TxtGen.Text);
        LblStatus.Text = "意味保存判定: 採用(Y) を記録しました。";
    }

    private void OnAcceptN(object sender, RoutedEventArgs e)
    {
        _onAccept(_job, false, TxtGen.Text);
        LblStatus.Text = "意味保存判定: 不採用(N) を記録しました。";
    }

    private void OnClose(object sender, RoutedEventArgs e) => Close();
}
