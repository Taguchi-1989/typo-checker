using TypoChecker.Core;
using Xunit;

namespace TypoChecker.Tests;

public class PromptsTests
{
    [Fact]
    public void BuildPrompt_Basic_EndsWithInput()
    {
        var p = Prompts.BuildPrompt(CorrectionMode.Typo, "本体テキスト");
        Assert.Contains("校正アシスタント", p);
        Assert.EndsWith("入力文:\n本体テキスト", p);
        Assert.DoesNotContain("参考例", p);
    }

    [Fact]
    public void BuildPrompt_Fewshot_InjectsExamples()
    {
        var fs = new List<CorpusItem>
        {
            new() { SourceText = "雑", AcceptedText = "丁寧" },
            new() { SourceText = "", AcceptedText = "良い文例のみ" },
            new() { SourceText = "x", AcceptedText = "" }, // accepted空はスキップ
        };
        var p = Prompts.BuildPrompt(CorrectionMode.Business, "本体", fs);
        Assert.Contains("参考例", p);
        Assert.Contains("入力: 雑", p);
        Assert.Contains("出力: 丁寧", p);
        Assert.Contains("良い文例: 良い文例のみ", p);
        Assert.EndsWith("入力文:\n本体", p);
    }

    [Fact]
    public void BuildPrompt_EmptyFewshot_NoExamplesBlock()
    {
        var p = Prompts.BuildPrompt(CorrectionMode.Typo, "本体", new List<CorpusItem>());
        Assert.DoesNotContain("参考例", p);
    }
}

public class ModelsTests
{
    [Theory]
    [InlineData(CorrectionMode.Business, "business", "ビジネス依頼文化")]
    [InlineData(CorrectionMode.Typo, "typo", "タイポ修正")]
    public void Mode_KeyAndLabel(CorrectionMode mode, string key, string label)
    {
        Assert.Equal(key, mode.Key());
        Assert.Equal(label, mode.Label());
    }

    [Fact]
    public void Job_Defaults()
    {
        var j = new Job { Mode = CorrectionMode.Typo, OriginalText = "本文" };
        Assert.Equal("queued", j.Status);
        Assert.Null(j.Accepted);
        Assert.Null(j.ResultText);
        Assert.False(string.IsNullOrEmpty(j.JobId));
    }
}
