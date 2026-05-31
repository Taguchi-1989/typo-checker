using TypoChecker.Core;
using Xunit;

namespace TypoChecker.Tests;

// Python版 tests/test_backend_behaviors.py に相当（UI非依存のオーケストレーション）
internal class StubOllama : IOllamaClient
{
    public string Response = "はい、修正しました：補正後の本文です。";
    public int DelayMs;
    private int _concurrent;
    public int MaxConcurrent;

    public Task<bool> CheckConnectionAsync(CancellationToken ct = default) => Task.FromResult(true);
    public Task<List<string>> ListModelsAsync(CancellationToken ct = default) => Task.FromResult(new List<string>());

    public async Task<string> GenerateAsync(string model, string prompt, double temperature,
        bool? think = false, CancellationToken ct = default)
    {
        var c = Interlocked.Increment(ref _concurrent);
        MaxConcurrent = Math.Max(MaxConcurrent, c);
        try
        {
            if (DelayMs > 0) await Task.Delay(DelayMs, ct);
            return Response;
        }
        finally
        {
            Interlocked.Decrement(ref _concurrent);
        }
    }
}

public class JobServiceTests
{
    private static AppSettings Settings(int maxParallel = 2, int maxChars = 3000) => new()
    {
        MaxChars = maxChars,
        Llm = new LlmSettings { MaxParallel = maxParallel, Model = "stub" },
    };

    [Fact]
    public async Task Empty_IsRejected()
    {
        var svc = new JobService(Settings(), new StubOllama());
        var job = await svc.RunAsync(CorrectionMode.Typo, "   ");
        Assert.Equal("failed", job.Status);
        Assert.Contains("空", job.ErrorMessage);
    }

    [Fact]
    public async Task MaxChars_IsRejected()
    {
        var svc = new JobService(Settings(maxChars: 5), new StubOllama());
        var job = await svc.RunAsync(CorrectionMode.Typo, "あいうえおかきくけこ");
        Assert.Equal("failed", job.Status);
        Assert.Contains("文字数", job.ErrorMessage);
    }

    [Fact]
    public async Task Normal_DoneAndSanitized()
    {
        var svc = new JobService(Settings(), new StubOllama());
        var job = await svc.RunAsync(CorrectionMode.Business, "雑なメモ");
        Assert.Equal("done", job.Status);
        Assert.Equal("補正後の本文です。", job.ResultText); // 前置き除去済み
        Assert.True(job.Sanitized);
    }

    [Fact]
    public async Task ParallelLimit_IsRespected()
    {
        var stub = new StubOllama { DelayMs = 80 };
        var svc = new JobService(Settings(maxParallel: 1), stub);
        var tasks = Enumerable.Range(0, 3)
            .Select(_ => svc.RunAsync(CorrectionMode.Typo, "テスト"))
            .ToArray();
        await Task.WhenAll(tasks);
        Assert.Equal(1, stub.MaxConcurrent);               // 上限1を超えない
        Assert.All(tasks, t => Assert.Equal("done", t.Result.Status));
    }
}
