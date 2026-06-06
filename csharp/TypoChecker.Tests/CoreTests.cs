using TypoChecker.Core;
using Xunit;

namespace TypoChecker.Tests;

// Python版 tests/test_prompts_corpus.py / test_config.py に相当
public class CorpusTests
{
    [Fact]
    public void Add_Trim_Select_Delete_Persist()
    {
        var tmp = Path.Combine(Path.GetTempPath(), Path.GetRandomFileName() + ".json");
        try
        {
            var s = new CorpusStore(tmp);
            for (var i = 0; i < 5; i++)
                s.Add(CorrectionMode.Typo, $"src{i}", $"acc{i}", "t", maxItems: 3);
            Assert.Equal(3, s.Items.Count);                 // 上限でトリム
            Assert.Equal("acc4", s.Items[^1].AcceptedText); // 最新が残る

            var fs = s.SelectFewshot(CorrectionMode.Typo, 2);
            Assert.Equal(2, fs.Count);
            Assert.Empty(s.SelectFewshot(CorrectionMode.Typo, 0));

            var id = s.Items[0].Id;
            Assert.True(s.Delete(id));

            var reloaded = new CorpusStore(tmp);            // 永続化確認
            Assert.Equal(2, reloaded.Items.Count);
            Assert.DoesNotContain(reloaded.Items, x => x.Id == id);
        }
        finally { if (File.Exists(tmp)) File.Delete(tmp); }
    }

    [Fact]
    public void ImportBulk_SplitsByBlankLine()
    {
        var tmp = Path.Combine(Path.GetTempPath(), Path.GetRandomFileName() + ".json");
        try
        {
            var s = new CorpusStore(tmp);
            var n = s.ImportBulk(CorrectionMode.Business, "例文A\n\n例文B\n\n例文C", "t");
            Assert.Equal(3, n);
        }
        finally { if (File.Exists(tmp)) File.Delete(tmp); }
    }
}

public class SettingsTests
{
    [Fact]
    public void Load_WritesDefaults_WhenMissing()
    {
        var tmp = Path.Combine(Path.GetTempPath(), Path.GetRandomFileName() + ".json");
        try
        {
            var s = AppSettings.Load(tmp);
            Assert.Equal("qwen3.5-jp-4b:q6", s.Llm.Model);
            Assert.Equal(0.3, s.Llm.TemperatureBusiness);
            Assert.False(s.Llm.Think);
            Assert.True(File.Exists(tmp));
        }
        finally { if (File.Exists(tmp)) File.Delete(tmp); }
    }

    [Fact]
    public void Load_Partial_KeepsDefaults()
    {
        var tmp = Path.Combine(Path.GetTempPath(), Path.GetRandomFileName() + ".json");
        try
        {
            File.WriteAllText(tmp, "{\"maxChars\":500}");
            var s = AppSettings.Load(tmp);
            Assert.Equal(500, s.MaxChars);
            Assert.Equal("qwen3.5-jp-4b:q6", s.Llm.Model); // 欠落キーは既定
        }
        finally { if (File.Exists(tmp)) File.Delete(tmp); }
    }
}
