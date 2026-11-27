from scripts import benchmark


def test_benchmark_reports_each_window_count(tiny_model, capsys):
    card_path, model_dir = tiny_model

    code = benchmark.main(
        [
            "--card",
            str(card_path),
            "--model-dir",
            str(model_dir),
            "--repeats",
            "1",
            "--windows",
            "1",
            "3",
        ]
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "windows=1 " in out
    assert "windows=3 " in out
    assert "median_ms=" in out
