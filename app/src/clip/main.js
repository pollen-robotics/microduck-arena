// The clip: the page the recorder photographs one frame at a time. It draws
// nothing on a clock of its own — the recorder asks for frame i, gets it, and
// asks for the soundtrack once. ?run=<id>&layout=landscape|vertical&frame=N, or
// ?match=<id> for a cup's match.

import { getBoutSettle, getBoutString, getBoutTrace, getMatch, getRun, getSettle, getString, getTrace } from "../api.js";
import { boutLane } from "../bouts.js";
import { credit, replaySeed, stageDucks } from "../cast.js";
import { LANE_COLORS } from "../course.js";
import { formatScore, isStage, isTug } from "../format.js";
import { lanesFor } from "../lanes.js";
import { CTRL_DT, TRACE_WIDTH, frameCount, leadIn, standing } from "../replay.js";
import { ratingLane } from "../tug.js";
import { createViewer } from "../viewer.js";
import { boutAt, matchPlan, matchWords, scoreAt } from "./match.js";
import { actAt, clipPlan, stampAt, stampLane, stepAt, travelAt } from "./plan.js";
import { stadiumDirection } from "./direction.js";
import { clipScore, clipVerdict, matchScore } from "./score.js";
import { renderSoundtrack } from "./soundtrack.js";

/** How far the chase camera stands per layout, as a factor on the viewer's
 * offsets. Measured on a three-lane sprint: 1.0 left the ducks small in a
 * 1080p frame, 0.55 crushed the far lane behind the near one; the portrait
 * frame wants a little more room than the landscape. A tug's chase takes none:
 * the viewer fits its span to the frame (tug.js tugPose). */
const DISTANCE = { landscape: 0.7, vertical: 0.8 };

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const layout = params.get("layout") === "vertical" ? "vertical" : "landscape";
document.documentElement.dataset.layout = layout;

function clock(step) {
  const seconds = step * CTRL_DT;
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(Math.floor(seconds % 60)).padStart(2, "0");
  const cc = String(Math.floor((seconds % 1) * 100)).padStart(2, "0");
  return `${mm}:${ss}.${cc}`;
}

/** The words on the frame, from the run and nothing else. */
function letter(run) {
  const stage = isStage(run.event);
  const who = `@${run.user} · ${run.policy_name}`;
  const earned = run.receipts.reduce((sum, r) => sum + r.points, 0);
  for (const id of ["top-title", "intro-title"]) $(id).textContent = run.event.title;
  // The captions credit a troupe whole; the recorder's tag keeps to its author.
  for (const id of ["top-participant", "intro-line"]) $(id).textContent = credit(run);
  $("osd-rec").textContent = `REC · ${who}`;
  $("osd-event").textContent = run.event.title.toUpperCase();
  $("fig-time").textContent = formatScore(run.score, { finished: run.seeds_finished, metric: run.event.metric });
  // A performance's number is its length, and votes rank it: no place to give at publication.
  if (stage) {
    $("fig-time").nextElementSibling.textContent = "length";
    $("fig-place").parentElement.hidden = true;
  } else {
    // A rated run's number is its rating, and it ranks the board.
    if (isTug(run.event)) $("fig-time").nextElementSibling.textContent = "rating";
    $("fig-place").textContent = run.on_board && !run.withdrawn ? `#${run.rank}` : "—";
  }
  $("fig-points").textContent = earned > 0 ? `+${earned}` : "—";
  const stamp = $("stamp");
  const said = clipVerdict(run);
  stamp.textContent = said.stamp;
  stamp.classList.add(said.pass ? "stamp-pass" : "stamp-fail");
}

/** The words on a match's frame: the cup, who meets whom, and the winner on the stamp, centred. */
function matchLetter(match) {
  const words = matchWords(match);
  for (const id of ["top-title", "intro-title"]) $(id).textContent = words.title;
  for (const id of ["top-participant", "intro-line"]) $(id).textContent = words.line;
  $("osd-rec").textContent = `REC · ${words.line}`;
  $("osd-event").textContent = words.title.toUpperCase();
  const stamp = $("stamp");
  stamp.textContent = words.outro;
  stamp.classList.add("stamp-pass");
  Object.assign(stamp.style, { left: "50%", top: "45%" });
}

function base64(bytes) {
  return new Promise((done) => {
    const reader = new FileReader();
    reader.onload = () => done(reader.result.split(",")[1]);
    reader.readAsDataURL(new Blob([bytes]));
  });
}

/** What the recorder drives: the plan, the score, a frame at a time and the soundtrack; then the
 * frame the page was asked for. */
function expose(plan, score, draw) {
  let pcm = null;
  window.clip = {
    plan,
    score,
    layout,
    draw,
    ready: true,
    error: null,
    /** Renders the whole soundtrack; resolves to its byte length. */
    async soundtrack() {
      pcm = new Uint8Array((await renderSoundtrack(score, plan.seconds)).buffer);
      return pcm.byteLength;
    },
    /** One slice of it, base64, for a transfer in bounded pieces. */
    chunk(offset, size) {
      return base64(pcm.subarray(offset, Math.min(offset + size, pcm.byteLength)));
    },
  };
  draw(Number(params.get("frame") ?? plan.poster));
}

async function main() {
  const run = await getRun(params.get("run"));
  const lanes = lanesFor(run);
  const stage = isStage(run.event);
  const tug = isTug(run.event);
  // One trace and one settle per duck: a race's lane has one, a stage's troupe every duck; a tug's
  // lane its string too, settle and all.
  const seed = replaySeed(run.event, run); // a lights event: every lane plays the run's own trace seed
  const [traces, settles, strings] = await Promise.all([
    Promise.all(lanes.map((lane) => getTrace(lane.run_id, seed))),
    Promise.all(lanes.map((lane) => getSettle(lane.run_id, seed).then(standing))),
    Promise.all(tug ? lanes.map((lane) => getString(lane.run_id)) : []),
  ]);
  // Every lane from where its ducks stand, all in step.
  const settle = Math.max(...settles.map(([first]) => frameCount(first)));
  const replays = lanes.map((_, i) => leadIn(settles[i][0], traces[i][0], settle, TRACE_WIDTH));
  // A stage plays the author's performance alone: every duck of its troupe from its settle. Each
  // beak moves on the stage; the clip's soundtrack plays the voices. A tug plays its bout
  // against the reference duck, each settle handed over apart, the string's beside them.
  const ducks = stage
    ? stageDucks(lanes[0].cast, traces[0], settles[0], { livery: lanes[0].livery, eventRig: run.event.rig, lead: settle })
    : [];
  const config = run.event.clip;
  const camera = tug ? config.camera : { ...config.camera, distance: DISTANCE[layout] };
  const viewer = await createViewer($("stage"), { rig: run.event.rig, lights: Boolean(run.event.lights), manual: true, camera });
  viewer.setLanes(
    lanes
      .map((lane, i) => ({
        runId: lane.run_id,
        livery: lane.livery,
        colour: LANE_COLORS[i % LANE_COLORS.length],
        opacity: 1,
        name: `@${lane.user}`,
        // A lane's caught frame counts after its settle lead-in (lights.js laneOut).
        ...(stage
          ? { ducks }
          : tug
            ? ratingLane(traces[i], settles[i], strings[i], { traceSeed: run.trace_seed, livery: lane.livery, name: `@${lane.user}` })
            : {
                trace: replays[i],
                lead: settle,
                ...(run.event.lights && { traceSeed: run.trace_seed, caught: traces[i].caught }),
              }),
      }))
      // The camera stands beyond the last lane: reversed, the author's duck is
      // the one in the foreground, still in the colour its page gives it.
      .reverse(),
    run.event,
    { loop: false },
  );
  const plan = clipPlan(
    run.event.lights ? Math.max(...traces.map(([t]) => frameCount(t))) : frameCount(traces[0][0]),
    config.tape_max_s,
    settle,
  );
  const score = clipScore({ run, plan, trace: replays[0], ducks, lanes: traces.map((t) => ({ trace: t[0], caught: t.caught })) });
  const crowdDirection = stadiumDirection(score.crowd ?? {});
  letter(run);

  /** Frame `i` of the plan. Returns the trace step it drew. */
  function draw(i) {
    const act = actAt(plan, i);
    const step = stepAt(plan, i);
    viewer.frame(step * CTRL_DT, travelAt(plan, i), i / plan.fps, crowdDirection);
    // The clock starts where the record's does, after the settle, and stops on
    // the author's last step while the rivals race on.
    $("osd-clock").textContent = clock(Math.max(0, Math.min(step, plan.steps - 1) - plan.settle));
    document.documentElement.dataset.act = act;
    $("intro").hidden = act !== "intro";
    $("stamp").hidden = act !== "outro";
    $("sheet").hidden = !(act === "outro" || layout === "vertical");
    if (act === "outro") {
      // Reversed for the viewer, the author's lane is its last. The stamp lands
      // on it, a tug's on the entry's duck, kept whole inside the screen and clear of the figures.
      const screen = $("stamp").parentElement.getBoundingClientRect();
      const floor = $("sheet").getBoundingClientRect().top - screen.top;
      const spot = viewer.spot(stampLane(run, lanes.length));
      const { x, y } = stampAt(run.event, spot, $("stamp").getBoundingClientRect(), screen, floor);
      Object.assign($("stamp").style, { left: `${100 * x}%`, top: `${100 * y}%` });
    }
    return step;
  }

  expose(plan, score, draw);
}

/** A cup's match: its bouts one after the other on the tug, a score bug over them, the winner at the outro. */
async function mainMatch() {
  const id = params.get("match");
  const match = await getMatch(id);
  // Two traces and two settles per bout, west first, and its string, bout k at k.
  const [traces, settles, strings] = await Promise.all([
    Promise.all(match.bouts.map(({ k }) => getBoutTrace(id, k))),
    Promise.all(match.bouts.map(({ k }) => getBoutSettle(id, k).then(standing))),
    Promise.all(match.bouts.map(({ k }) => getBoutString(id, k))),
  ]);
  const plan = matchPlan(
    match.bouts.map(({ k }) => ({ k, settle: frameCount(settles[k][0]), steps: frameCount(traces[k][0]) })),
  );
  const score = matchScore({ match, plan });
  const crowdDirection = stadiumDirection(score.crowd ?? {});
  const viewer = await createViewer($("stage"), { rig: match.event.rig, manual: true, camera: match.event.clip.camera });
  matchLetter(match);
  const bold = (text) => Object.assign(document.createElement("b"), { textContent: text });
  let playing = null;

  /** Frame `i` of the plan. Returns the bout's step it drew. */
  function draw(i) {
    const act = actAt(plan, i);
    const { bout, step } = boutAt(plan, i);
    if (bout !== playing) {
      viewer.setLanes([boutLane(match, bout, traces[bout], settles[bout], strings[bout])], match.event, { loop: false });
      playing = bout;
    }
    // The bout's lane starts from its settle, as a rated run's does.
    viewer.frame(step * CTRL_DT, travelAt(plan, i), i / plan.fps, crowdDirection);
    // Each bout's clock starts after its settle.
    $("osd-clock").textContent = clock(Math.max(0, step - plan.spans[bout].settle));
    document.documentElement.dataset.act = act;
    $("intro").hidden = act !== "intro";
    $("stamp").hidden = act !== "outro";
    const [a, b] = scoreAt(plan, match, i);
    $("osd-bug").hidden = act === "intro";
    $("osd-bug").replaceChildren(`${match.a.name} `, bold(`${a}–${b}`), ` ${match.b.name}`);
    return step;
  }

  expose(plan, score, draw);
}

(params.has("match") ? mainMatch() : main()).catch((jammed) => {
  $("jam").hidden = false;
  $("jam-why").textContent = jammed.message;
  window.clip = { error: jammed.message, ready: true };
  throw jammed;
});
