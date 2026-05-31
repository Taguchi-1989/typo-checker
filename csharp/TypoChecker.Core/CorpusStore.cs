using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Unicode;

namespace TypoChecker.Core;

/// <summary>用例（§12.3 / Python版 app/corpus.py の CorpusItem 相当）。</summary>
public class CorpusItem
{
    public string Id { get; set; } = "";
    public string Mode { get; set; } = "";
    public string SourceText { get; set; } = "";
    public string AcceptedText { get; set; } = "";
    public List<string> Tags { get; set; } = new();
    public string CreatedAt { get; set; } = "";
}

/// <summary>用例コーパス Store（§9 方式A / app/corpus.py の移植）。ローカル保存のみ。</summary>
public class CorpusStore
{
    private readonly string _path;
    public List<CorpusItem> Items { get; private set; }

    private static readonly JsonSerializerOptions Opts = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Encoder = JavaScriptEncoder.Create(UnicodeRanges.All),
    };

    public CorpusStore(string path)
    {
        _path = path;
        Items = Load();
    }

    private List<CorpusItem> Load()
    {
        try
        {
            if (File.Exists(_path))
                return JsonSerializer.Deserialize<List<CorpusItem>>(File.ReadAllText(_path), Opts) ?? new();
        }
        catch { /* 壊れていたら空 */ }
        return new();
    }

    private void Save() => File.WriteAllText(_path, JsonSerializer.Serialize(Items, Opts));

    private string NewId()
    {
        var used = new HashSet<string>(Items.Select(i => i.Id));
        var n = 1;
        while (used.Contains($"c{n:D4}")) n++;
        return $"c{n:D4}";
    }

    public CorpusItem Add(CorrectionMode mode, string source, string accepted, string createdAt, int maxItems = 200)
    {
        var item = new CorpusItem
        {
            Id = NewId(),
            Mode = mode.Key(),
            SourceText = source ?? "",
            AcceptedText = accepted ?? "",
            CreatedAt = createdAt,
        };
        Items.Add(item);
        Trim(maxItems);
        Save();
        return item;
    }

    /// <summary>全文貼り付け一括インポート（空行区切りの各ブロックを良い文例として取り込み）。</summary>
    public int ImportBulk(CorrectionMode mode, string blob, string createdAt, int maxItems = 200)
    {
        var added = 0;
        foreach (var raw in blob.Replace("\r\n", "\n").Split("\n\n"))
        {
            var t = raw.Trim();
            if (t.Length == 0) continue;
            Items.Add(new CorpusItem
            {
                Id = NewId(),
                Mode = mode.Key(),
                AcceptedText = t,
                Tags = new List<string> { "import" },
                CreatedAt = createdAt,
            });
            added++;
        }
        Trim(maxItems);
        Save();
        return added;
    }

    public bool Delete(string id)
    {
        var removed = Items.RemoveAll(i => i.Id == id) > 0;
        if (removed) Save();
        return removed;
    }

    /// <summary>モード一致の最新 n 件（§9.1 将来は類似度上位）。</summary>
    public List<CorpusItem> SelectFewshot(CorrectionMode mode, int n)
    {
        if (n <= 0) return new();
        var matched = Items.Where(i => i.Mode == mode.Key()).ToList();
        return matched.Skip(Math.Max(0, matched.Count - n)).ToList();
    }

    private void Trim(int maxItems)
    {
        if (maxItems > 0 && Items.Count > maxItems)
            Items = Items.Skip(Items.Count - maxItems).ToList();
    }
}
