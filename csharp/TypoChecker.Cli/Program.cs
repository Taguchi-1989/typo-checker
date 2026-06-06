using TypoChecker.Core;

// 移植の動作確認用 CLI（Python版 run_phase0 / バックエンドの最小相当）
//   dotnet run --project TypoChecker.Cli -- typo "なおすテキスト"
//   echo テキスト | dotnet run --project TypoChecker.Cli -- business

var modeArg = args.Length > 0 ? args[0] : "typo";
var text = args.Length > 1 ? args[1] : await Console.In.ReadToEndAsync();
if (string.IsNullOrWhiteSpace(text))
{
    Console.Error.WriteLine("入力テキストがありません。");
    return 2;
}

var mode = modeArg == "business" ? CorrectionMode.Business : CorrectionMode.Typo;
var client = new OllamaClient();

if (!await client.CheckConnectionAsync())
{
    Console.Error.WriteLine("ローカルLLMに接続できません。Ollama を確認してください。");
    return 1;
}

var prompt = Prompts.BuildPrompt(mode, text);
var temperature = mode == CorrectionMode.Business ? 0.3 : 0.2;
var raw = await client.GenerateAsync("qwen3.5-jp-4b:q6", prompt, temperature, think: false);
Console.WriteLine(Sanitizer.Sanitize(raw));
return 0;
