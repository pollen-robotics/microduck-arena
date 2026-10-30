"""The bible is data the owner edits; the code only checks it and picks from it."""

import json
import random
import re

import pytest

from arena.commentary.context import Fact
from arena.commentary.lore import Lore, Memory, load, select_memories


def test_the_shipped_bible_is_well_formed():
    lore = load()
    assert set(lore.characters) == {"peter", "ray"}
    assert lore.characters["peter"]["name"] == "Peter Duckry"
    assert len(lore.scenes) == 8
    assert len(set(lore.scenes)) == len(lore.scenes)
    assert len(lore.memories) >= 24
    assert len({m.id for m in lore.memories}) == len(lore.memories)
    assert all(m.tags for m in lore.memories)


def test_a_malformed_bible_is_refused(tmp_path):
    path = tmp_path / "lore.json"
    good = {"characters": {"peter": {"name": "P", "sheet": "s"}, "ray": {"name": "R", "sheet": "s"}},
            "scenes": ["A quiet scene."],
            "memories": [{"id": "a", "tags": ["hill"], "memory": "Once."}]}
    for broken in (
        {**good, "memories": good["memories"] * 2},                                   # duplicate id
        {**good, "memories": [{"id": "a", "tags": [], "memory": "Once."}]},             # no tags
        {**good, "memories": [{"id": "a", "tags": ["hill"], "memory": "x" * 401}]},     # too long
        {**good, "memories": [{"id": "a", "tags": ["hill"], "memory": "see /tmp/x"}]},  # technical
        {**good, "memories": ["Once."]},                                          # not an object
        {**good, "characters": {"peter": good["characters"]["peter"]}},               # ray missing
        {k: v for k, v in good.items() if k != "scenes"},                        # scenes missing
        {**good, "scenes": []},                                                    # scenes empty
        {**good, "scenes": ["see clips/R1/x.mp4"]},                           # scene is technical
        {**good, "scenes": [1]},                                              # scene is not a string
        {**good, "scenes": ["A quiet scene.", "A quiet scene."]},                # duplicate scene
        ["a bible that is a list"],                                              # not an object
    ):
        path.write_text(json.dumps(broken))
        with pytest.raises(ValueError):
            load(path)


def test_selection_draws_among_the_memories_that_match_and_skips_recent():
    lore = Lore(characters={}, scenes=("A quiet scene.",), memories=(
        Memory("throne", ("podium", "first-run"), "The throne."),
        Memory("queue", ("podium",), "The queue."),
        Memory("newcomer", ("first-run",), "The newcomer."),
        Memory("slope", ("hill", "fall"), "The slope."),
    ))
    facts = [Fact("run#/board", "...", "result", ("podium",)),
             Fact("notable#/first-ever", "...", "notable", ("first-run",))]
    drawn = {frozenset(m.id for m in select_memories(lore, facts, set(), random.Random(seed)))
             for seed in range(50)}
    # Every pair of the three that match comes up: the same two are not offered every time.
    assert drawn == {frozenset(pair) for pair in
                     (("throne", "queue"), ("throne", "newcomer"), ("queue", "newcomer"))}
    assert {m.id for m in select_memories(lore, facts, {"throne"}, random.Random(0))} == {
        "queue", "newcomer"}
    assert select_memories(lore, [Fact("x", "...", "result", ("sprint",))], set(),
                           random.Random(0)) == []
    assert len(select_memories(lore, facts, set(), random.Random(0), limit=1)) == 1


def test_the_heists_memories_tell_of_the_giant():
    heist = [m for m in load().memories if {"lights", "caught"} & set(m.tags)]
    assert {"lights", "caught"} <= {tag for m in heist for tag in m.tags}
    for memory in heist:
        assert not re.search(r"caller|red light|reachy", memory.memory, re.IGNORECASE), memory.id
