import animate, config

def test_stage_boundaries():
    assert animate.stage_for(0) == 'calm'
    assert animate.stage_for(59.9) == 'calm'
    assert animate.stage_for(60) == 'nudging'
    assert animate.stage_for(300) == 'agitated'
    assert animate.stage_for(900) == 'frantic'

def test_base_colour_not_red_before_frantic():
    assert animate.base_colour('question', 899) == config.COLOURS['question']

def test_base_colour_blends_to_red():
    assert animate.base_colour('finished', 900) == config.COLOURS['finished']
    assert animate.base_colour('finished', 900 + config.RED_BLEND_S) == config.RED
    assert animate.base_colour('finished', 99999) == config.RED

def test_frame_brightness_capped_per_stage():
    peak = max(max(animate.frame('permission', 10, t / 100)) for t in range(400))
    assert 0 < peak <= round(255 * config.BRIGHTNESS['calm']) + 1

def test_frame_frantic_reaches_full():
    peak = max(max(animate.frame('question', 2000, t / 1000)) for t in range(200))
    assert peak >= 250

def test_frame_values_are_ints_in_range():
    for t in range(100):
        c = animate.frame('question', 400, t / 37)
        assert all(isinstance(v, int) and 0 <= v <= 255 for v in c)

def test_multi_blink_inserts_dark_and_bright():
    frames = [animate.frame('finished', 10, config.MULTI_EVERY_S * 3 + i / 100, waiting_count=2) for i in range(40)]
    assert any(max(f) == 0 for f in frames)
    assert any(max(f) >= 250 for f in frames)  # calm alone never gets this bright
    single = [animate.frame('finished', 10, config.MULTI_EVERY_S * 3 + i / 100) for i in range(40)]
    assert all(max(f) < 250 for f in single)

def test_offline_frame_mostly_off():
    frames = [animate.offline_frame(i / 50) for i in range(int(config.OFFLINE_EVERY_S * 50))]
    assert sum(1 for f in frames if max(f) > 0) < len(frames) / 5

def test_anim_time_stays_small_and_continuous():
    # float32 on the board: keep t small so 0.1 s slots stay exact
    assert animate.anim_time(10**9) < config.CYCLE_MS / 1000
    assert animate.anim_time(config.CYCLE_MS + 250) == 0.25

def test_cycle_is_multiple_of_every_period():
    periods = list(config.PERIOD_S.values()) + [config.MULTI_EVERY_S, config.OFFLINE_EVERY_S]
    for p in periods:
        assert round(config.CYCLE_MS % round(p * 1000)) == 0, p
