using System.Globalization;
using System.Windows;
using System.Windows.Media;
using TypoChecker.Core;

namespace TypoChecker.WpfApp;

public partial class SettingsWindow : Window
{
    private readonly AppSettings _settings;
    private readonly OllamaClient _client;
    private readonly Action _onSaved;

    public SettingsWindow(AppSettings settings, OllamaClient client, Action onSaved)
    {
        InitializeComponent();
        _settings = settings;
        _client = client;
        _onSaved = onSaved;

        CmbModel.ItemsSource = AppSettings.ModelCandidates;
        TxtEndpoint.Text = settings.Llm.Endpoint;
        CmbModel.Text = settings.Llm.Model;
        ChkThink.IsChecked = settings.Llm.Think ?? false;
        TxtTempB.Text = settings.Llm.TemperatureBusiness.ToString(CultureInfo.InvariantCulture);
        TxtTempT.Text = settings.Llm.TemperatureTypo.ToString(CultureInfo.InvariantCulture);
        TxtMaxChars.Text = settings.MaxChars.ToString();
        TxtMaxParallel.Text = settings.Llm.MaxParallel.ToString();
        ChkCopy.IsChecked = settings.CopyResultOnComplete;
        ChkCorpus.IsChecked = settings.CorpusEnabled;
        TxtFewshot.Text = settings.CorpusFewshotCount.ToString();
        TxtCorpusMax.Text = settings.CorpusMaxItems.ToString();
    }

    private async void OnFetchModels(object sender, RoutedEventArgs e)
    {
        var ep = TxtEndpoint.Text.Trim();
        var probe = new OllamaClient(ep);
        var models = await probe.ListModelsAsync();
        if (models.Count > 0)
        {
            var keep = CmbModel.Text;
            CmbModel.ItemsSource = models;
            CmbModel.Text = keep;
            LblConn.Text = $"接続OK / {models.Count} モデル検出";
            LblConn.Foreground = Brushes.Green;
        }
        else
        {
            var ok = await probe.CheckConnectionAsync();
            LblConn.Text = ok ? "接続OK（モデル未取得）" : "未接続（Ollama を確認）";
            LblConn.Foreground = ok ? Brushes.DarkOrange : Brushes.Red;
        }
    }

    private static double ParseDouble(string s, double fallback) =>
        double.TryParse(s, NumberStyles.Any, CultureInfo.InvariantCulture, out var v) ? v : fallback;

    private static int ParseInt(string s, int fallback) =>
        int.TryParse(s, out var v) ? v : fallback;

    private void OnSave(object sender, RoutedEventArgs e)
    {
        _settings.Llm.Endpoint = TxtEndpoint.Text.Trim();
        _settings.Llm.Model = CmbModel.Text.Trim();
        _settings.Llm.Think = ChkThink.IsChecked == true;
        _settings.Llm.TemperatureBusiness = ParseDouble(TxtTempB.Text, _settings.Llm.TemperatureBusiness);
        _settings.Llm.TemperatureTypo = ParseDouble(TxtTempT.Text, _settings.Llm.TemperatureTypo);
        _settings.MaxChars = ParseInt(TxtMaxChars.Text, _settings.MaxChars);
        _settings.Llm.MaxParallel = Math.Max(1, ParseInt(TxtMaxParallel.Text, _settings.Llm.MaxParallel));
        _settings.CopyResultOnComplete = ChkCopy.IsChecked == true;
        _settings.CorpusEnabled = ChkCorpus.IsChecked == true;
        _settings.CorpusFewshotCount = ParseInt(TxtFewshot.Text, _settings.CorpusFewshotCount);
        _settings.CorpusMaxItems = ParseInt(TxtCorpusMax.Text, _settings.CorpusMaxItems);

        _onSaved();
        Close();
    }

    private void OnClose(object sender, RoutedEventArgs e) => Close();
}
