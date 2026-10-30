# 6 m Sock Heist

Sneak 6 metres up to a giant microduck's nest and steal its socks without being seen. The lowest
average time wins.

## The giant

A giant microduck sits in its nest of socks past the finish line, its back to the lanes. Every few
seconds it turns its head round over its shoulder to look at the lanes, with a very deep quack, and
the turn takes **0.4 seconds**. From the moment it faces the lanes until it looks away, a duck whose
trunk moves more than **3 cm** across the floor from where it stood is caught: its motors switch off,
it collapses where it stands, and that attempt ends there.

## When it looks

The giant looks at random moments, different on each of the five starts and the same for every entry.
It first starts to turn **0.6 to 1.0 s** after the start, so a duck that bolts off the line has to stop
as hard as it started. Then it looks for **1.4 to 2.4 s** at a time, and away for **1.6 to 3.0 s**.

## What the policy sees

Only its command, as on every race. From the moment the giant starts to turn its head until it looks
away, the Arena asks the policy to stand still: the forward, sideways and turn rates drop to zero, so
the turn is its time to stop. The policy never sees the giant, the clock or the lane. A walk that stops
dead on a zero command, holds still while watched, and starts again cleanly does well.

## The lane

Nobody walks six metres straight unaided. While the giant looks away, the Arena steers the duck
through its command: the turn rate aims it at the middle of the lane half a metre ahead, at no more
than **1 rad/s**. A walk that follows a turn command holds its lane; one that ignores it drifts into a
wall.

## Train

Open **Train my own robot** on the challenge page, or run this in a terminal:

```bash
uv run https://pollen-robotics-microduck-arena.hf.space/workshop.py sock-heist-6m
```

Its training stops the duck at random moments, as the giant does. Get a walk that stops dead on a zero
command and starts again cleanly first, then make it faster.

## Scoring

The Arena scans forward commands from **0.20 to 1.20 m/s** in 0.05 steps. It tests three shortlisted
speeds over five starts and keeps the best average. Each fall, catch or timeout counts as
**40 seconds**, the time limit.

For example, four 24-second finishes and one catch score **27.2 seconds**.

[How the workshop works, and the shell path →](../train-a-policy.md)
