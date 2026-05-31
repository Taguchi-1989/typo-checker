using System.Windows;
using System.Windows.Media;
using TypoChecker.Core;

namespace TypoChecker.WpfApp;

public partial class MainWindow : Window
{
    private readonly OllamaClient _client;

    public MainWindow(AppSettings settings, OllamaClient client)
    {
        InitializeComponent();
        _client = client;
        LblModel.Text = $"モデル: {settings.Llm.Model}";
        Loaded += async (_, _) => await RefreshConnAsync();
    }

    public void SetStatus(string text) => LblStatus.Text = text;

    private async Task RefreshConnAsync()
    {
        var ok = await _client.CheckConnectionAsync();
        LblConn.Text = ok ? "接続状態: 接続OK" : "接続状態: 未接続（Ollama未起動?）";
        LblConn.Foreground = ok ? Brushes.Green : Brushes.Red;
    }

    private async void OnCheckConn(object sender, RoutedEventArgs e) => await RefreshConnAsync();

    private void OnQuit(object sender, RoutedEventArgs e) => Application.Current.Shutdown();
}
