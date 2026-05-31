using System.Windows;
using System.Windows.Media;
using TypoChecker.Core;

namespace TypoChecker.WpfApp;

public partial class MainWindow : Window
{
    private OllamaClient _client;
    private readonly Action _onOpenSettings;
    private readonly Action _onOpenHistory;

    public MainWindow(AppSettings settings, OllamaClient client, Action onOpenSettings, Action onOpenHistory)
    {
        InitializeComponent();
        _client = client;
        _onOpenSettings = onOpenSettings;
        _onOpenHistory = onOpenHistory;
        LblModel.Text = $"モデル: {settings.Llm.Model}";
        Loaded += async (_, _) => await RefreshConnAsync();
    }

    public void SetStatus(string text) => LblStatus.Text = text;

    /// <summary>設定適用後にモデル表示・接続先クライアントを更新。</summary>
    public async void Refresh(AppSettings settings, OllamaClient client)
    {
        _client = client;
        LblModel.Text = $"モデル: {settings.Llm.Model}";
        await RefreshConnAsync();
    }

    private void OnSettings(object sender, RoutedEventArgs e) => _onOpenSettings();

    private void OnHistory(object sender, RoutedEventArgs e) => _onOpenHistory();

    private async Task RefreshConnAsync()
    {
        var ok = await _client.CheckConnectionAsync();
        LblConn.Text = ok ? "接続状態: 接続OK" : "接続状態: 未接続（Ollama未起動?）";
        LblConn.Foreground = ok ? Brushes.Green : Brushes.Red;
    }

    private async void OnCheckConn(object sender, RoutedEventArgs e) => await RefreshConnAsync();

    private void OnQuit(object sender, RoutedEventArgs e) => Application.Current.Shutdown();
}
