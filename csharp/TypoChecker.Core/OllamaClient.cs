using System.Text;
using System.Text.Json;

namespace TypoChecker.Core;

/// <summary>LLM クライアントの抽象（テスト時にスタブを注入できるように）。</summary>
public interface IOllamaClient
{
    Task<string> GenerateAsync(string model, string prompt, double temperature,
        bool? think = false, CancellationToken ct = default);
    Task<bool> CheckConnectionAsync(CancellationToken ct = default);
}

/// <summary>Ollama クライアント（Python版 app/llm.py の移植）。think 制御対応。</summary>
public class OllamaClient : IOllamaClient
{
    private readonly HttpClient _http;
    private readonly string _endpoint;

    public OllamaClient(string endpoint = "http://localhost:11434", HttpClient? http = null)
    {
        _endpoint = endpoint.TrimEnd('/');
        _http = http ?? new HttpClient { Timeout = TimeSpan.FromSeconds(120) };
    }

    /// <summary>補正案を1件生成。think=false で思考モデルを高速化（Qwen3等）。</summary>
    public async Task<string> GenerateAsync(
        string model, string prompt, double temperature, bool? think = false,
        CancellationToken ct = default)
    {
        var payload = new Dictionary<string, object?>
        {
            ["model"] = model,
            ["prompt"] = prompt,
            ["stream"] = false,
            ["options"] = new Dictionary<string, object> { ["temperature"] = temperature },
        };
        if (think.HasValue) payload["think"] = think.Value;

        var json = JsonSerializer.Serialize(payload);
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        using var resp = await _http.PostAsync($"{_endpoint}/api/generate", content, ct);
        resp.EnsureSuccessStatusCode();

        var body = await resp.Content.ReadAsStringAsync(ct);
        using var doc = JsonDocument.Parse(body);
        return doc.RootElement.TryGetProperty("response", out var r) ? r.GetString() ?? "" : "";
    }

    /// <summary>接続確認（§11.4）。例外は投げない。</summary>
    public async Task<bool> CheckConnectionAsync(CancellationToken ct = default)
    {
        try
        {
            using var resp = await _http.GetAsync($"{_endpoint}/api/tags", ct);
            return resp.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }
}
