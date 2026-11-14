from studio import progress


def test_no_logs_means_queued():
    r = progress.read([])
    assert r["stage"] == "queued" and r["step"] == 0 and r["percent"] is None
    assert progress.read(None)["stage"] == "queued"


def test_furthest_stage_wins_and_never_goes_back():
    r = progress.read(["Downloading video", "Transcribing audio", "Downloading again (retry)"])
    assert r["stage"] == "transcribe" and r["step"] == 2


def test_percent_only_while_transcribing():
    r = progress.read(["Transcribing… 41%", "Transcribing… 63%"])
    assert r["stage"] == "transcribe" and r["percent"] == 63
    later = progress.read(["Transcribing… 63%", "Gemini scoring window 1"])
    assert later["stage"] == "analyze" and later["percent"] is None


def test_render_counts_ready_clips():
    r = progress.read(["found 5 clips", "Creating clip 1", "Clip 1 ready", "clip 2 ready"])
    assert r["stage"] == "render" and r["step"] == 4 and r["clips_ready"] == 2
