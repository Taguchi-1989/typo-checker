using System.Windows;
using System.Windows.Controls;
using TypoChecker.Core;

namespace TypoChecker.WpfApp;

public partial class HistoryWindow : Window
{
    private readonly List<Job> _jobs;
    private readonly Action<Job> _onReopen;

    public HistoryWindow(IEnumerable<Job> jobs, Action<Job> onReopen)
    {
        InitializeComponent();
        _jobs = jobs.ToList();
        _onReopen = onReopen;
        foreach (var j in _jobs)
        {
            var mark = j.Status == "done" ? "✓" : j.Status == "failed" ? "✗" : "?";
            var snippet = (j.OriginalText ?? "").Replace("\n", " ");
            if (snippet.Length > 30) snippet = snippet[..30];
            LstHistory.Items.Add($"{mark} [{j.CreatedAt:HH:mm:ss}] {j.Mode.Label()}: {snippet}");
        }
    }

    private void OnReopen(object sender, RoutedEventArgs e)
    {
        var i = LstHistory.SelectedIndex;
        if (i >= 0 && i < _jobs.Count)
            _onReopen(_jobs[i]);
    }
}
