import dataclasses
import inspect
from datetime import date, time

import pytest

from arena.manifest import (
    EVENTS_DIR,
    BoutRules,
    CupRules,
    ManifestError,
    Rating,
    Stage,
    Tug,
    all_events,
    higher_wins,
    load_event,
    load_manifest,
)

# A well-formed manifest, as TOML sections. Tests override one entry to build a
# specific malformation, so each test names only what it is breaking.
GOOD = {
    "root": 'id="probe"\ntitle="Probe"\nrig="legs"\ncategory="race"\n'
            'time_limit_s=10.0\nmetric="mean_finish_time"\nseeds=[1]\n',
    "kind": 'kind="perpetual"\n',
    "course": '[course]\nkind="lane"\nlength_m=1.0\nwidth_m=0.8\n'
              'wall_height_m=0.15\nslope_deg=0.0\n',
    "command": '[command]\nvel=[0.25,0,0]\nhead=[0,0,0,0]\nbody=[0,0,0,0,0,0]\n',
    "start": '[start]\nkeyframe="STAND"\nsettle_s=0.5\n'
             '[start.perturbation]\njoint_rad=0.01\nyaw_deg=2.0\n',
    "termination": '[termination]\nfall_gravity_z=-0.5\nfall_hold_s=0.3\n',
    "sweep": '[sweep]\nlo=0.2\nhi=0.4\nstep=0.1\nfinalists=1\n',
    "clip": "",
}


def write_manifest(tmp_path, **overrides):
    """Write a manifest that is well-formed except for the sections overridden."""
    sections = GOOD | overrides
    path = tmp_path / "probe.toml"
    path.write_text("".join(sections[key] for key in GOOD))
    return path


def test_sprint_loads():
    m = load_event("sprint-2m")
    assert m.id == "sprint-2m"
    assert m.rig == "legs"
    assert m.seeds == (1, 2, 3, 4, 5)
    assert m.course.length_m == 2.0
    assert m.time_limit_s == 50.0


def test_command_is_13_wide_with_velocity_first():
    m = load_event("sprint-2m")
    assert len(m.command) == 13
    assert m.command[:3] == (0.25, 0.0, 0.0)
    # head(4) and body(6) slots are zero-padded, as the runtime pads them.
    assert m.command[3:] == (0.0,) * 10


def test_a_manifest_is_hashable_and_compares_by_value():
    """frozen=True has to mean what it says.

    An ndarray command field would make this dataclass unhashable, make `==`
    return an elementwise array instead of a bool, and — worst — leave a loaded
    event mutable in place, so one stray write could corrupt the event for every
    later run in the same process.
    """
    a, b = load_event("sprint-2m"), load_event("sprint-2m")
    assert a == b
    assert len({a, b}) == 1


def test_every_shipped_event_loads():
    events = all_events()
    assert len(events) >= 1
    assert len({m.id for m in events}) == len(events), "duplicate event ids"


def test_shipped_events_span_more_than_one_rig():
    """The whole platform claim is that a new rig or course is data, not code.

    If every shipped event happened to share one rig, that claim would be
    untested by the fixture set itself — this guards against that regression.
    """
    rigs = {m.rig for m in all_events()}
    assert len(rigs) > 1


def test_unknown_event_is_an_error():
    with pytest.raises(ManifestError, match="no such event"):
        load_event("nope")


def test_the_probe_fixture_is_itself_valid(tmp_path):
    """Guards the helper: if the baseline were malformed, every test below would
    pass for the wrong reason."""
    assert load_manifest(write_manifest(tmp_path)).id == "probe"


def test_unknown_metric_is_rejected(tmp_path):
    path = write_manifest(
        tmp_path,
        root='id="probe"\ntitle="Probe"\nrig="legs"\ncategory="race"\ntime_limit_s=10.0\n'
             'metric="vibes"\nseeds=[1]\n',
    )
    with pytest.raises(ManifestError, match="unknown metric"):
        load_manifest(path)


def test_unknown_rig_is_rejected(tmp_path):
    path = write_manifest(
        tmp_path,
        root='id="probe"\ntitle="Probe"\nrig="hovercraft"\ncategory="race"\ntime_limit_s=10.0\n'
             'metric="mean_finish_time"\nseeds=[1]\n',
    )
    with pytest.raises(ManifestError, match="unknown rig"):
        load_manifest(path)


def test_command_width_is_validated(tmp_path):
    path = write_manifest(
        tmp_path,
        command='[command]\nvel=[0.25,0]\nhead=[0,0,0,0]\nbody=[0,0,0,0,0,0]\n',
    )
    with pytest.raises(ManifestError, match="vel must have 3"):
        load_manifest(path)


def test_empty_seeds_is_rejected(tmp_path):
    """An event with no seeds would score every entry as a mean of nothing."""
    path = write_manifest(
        tmp_path,
        root='id="probe"\ntitle="Probe"\nrig="legs"\ncategory="race"\ntime_limit_s=10.0\n'
             'metric="mean_finish_time"\nseeds=[]\n',
    )
    with pytest.raises(ManifestError, match="seeds must not be empty"):
        load_manifest(path)


def test_duplicate_seeds_are_rejected(tmp_path):
    """A repeated seed would run the same episode twice and weight it double."""
    path = write_manifest(
        tmp_path,
        root='id="probe"\ntitle="Probe"\nrig="legs"\ncategory="race"\ntime_limit_s=10.0\n'
             'metric="mean_finish_time"\nseeds=[1,1,2]\n',
    )
    with pytest.raises(ManifestError, match="duplicate seeds"):
        load_manifest(path)


def test_sweep_speeds_span_the_declared_range_inclusive():
    m = load_event("sprint-2m")
    speeds = m.sweep.speeds()
    assert speeds[0] == pytest.approx(m.sweep.lo)
    # The top of the range must be INCLUDED. Accumulating 0.05 twenty times from
    # 0.20 lands on 1.2000000000000002, so a bare `v <= hi` would silently drop
    # the fastest speed the event asked for.
    assert speeds[-1] == pytest.approx(m.sweep.hi)
    assert len(speeds) == 21
    assert speeds == tuple(sorted(set(speeds))), "speeds must be distinct and ascending"


def test_the_sweep_is_wide_enough_to_be_worth_running():
    """A one-point sweep would quietly restore the pinned-command behaviour.

    Except for a stage event: there it plays each entry's timeline (or the
    event's own command) rather than sweeping a speed, so it has no sweep.
    """
    for m in all_events():
        if m.sweep is None:
            continue
        speeds = m.sweep.speeds()
        assert len(speeds) >= 10, f"{m.id}: {len(speeds)} speeds is not a sweep"
        assert m.sweep.hi >= 2 * m.command[0], f"{m.id}: sweep tops out near the old pin"
        assert 1 <= m.sweep.finalists <= len(speeds)


def test_command_at_replaces_only_the_forward_speed():
    m = load_event("sprint-2m")
    swapped = m.command_at(0.85)
    assert swapped[0] == 0.85
    assert swapped[1:] == m.command[1:]
    assert len(swapped) == len(m.command)
    # The event itself is untouched: frozen has to survive a sweep of 21 calls.
    assert m.command[0] == 0.25


@pytest.mark.parametrize(
    "sweep,complaint",
    [
        ('[sweep]\nlo=0.2\nhi=0.4\nstep=0.0\nfinalists=1\n', "step"),
        ('[sweep]\nlo=0.2\nhi=0.4\nstep=-0.1\nfinalists=1\n', "step"),
        ('[sweep]\nlo=0.9\nhi=0.4\nstep=0.1\nfinalists=1\n', "hi"),
        ('[sweep]\nlo=0.2\nhi=0.4\nstep=0.1\nfinalists=0\n', "finalists"),
        ('[sweep]\nlo=0.2\nhi=0.4\nstep=0.1\n', "finalists"),
    ],
)
def test_a_malformed_sweep_is_rejected(tmp_path, sweep, complaint):
    """A sweep with no step would loop forever rather than fail, so this is
    validation with teeth and not a courtesy message."""
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(write_manifest(tmp_path, sweep=sweep))


def test_a_missing_sweep_section_is_rejected(tmp_path):
    path = tmp_path / "probe.toml"
    path.write_text("".join(
        GOOD[key] for key in GOOD if key != "sweep"
    ))
    with pytest.raises(ManifestError, match="sweep"):
        load_manifest(path)


# A stage's sections, over GOOD: [course] names its kind, its floor and its cap, and there is no [sweep].
STAGE = {"course": '[course]\nkind="stage"\nsize_m=[2.0,3]\nmax_ducks=2\n', "sweep": ""}


def test_a_stage_loads_with_no_lane_and_no_sweep(tmp_path):
    m = load_manifest(write_manifest(tmp_path, **STAGE))
    assert m.course == Stage(size_m=(2.0, 3.0), max_ducks=2)
    assert m.course.kind == "stage"
    assert m.sweep is None


@pytest.mark.parametrize(
    "lines, complaint",
    [
        ("max_ducks=2\n", r"\[course\]: missing 'size_m'"),
        ("size_m=[2.0,3.0]\n", r"\[course\]: missing 'max_ducks'"),
        ("size_m=2.0\nmax_ducks=2\n", r"size_m must be two positive numbers, depth along x then width along y, got 2\.0"),
        ("size_m=[2.0]\nmax_ducks=2\n", r"size_m must be two positive numbers"),
        ("size_m=[2.0,3.0,1.0]\nmax_ducks=2\n", r"size_m must be two positive numbers"),
        ("size_m=[2.0,0.0]\nmax_ducks=2\n", r"size_m must be two positive numbers"),
        ("size_m=[-2.0,3.0]\nmax_ducks=2\n", r"size_m must be two positive numbers"),
        ('size_m=[2.0,"3"]\nmax_ducks=2\n', r"size_m must be two positive numbers"),
        ("size_m=[true,3.0]\nmax_ducks=2\n", r"size_m must be two positive numbers"),
        ("size_m=[2.0,3.0]\nmax_ducks=0\n", r"max_ducks must be a whole number of at least 1, got 0"),
        ("size_m=[2.0,3.0]\nmax_ducks=1.5\n", r"max_ducks must be a whole number of at least 1, got 1\.5"),
        ("size_m=[2.0,3.0]\nmax_ducks=true\n", r"max_ducks must be a whole number of at least 1, got True"),
    ],
)
def test_a_stages_floor_and_cap_are_checked(tmp_path, lines, complaint):
    course = '[course]\nkind="stage"\n' + lines
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(write_manifest(tmp_path, course=course, sweep=""))


def test_a_stage_refuses_a_lanes_geometry(tmp_path):
    course = '[course]\nkind="stage"\nlength_m=2.0\n'
    with pytest.raises(ManifestError, match=r"\[course\]: unknown keys \['length_m'\]"):
        load_manifest(write_manifest(tmp_path, course=course, sweep=""))


def test_a_stage_refuses_a_sweep(tmp_path):
    with pytest.raises(ManifestError, match=r"takes no \[sweep\]"):
        load_manifest(write_manifest(tmp_path, course=STAGE["course"]))


def test_a_stage_plays_one_seed(tmp_path):
    root = GOOD["root"].replace("seeds=[1]", "seeds=[1,2]")
    with pytest.raises(ManifestError, match="exactly one seed"):
        load_manifest(write_manifest(tmp_path, root=root, **STAGE))


# The programme. Written out rather than derived, so
# that adding an event fails this test until someone chooses its category on
# purpose — which is the whole reason the field is required.
EXPECTED_CATEGORIES = {
    "sprint-2m": "race",
    "roller-sprint-2m": "race",
    "hill-climb-1m5": "race",
    "sock-heist-6m": "race",
    "got-a-talent": "showcase",
    "tug-of-war": "versus",
}


def test_the_programme_is_categorised_as_designed():
    assert {m.id: m.category for m in all_events()} == EXPECTED_CATEGORIES


def test_an_unknown_category_is_refused(tmp_path):
    path = write_manifest(tmp_path, root=GOOD["root"].replace('category="race"', 'category="sprint"'))
    with pytest.raises(ManifestError, match="unknown category"):
        load_manifest(path)


def test_a_missing_category_is_refused(tmp_path):
    """No default: `order` has a safe one, `category` does not.
    Defaulting to "race" is exactly the bug this field exists to fix."""
    path = write_manifest(tmp_path, root=GOOD["root"].replace('category="race"\n', ""))
    with pytest.raises(ManifestError, match="missing 'category'"):
        load_manifest(path)


def test_the_programme_has_a_declared_order_with_the_sprint_first():
    """Declared, not derived: neither alphabetical nor filesystem order is the
    order a person wants to read a race card in."""
    programme = sorted(all_events(), key=lambda m: (m.order, m.title))
    assert [m.id for m in programme] == [
        "sprint-2m",
        "got-a-talent",
        "roller-sprint-2m",
        "hill-climb-1m5",
        "tug-of-war",
        "sock-heist-6m",
    ]


def test_an_event_without_an_order_sorts_last_rather_than_first():
    """A new manifest that forgets the field must not jump the queue."""
    m = load_manifest(write_manifest(tmp_path_for_order()))
    assert m.order == 100


def tmp_path_for_order():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())


def test_an_event_without_a_vote_section_has_no_vote_rules():
    assert load_event("sprint-2m").vote is None


def test_got_a_talent_declares_its_ballot_and_its_window():
    vote = load_event("got-a-talent").vote
    assert (vote.ballot_min, vote.ballot_max) == (2, 4)
    assert (vote.window_days, vote.per_day) == (7, 20)


def test_got_a_talent_is_a_stage_played_once_for_20_s():
    talent, sprint = load_event("got-a-talent"), load_event("sprint-2m")
    assert talent.course == Stage(size_m=(2.6, 3.8), max_ducks=8)
    assert talent.sweep is None
    assert talent.seeds == (1,)
    assert talent.time_limit_s == 20.0
    # An entry without a timeline stands still: the all-zero command.
    assert talent.command == (0.0,) * 13
    assert talent.start == sprint.start
    assert talent.termination == sprint.termination
    assert talent.metric == "votes"


def test_a_vote_section_is_validated_loudly(tmp_path):
    base = (EVENTS_DIR / "got-a-talent.toml").read_text()
    for bad, message in [
        ("ballot_min  = 1", "ballot_min"),
        ("ballot_max  = 1", "ballot_max"),
        ("window_days = 0", "window_days"),
        ("per_day     = 0", "per_day"),
    ]:
        key = bad.split()[0]
        broken = "\n".join(
            bad if line.startswith(key) else line for line in base.splitlines()
        )
        path = tmp_path / "broken.toml"
        path.write_text(broken)
        with pytest.raises(ManifestError, match=message):
            load_manifest(path)


def test_ballot_max_cannot_outgrow_the_voting_page_s_colour_palette(tmp_path):
    """The voting page has exactly 5 lane colours (LANE_CSS in course.js). A
    ballot_max above that would put two lanes in the same colour, which is
    unvotable in a feature whose whole premise is "pick a colour"."""
    base = (EVENTS_DIR / "got-a-talent.toml").read_text()
    broken = "\n".join(
        "ballot_max  = 6" if line.startswith("ballot_max") else line
        for line in base.splitlines()
    )
    path = tmp_path / "broken.toml"
    path.write_text(broken)
    with pytest.raises(ManifestError, match="ballot_max"):
        load_manifest(path)


def test_ranking_on_votes_without_a_vote_section_is_refused(tmp_path):
    base = (EVENTS_DIR / "sprint-2m.toml").read_text()
    path = tmp_path / "no-rules.toml"
    path.write_text(base.replace('metric       = "mean_finish_time"', 'metric       = "votes"'))
    with pytest.raises(ManifestError, match="votes"):
        load_manifest(path)


def test_a_vote_section_without_metric_votes_is_refused(tmp_path):
    """`[vote]` and `metric = "votes"` imply each other, in both directions.

    Without this direction, adding `[vote]` to a timed event's manifest alone
    would leave `routes_read._voted()` (keyed on `[vote]`) treating it as
    voted while `event_leaderboard` (keyed on `metric`) kept ranking it on
    time — the two readings would diverge silently.
    """
    base = (EVENTS_DIR / "got-a-talent.toml").read_text()
    path = tmp_path / "vote-without-metric.toml"
    path.write_text(base.replace('metric       = "votes"', 'metric       = "mean_finish_time"'))
    with pytest.raises(ManifestError, match="vote"):
        load_manifest(path)


def test_every_shipped_events_metric_has_a_scoring_function():
    """`manifest.py` validates which metric NAMES an event may declare;
    `evaluate.py` holds a second registry mapping that name to the function
    that computes a run's score. A manifest naming a metric with no entry
    there is unreachable — `evaluate()` and `evaluate_at()` both raise
    `KeyError` the instant anyone enters it — and nothing else catches this,
    because every other test fabricates RunRecords directly rather than
    running `evaluate()` against a real manifest.
    """
    from arena.evaluate import METRICS as SCORERS

    for m in all_events():
        assert m.metric in SCORERS, f"{m.id}: no evaluate.METRICS entry for {m.metric!r}"


def test_category_never_reaches_scoring_storage_or_the_run_record():
    """`category` is display-only: which wall a flyer hangs on, nothing more.

    It must never influence how a run is scored, how it is stored, how points
    are folded, or what a RunRecord carries — a scoring rule that read it
    would let event authors game the board by relabelling an event, and a
    stored field would be a second place category could drift from the
    manifest. This was checked by hand with grep during review; nothing kept
    it checked, so it is cheap for a category to sneak back in unnoticed.
    """
    from arena import evaluate, points, store

    for module in (evaluate, points, store):
        src = inspect.getsource(module)
        assert "category" not in src.lower(), f"'category' appears in {module.__name__}"

    field_names = {f.name for f in dataclasses.fields(store.RunRecord)}
    assert "category" not in field_names, "RunRecord carries a 'category' field"


def test_an_event_without_a_clip_section_gets_the_defaults():
    clip = load_event("sprint-2m").clip
    assert clip.tape_max_s == 12.0
    assert clip.sounds == ("crowd", "horn", "verdict")
    assert clip.camera.kind == "chase"
    assert clip.camera.side is None
    assert clip.to_dict() == {
        "tape_max_s": 12.0,
        "sounds": ["crowd", "horn", "verdict"],
        "camera": {"kind": "chase", "back": 0.35, "height": 0.34, "side": None,
                   "target_height": 0.12, "fov": 42.0, "track": False, "hold": None},
    }


def test_a_clip_section_pins_the_tape_a_fixed_camera_and_the_sounds(tmp_path):
    path = write_manifest(
        tmp_path,
        clip='[clip]\ntape_max_s=6.0\nsounds=["crowd"]\n'
             '[clip.camera]\nkind="fixed"\nposition=[1.0,0.6,2.2]\ntarget=[1.0,0.1,0.0]\nfov=40\n',
    )
    clip = load_manifest(path).clip
    assert clip.tape_max_s == 6.0
    assert clip.sounds == ("crowd",)
    assert clip.camera.to_dict() == {
        "kind": "fixed", "position": [1.0, 0.6, 2.2], "target": [1.0, 0.1, 0.0], "fov": 40.0
    }


def test_a_chase_can_track_its_leader_and_hold_short_of_the_line(tmp_path):
    path = write_manifest(
        tmp_path,
        clip='[clip]\n[clip.camera]\nkind="chase"\nback=2.1\nheight=0.86\ntrack=true\nhold=1\n',
    )
    camera = load_manifest(path).clip.camera
    assert (camera.track, camera.hold) == (True, 1.0)
    assert camera.to_dict() == {
        "kind": "chase", "back": 2.1, "height": 0.86, "side": None,
        "target_height": 0.12, "fov": 42.0, "track": True, "hold": 1.0,
    }


def test_a_performance_is_filmed_whole_without_a_start_horn():
    clip = load_event("got-a-talent").clip
    assert (clip.tape_max_s, clip.sounds) == (20.0, ("crowd", "verdict"))


@pytest.mark.parametrize(
    "section, said",
    [
        ('[clip]\nsounds=["crowd","organ"]\n', "unknown sound source"),
        ('[clip]\ntape_max_s=0\n', "tape_max_s must be positive"),
        ('[clip]\nspeed=4\n', r"unknown keys \['speed'\]"),
        ('[clip]\nsounds=["giant"]\n', r"the giant's sound goes with \[lights\]"),
        ('[clip]\nfoo=1\n', "unknown keys"),
        ('[clip]\n[clip.camera]\nkind="drone"\n', "unknown camera kind"),
        ('[clip]\n[clip.camera]\nkind="fixed"\nfov=40\n', "needs position and target"),
        ('[clip]\n[clip.camera]\nkind="chase"\nposition=[0,0,0]\n', "unknown keys"),
        ('[clip]\n[clip.camera]\nkind="chase"\ntrack="yes"\n', "track must be true or false, got 'yes'"),
        ('[clip]\n[clip.camera]\nkind="chase"\nhold=-1\n', "hold must be a distance of at least 0 m, got -1"),
        ('[clip]\n[clip.camera]\nkind="chase"\nhold=true\n', "hold must be a distance of at least 0 m, got True"),
        ('[clip]\n[clip.camera]\nkind="fixed"\nposition=[0,0,0]\ntarget=[1,0,0]\ntrack=true\n', "unknown keys"),
    ],
)
def test_a_malformed_clip_section_is_refused(tmp_path, section, said):
    with pytest.raises(ManifestError, match=said):
        load_manifest(write_manifest(tmp_path, clip=section))


def test_every_shipped_event_takes_perpetual_policies():
    """What `publish` writes for a gait, and what the Space checks a manifest's `kind` against."""
    assert {e.id: e.kind for e in all_events()} == {e.id: "perpetual" for e in all_events()}


def test_an_unknown_kind_is_refused(tmp_path):
    with pytest.raises(ManifestError, match="unknown kind"):
        load_manifest(write_manifest(tmp_path, kind='kind="forever"\n'))


def test_a_missing_kind_is_refused(tmp_path):
    """No default: an entry's manifest is checked against it, and a guessed kind would
    admit or refuse the wrong policies without anyone having decided which."""
    with pytest.raises(ManifestError, match="missing 'kind'"):
        load_manifest(write_manifest(tmp_path, kind=""))


CUP = '[cup]\nfirst="2026-10-30"\npremiere="18:00"\ntimezone="Europe/Paris"\nclose_before_h=2.0\nmin_entrants=4\n'

RATING = '[rating]\nreference="tug-reference-t20-500.onnx"\npit_bonus_cm=100.0\n'

TUG = {
    "root": GOOD["root"].replace('category="race"', 'category="versus"').replace('"mean_finish_time"', '"mean_ground_cm"'),
    "course": '[course]\nkind="tug"\nring_m=3.0\npit_m=0.3\npit_depth_m=0.3\nstring_m=1.0\n',
    "sweep": RATING + '[bout]\ntime_limit_s=10.0\nbouts_to_win=2\nmax_bouts=5\n',
    "clip": CUP,
}


def test_the_tug_of_war_loads(tmp_path):
    m = load_event("tug-of-war")
    assert m.course == Tug(3.0, 0.3, 0.3, 1.0)
    assert m.rating == Rating("tug-reference-t20-500.onnx", 100.0)
    assert m.bout == BoutRules(45.0, 2, 5)
    assert (m.category, m.metric, m.rig, m.time_limit_s, m.clip.tape_max_s) == ("versus", "mean_ground_cm", "legs", 45.0, 45.0)
    assert m.sweep is None and m.vote is None and m.command[:3] == (-0.3, 0.0, 0.0)
    assert load_manifest(write_manifest(tmp_path, **TUG)).course.kind == "tug"


@pytest.mark.parametrize("change, complaint", [
    ({"root": TUG["root"].replace('"versus"', '"race"')}, "goes with"),
    ({"root": TUG["root"].replace('"mean_ground_cm"', '"mean_finish_time"')}, "goes with"),
    ({"course": GOOD["course"], "sweep": GOOD["sweep"]}, "goes with"),
    ({"sweep": TUG["sweep"].split("[bout]")[0]}, r"needs \[bout\]"),
    ({"sweep": "[bout]" + TUG["sweep"].split("[bout]")[1]}, r"needs \[rating\]"),
    ({"sweep": TUG["sweep"].replace("t20-500", "t9")}, r"\[rating\] reference"),
    ({"sweep": TUG["sweep"].replace('"tug-', '"../policies/tug-')}, r"\[rating\] reference"),
    ({"sweep": TUG["sweep"].replace("pit_bonus_cm=100.0", "pit_bonus_cm=0.0")}, r"\[rating\] pit_bonus_cm"),
    ({"sweep": TUG["sweep"].replace("pit_bonus_cm=100.0", "pit_bonus_cm=100.0\nopponent=1")}, "unknown keys"),
    ({"sweep": TUG["sweep"].replace("time_limit_s=10.0\nbouts", "time_limit_s=12.0\nbouts")}, "time_limit_s is its bouts'"),
    ({"sweep": TUG["sweep"] + GOOD["sweep"]}, r"no \[sweep\]"),
    ({"sweep": TUG["sweep"] + "[vote]\nballot_min=2\nballot_max=4\nwindow_days=7\nper_day=3\n"}, r"no \[vote\]"),
    ({"root": TUG["root"].replace('rig="legs"', 'rig="rollers"')}, "rig 'legs'"),
    ({"course": TUG["course"] + "slope_deg=0.0\n"}, "unknown keys"),
    ({"course": TUG["course"] + "length_m=4.0\n"}, "unknown keys"),
    ({"course": TUG["course"].replace("pit_m=0.3", "pit_m=1.2")}, r"pit must be narrower than its string"),
    ({"course": TUG["course"].replace("string_m=1.0", "string_m=3.5")}, r"shorter than its ring"),
    ({"sweep": TUG["sweep"] + "draws=1\n"}, "unknown keys"),
    ({"sweep": TUG["sweep"].replace("max_bouts=5", "max_bouts=2")}, r"probe\.toml: \[bout\] max_bouts"),
    ({"sweep": TUG["sweep"].replace("time_limit_s=10.0\nbouts", "time_limit_s=0.01\nbouts")}, r"probe\.toml: \[bout\] time_limit_s"),
    ({"sweep": TUG["sweep"].replace("bouts_to_win=2", "bouts_to_win=0")}, r"probe\.toml: \[bout\] bouts_to_win"),
])
def test_a_malformed_tug_is_refused(tmp_path, change, complaint):
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(write_manifest(tmp_path, **(TUG | change)))


@pytest.mark.parametrize("section", [RATING, "[bout]\ntime_limit_s=10.0\nbouts_to_win=2\nmax_bouts=5\n"])
def test_only_a_tug_takes_a_rating_or_bouts(tmp_path, section):
    with pytest.raises(ManifestError, match="only a tug"):
        load_manifest(write_manifest(tmp_path, sweep=GOOD["sweep"] + section))


def test_higher_wins_reads_the_events_metric():
    assert higher_wins("tug-of-war") and not any(map(higher_wins, ("sprint-2m", "got-a-talent", "no-such-event")))


def tug(tmp_path, cup=CUP):
    """The shipped tug of war with its [cup], its last section, replaced."""
    path = tmp_path / "tug.toml"
    path.write_text((EVENTS_DIR / "tug-of-war.toml").read_text().split("[cup]")[0] + cup)
    return path


def test_the_tug_of_war_holds_a_weekly_cup():
    assert load_event("tug-of-war").cup == CupRules(date(2026, 11, 6), time(18, 0), "Europe/Paris", 2.0, 4)
    assert load_event("sprint-2m").cup is None


def test_a_versus_event_needs_a_cup(tmp_path):
    with pytest.raises(ManifestError, match=r"\[cup\]"):
        load_manifest(tug(tmp_path, cup=""))


def test_only_a_versus_event_takes_a_cup(tmp_path):
    with pytest.raises(ManifestError, match=r"\[cup\]"):
        load_manifest(write_manifest(tmp_path, clip=CUP))


@pytest.mark.parametrize("old, new, complaint", [
    ('"Europe/Paris"', '"Mars/Olympus"', "timezone"), ('"2026-10-30"', '"2026-13-01"', "first"),
    ('"18:00"', '"6pm"', "premiere"), ("close_before_h=2.0", "close_before_h=0", "close_before_h"),
    ("min_entrants=4", "min_entrants=2", "min_entrants"),
    ("min_entrants=4", "min_entrants=4\nseeded=true", "unknown keys"),
])
def test_a_malformed_cup_is_refused(tmp_path, old, new, complaint):
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(tug(tmp_path, cup=CUP.replace(old, new)))


def test_the_image_carries_the_time_zones():
    dockerfile = (EVENTS_DIR.parents[1] / "Dockerfile").read_text()
    assert "tzdata" in dockerfile and "ZoneInfo('Europe/Paris')" in dockerfile
