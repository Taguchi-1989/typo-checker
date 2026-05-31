using System.Net;
using TypoChecker.Core;
using Xunit;

namespace TypoChecker.Tests;

// HttpMessageHandler を差し替えてリクエスト本文を検証（think/temperature の送出確認）
internal class CapturingHandler : HttpMessageHandler
{
    public string? LastBody;
    public string Response = "{\"response\":\"テスト応答\"}";

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken cancellationToken)
    {
        if (request.Content != null)
            LastBody = await request.Content.ReadAsStringAsync(cancellationToken);
        return new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(Response),
        };
    }
}

public class OllamaClientTests
{
    [Fact]
    public async Task Generate_ReturnsResponse_AndIncludesThinkFalse()
    {
        var handler = new CapturingHandler();
        var client = new OllamaClient("http://x", new HttpClient(handler));
        var result = await client.GenerateAsync("m", "p", 0.2, think: false);

        Assert.Equal("テスト応答", result);
        Assert.NotNull(handler.LastBody);
        Assert.Contains("\"think\":false", handler.LastBody);
        Assert.Contains("\"temperature\":0.2", handler.LastBody);
        Assert.Contains("\"model\":\"m\"", handler.LastBody);
    }

    [Fact]
    public async Task Generate_OmitsThink_WhenNull()
    {
        var handler = new CapturingHandler();
        var client = new OllamaClient("http://x", new HttpClient(handler));
        await client.GenerateAsync("m", "p", 0.3, think: null);

        Assert.NotNull(handler.LastBody);
        Assert.DoesNotContain("think", handler.LastBody);
    }

    [Fact]
    public async Task CheckConnection_TrueOnSuccess()
    {
        var client = new OllamaClient("http://x", new HttpClient(new CapturingHandler()));
        Assert.True(await client.CheckConnectionAsync());
    }
}
