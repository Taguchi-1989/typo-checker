namespace TypoChecker.Core;

/// <summary>ジョブのオーケストレーション（Python版 app/backend.py のコア相当・UI非依存）。

/// バリデーション（空/文字数超過）→ プロンプト組み立て(+Corpus) → Ollama → サニタイズ。
/// 並列実行は SemaphoreSlim で max_parallel に制限（§Phase 3）。
/// </summary>
public class JobService
{
    private readonly AppSettings _settings;
    private readonly IOllamaClient _client;
    private readonly CorpusStore? _corpus;
    private readonly SemaphoreSlim _gate;

    public JobService(AppSettings settings, IOllamaClient client, CorpusStore? corpus = null)
    {
        _settings = settings;
        _client = client;
        _corpus = corpus;
        _gate = new SemaphoreSlim(Math.Max(1, settings.Llm.MaxParallel));
    }

    public async Task<Job> RunAsync(CorrectionMode mode, string text, CancellationToken ct = default)
    {
        var job = new Job { Mode = mode, OriginalText = text ?? "" };

        var trimmed = (text ?? "").Trim();
        if (trimmed.Length == 0)
        {
            job.Status = "failed";
            job.ErrorMessage = "選択範囲が空です";
            return job;
        }
        if (trimmed.Length > _settings.MaxChars)
        {
            job.Status = "failed";
            job.ErrorMessage = $"文字数超過（{_settings.MaxChars}字まで）";
            return job;
        }

        await _gate.WaitAsync(ct);
        try
        {
            job.Status = "running";
            IEnumerable<CorpusItem>? fewshot = null;
            if (_settings.CorpusEnabled && _corpus != null)
                fewshot = _corpus.SelectFewshot(mode, _settings.CorpusFewshotCount);

            var prompt = Prompts.BuildPrompt(mode, job.OriginalText, fewshot);
            var raw = await _client.GenerateAsync(
                _settings.Llm.Model, prompt, _settings.Llm.TemperatureFor(mode),
                _settings.Llm.Think, ct);

            job.ResultText = Sanitizer.Sanitize(
                raw, _settings.Sanitize.StripPreamble, _settings.Sanitize.StripWrappingQuotes);
            job.Sanitized = true;
            job.Status = "done";
        }
        catch (Exception e)
        {
            job.Status = "failed";
            job.ErrorMessage = e.Message;
        }
        finally
        {
            _gate.Release();
        }
        return job;
    }
}
