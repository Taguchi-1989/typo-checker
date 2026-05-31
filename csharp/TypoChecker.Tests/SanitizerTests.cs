using TypoChecker.Core;
using Xunit;

namespace TypoChecker.Tests;

// Python版 tests/test_sanitize.py と同等の回帰テスト
public class SanitizerTests
{
    [Theory]
    [InlineData("はい、修正しました：本件についてご確認ください。", "本件についてご確認ください。")]
    [InlineData("校正しました。本文です", "本文です")]
    [InlineData("承知しました。これでお願いします", "これでお願いします")]
    [InlineData("「依頼文です」", "依頼文です")]
    [InlineData("以下が修正後の文です：\n本文", "本文")]
    [InlineData("普通の文。「引用」を含む。", "普通の文。「引用」を含む。")]
    [InlineData("<think>考え中\n複数行</think>本文です", "本文です")]
    [InlineData("", "")]
    [InlineData(null, "")]
    public void Sanitize_Cases(string? input, string expected)
    {
        Assert.Equal(expected, Sanitizer.Sanitize(input));
    }

    [Fact]
    public void Sanitize_PreservesLineBreaks()
    {
        Assert.Equal("1行目\n2行目\n3行目", Sanitizer.Sanitize("1行目\n2行目\n3行目"));
    }

    [Fact]
    public void Sanitize_StripsCodeFence()
    {
        Assert.Equal("本文です", Sanitizer.Sanitize("```\n本文です\n```"));
    }
}
