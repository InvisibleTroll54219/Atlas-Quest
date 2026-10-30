"use strict";

const QUESTIONS_PER_LEVEL = 5;
const GOAL = 4;
const $ = (id) => document.getElementById(id);
let state;
let levelIndex = 0;
let round;
let questionIndex = 0;
let hintUsed = false;
let answered = false;
let roundResult = null;
let globeRotation = 0;
let globeTilt = 0;
let globeMarkers = [];
let globePointer = null;
let globeLand = null;
let globeBorders = null;
let globeLakes = null;

const GLOBE_CENTER = 300;
const GLOBE_RADIUS = 238;
const CONTINENT_LOCATIONS = {
  Africa: [2, 20],
  Asia: [31, 100],
  Europe: [50, 15],
  "North America": [42, -102],
  "South America": [-16, -60],
  Oceania: [-25, 135],
  Antarctica: [-78, 0],
  World: [0, -165],
};
const globeCanvas = $("globe-canvas");
const globeContext = globeCanvas.getContext("2d");

async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.method === "POST") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  const responseBody = await response.text();
  let data;
  try {
    data = JSON.parse(responseBody);
  } catch (error) {
    const detail = responseBody
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 220);
    const status = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ""}`;
    throw new Error(detail
      ? `The game server returned ${status} instead of JSON: ${detail}`
      : `The game server returned ${status} instead of JSON.`);
  }
  if (!response.ok) throw new Error(data.error || `The server returned ${response.status}.`);
  return data;
}

function getCookie(name) {
  const cookie = document.cookie.split("; ").find((entry) => entry.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
}

function showError(error) {
  const feedback = $("feedback");
  feedback.className = "feedback bad";
  feedback.textContent = error.message || "Something went wrong. Please try again.";
}

function showFeedback(message, kind = "") {
  const feedback = $("feedback");
  feedback.className = `feedback${kind ? ` ${kind}` : ""}`;
  feedback.replaceChildren();
  if (kind === "good" || kind === "bad") {
    const strong = document.createElement("strong");
    strong.textContent = kind === "good" ? "Correct! " : "Not quite. ";
    feedback.append(strong, document.createTextNode(message));
  } else {
    feedback.textContent = message;
  }
}

function globeVector(latitude, longitude) {
  const latitudeRadians = (latitude * Math.PI) / 180;
  const longitudeRadians = ((longitude + globeRotation) * Math.PI) / 180;
  const tiltRadians = (globeTilt * Math.PI) / 180;
  const x = Math.cos(latitudeRadians) * Math.sin(longitudeRadians);
  const y = Math.sin(latitudeRadians);
  const z = Math.cos(latitudeRadians) * Math.cos(longitudeRadians);
  return {
    x,
    y: y * Math.cos(tiltRadians) - z * Math.sin(tiltRadians),
    z: y * Math.sin(tiltRadians) + z * Math.cos(tiltRadians),
  };
}

function projectGlobePoint(latitude, longitude) {
  const vector = globeVector(latitude, longitude);
  return {
    x: GLOBE_CENTER + GLOBE_RADIUS * vector.x,
    y: GLOBE_CENTER - GLOBE_RADIUS * vector.y,
    depth: vector.z,
  };
}

function drawGlobeGrid() {
  const context = globeContext;
  context.save();
  context.beginPath();
  context.arc(GLOBE_CENTER, GLOBE_CENTER, GLOBE_RADIUS, 0, Math.PI * 2);
  context.clip();

  const drawLine = (points) => {
    context.beginPath();
    let drawing = false;
    points.forEach(([latitude, longitude]) => {
      const point = projectGlobePoint(latitude, longitude);
      if (point.depth > 0) {
        if (!drawing) context.moveTo(point.x, point.y);
        else context.lineTo(point.x, point.y);
        drawing = true;
      } else {
        drawing = false;
      }
    });
    context.stroke();
  };

  context.lineWidth = 1;
  context.strokeStyle = "rgba(255,255,255,.16)";
  for (let latitude = -75; latitude <= 75; latitude += 15) {
    context.beginPath();
    const points = [];
    for (let longitude = -180; longitude <= 180; longitude += 2) {
      points.push([latitude, longitude]);
    }
    context.strokeStyle = latitude === 0
      ? "rgba(255,255,255,.58)"
      : Math.abs(latitude) === 60
        ? "rgba(229,236,195,.38)"
        : "rgba(255,255,255,.16)";
    context.lineWidth = latitude === 0 ? 1.6 : 1;
    drawLine(points);
  }
  for (let longitude = -180; longitude < 180; longitude += 15) {
    const points = [];
    for (let latitude = -89; latitude <= 89; latitude += 2) {
      points.push([latitude, longitude]);
    }
    context.strokeStyle = longitude === 0 ? "rgba(255,255,255,.54)" : "rgba(255,255,255,.13)";
    context.lineWidth = longitude === 0 ? 1.5 : 1;
    drawLine(points);
  }
  context.restore();
}

function traceVisibleLandRing(ring) {
  const vertices = ring.map(([longitude, latitude]) => globeVector(latitude, longitude));
  const clipped = [];
  vertices.forEach((current, index) => {
    const previous = vertices[(index + vertices.length - 1) % vertices.length];
    const currentVisible = current.z >= 0;
    const previousVisible = previous.z >= 0;
    if (currentVisible !== previousVisible) {
      const fraction = previous.z / (previous.z - current.z);
      const intersection = {
        x: previous.x + (current.x - previous.x) * fraction,
        y: previous.y + (current.y - previous.y) * fraction,
        z: 0,
      };
      const length = Math.hypot(intersection.x, intersection.y);
      clipped.push({ x: intersection.x / length, y: intersection.y / length, z: 0 });
    }
    if (currentVisible) clipped.push(current);
  });
  if (clipped.length < 3) return;

  clipped.forEach((point, index) => {
    const x = GLOBE_CENTER + GLOBE_RADIUS * point.x;
    const y = GLOBE_CENTER - GLOBE_RADIUS * point.y;
    if (index === 0) globeContext.moveTo(x, y);
    else globeContext.lineTo(x, y);
  });
  globeContext.closePath();
}

function horizonIntersection(previous, current) {
  const fraction = previous.z / (previous.z - current.z);
  const x = previous.x + (current.x - previous.x) * fraction;
  const y = previous.y + (current.y - previous.y) * fraction;
  const length = Math.hypot(x, y);
  return { x: x / length, y: y / length, z: 0 };
}

function traceGlobeBorder(line) {
  const context = globeContext;
  context.beginPath();
  let previous = null;
  let drawing = false;
  line.forEach(([longitude, latitude]) => {
    const current = globeVector(latitude, longitude);
    const currentVisible = current.z >= 0;
    if (previous) {
      const previousVisible = previous.z >= 0;
      if (currentVisible && previousVisible) {
        context.lineTo(
          GLOBE_CENTER + GLOBE_RADIUS * current.x,
          GLOBE_CENTER - GLOBE_RADIUS * current.y,
        );
      } else if (currentVisible) {
        const crossing = horizonIntersection(previous, current);
        context.moveTo(
          GLOBE_CENTER + GLOBE_RADIUS * crossing.x,
          GLOBE_CENTER - GLOBE_RADIUS * crossing.y,
        );
        context.lineTo(
          GLOBE_CENTER + GLOBE_RADIUS * current.x,
          GLOBE_CENTER - GLOBE_RADIUS * current.y,
        );
      } else if (previousVisible) {
        const crossing = horizonIntersection(previous, current);
        context.lineTo(
          GLOBE_CENTER + GLOBE_RADIUS * crossing.x,
          GLOBE_CENTER - GLOBE_RADIUS * crossing.y,
        );
      }
      if (previousVisible && !currentVisible) {
        context.stroke();
        context.beginPath();
        drawing = false;
      } else if (currentVisible) {
        drawing = true;
      }
    } else if (currentVisible) {
      context.moveTo(
        GLOBE_CENTER + GLOBE_RADIUS * current.x,
        GLOBE_CENTER - GLOBE_RADIUS * current.y,
      );
      drawing = true;
    }
    previous = current;
  });
  if (drawing) context.stroke();
}

function drawLandPolygon(rings) {
  globeContext.beginPath();
  rings.forEach(traceVisibleLandRing);
  globeContext.fill("evenodd");
  globeContext.stroke();
}

async function loadGlobeGeography() {
  const [landResponse, borderResponse, lakeResponse] = await Promise.all([
    fetch("/static/world-land.json", { credentials: "same-origin" }),
    fetch("/static/world-borders.json", { credentials: "same-origin" }),
    fetch("/static/world-lakes.json", { credentials: "same-origin" }),
  ]);
  if (!landResponse.ok) {
    throw new Error(`The coastline map could not be loaded (HTTP ${landResponse.status}).`);
  }
  if (!borderResponse.ok) {
    throw new Error(`Country borders could not be loaded (HTTP ${borderResponse.status}).`);
  }
  if (!lakeResponse.ok) {
    throw new Error(`The lake map could not be loaded (HTTP ${lakeResponse.status}).`);
  }
  const [landData, borderData, lakeData] = await Promise.all([
    landResponse.json(),
    borderResponse.json(),
    lakeResponse.json(),
  ]);
  if (landData.type !== "MultiPolygon" || !Array.isArray(landData.coordinates)) {
    throw new Error("The coastline map data is not in the expected format.");
  }
  if (!Array.isArray(borderData.features)) {
    throw new Error("The country border data is not in the expected format.");
  }
  if (lakeData.type !== "MultiPolygon" || !Array.isArray(lakeData.coordinates)) {
    throw new Error("The lake map data is not in the expected format.");
  }
  globeLand = landData;
  globeBorders = borderData;
  globeLakes = lakeData;
}

function drawGlobe() {
  if (!globeContext || !state) return;
  const context = globeContext;
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  if (globeCanvas.width !== 600 * pixelRatio) {
    globeCanvas.width = 600 * pixelRatio;
    globeCanvas.height = 600 * pixelRatio;
  }
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, 600, 600);
  context.save();
  context.shadowColor = "rgba(31, 86, 70, .22)";
  context.shadowBlur = 32;
  context.shadowOffsetY = 14;
  const ocean = context.createRadialGradient(220, 190, 20, 300, 300, GLOBE_RADIUS);
  ocean.addColorStop(0, "#75c4c2");
  ocean.addColorStop(.68, "#398f99");
  ocean.addColorStop(1, "#246d7b");
  context.fillStyle = ocean;
  context.beginPath();
  context.arc(GLOBE_CENTER, GLOBE_CENTER, GLOBE_RADIUS, 0, Math.PI * 2);
  context.fill();
  context.restore();

  drawGlobeGrid();
  context.save();
  context.beginPath();
  context.arc(GLOBE_CENTER, GLOBE_CENTER, GLOBE_RADIUS, 0, Math.PI * 2);
  context.clip();
  if (globeLand) {
    context.fillStyle = "#b8d2a1";
    context.strokeStyle = "rgba(54, 95, 72, .55)";
    context.lineWidth = .85;
    context.lineJoin = "round";
    globeLand.coordinates.forEach(drawLandPolygon);
  }
  if (globeLakes) {
    context.fillStyle = "rgba(52, 142, 163, .88)";
    context.strokeStyle = "rgba(37, 113, 134, .7)";
    context.lineWidth = .7;
    globeLakes.coordinates.forEach(drawLandPolygon);
  }
  context.restore();
  if (globeBorders) {
    context.save();
    context.beginPath();
    context.arc(GLOBE_CENTER, GLOBE_CENTER, GLOBE_RADIUS, 0, Math.PI * 2);
    context.clip();
    context.lineWidth = .75;
    context.lineCap = "round";
    globeBorders.features.forEach((feature) => {
      context.strokeStyle = feature.disputed
        ? "rgba(146, 104, 76, .7)"
        : "rgba(69, 102, 78, .55)";
      context.setLineDash(feature.disputed ? [2, 2] : []);
      const lines = feature.type === "LineString"
        ? [feature.coordinates]
        : feature.coordinates;
      lines.forEach(traceGlobeBorder);
    });
    context.setLineDash([]);
    context.restore();
  }

  globeMarkers = [];
  state.levels.forEach((level, index) => {
    const location = CONTINENT_LOCATIONS[level.continent];
    if (!location || (index === 7 && state.unlocked_level < 7)) return;
    const point = projectGlobePoint(location[0], location[1]);
    if (point.depth < .08) return;
    const unlocked = index <= state.unlocked_level;
    const cleared = state.cleared_levels.includes(index);
    const bestScore = state.level_best_scores[String(index)];
    const perfect = bestScore === QUESTIONS_PER_LEVEL;
    const attempted = Number.isInteger(bestScore) && bestScore < GOAL;
    globeMarkers.push({ x: point.x, y: point.y, level: index });
    context.beginPath();
    context.arc(point.x, point.y, 18, 0, Math.PI * 2);
    context.fillStyle = perfect ? "#1d5949" : cleared ? "#e9ba55" : attempted ? "#efb18f" : unlocked ? "#fffefa" : "rgba(255,254,250,.76)";
    context.fill();
    context.lineWidth = 3;
    context.strokeStyle = perfect ? "#dceee4" : cleared ? "#fff0bc" : attempted ? "#ffe1ca" : unlocked ? "#26745e" : "rgba(89,111,102,.45)";
    context.stroke();
    context.font = "16px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = perfect ? "#ffffff" : "#172d3b";
    context.fillText(perfect ? "★" : cleared ? "4" : attempted ? String(bestScore) : unlocked ? level.icon : "🔒", point.x, point.y + 1);
  });
  context.beginPath();
  context.arc(GLOBE_CENTER, GLOBE_CENTER, GLOBE_RADIUS, 0, Math.PI * 2);
  context.strokeStyle = "rgba(255,255,255,.72)";
  context.lineWidth = 2;
  context.stroke();
}

function renderProgress() {
  $("score").textContent = state.score.toLocaleString();
  const clearedContinents = state.cleared_levels.filter((index) => index < 7).length;
  $("levels-stat").textContent = `${clearedContinents} / 7`;
  $("map-progress").textContent = `${clearedContinents} / 7 continents`;
  $("correct-stat").textContent = state.correct_answers.toLocaleString();
  $("streak-stat").textContent = state.best_streak.toLocaleString();

  const list = $("region-list");
  list.replaceChildren();
  state.levels.forEach((level, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = index > state.unlocked_level;
    const destination = index === 7 ? "World Challenge" : level.continent;
    const bestScore = state.level_best_scores[String(index)];
    const cleared = state.cleared_levels.includes(index);
    const perfect = bestScore === QUESTIONS_PER_LEVEL;
    const attempted = Number.isInteger(bestScore) && bestScore < GOAL;
    button.className = `region-button${perfect ? " perfect" : cleared ? " cleared" : attempted ? " attempted" : ""}`;
    const progressLabel = button.disabled
      ? "Locked"
      : perfect
        ? "Perfect · 5/5"
        : cleared
          ? bestScore === GOAL
            ? "Passed · 4/5 · replay for 5/5"
            : "Previously cleared · replay for 5/5"
          : attempted
            ? `Best: ${bestScore}/5 · try again`
            : "Quiz ready";
    button.setAttribute("aria-label", `${destination} quiz, ${progressLabel}`);
    const icon = document.createElement("span");
    icon.className = "region-icon";
    icon.textContent = level.icon;
    const text = document.createElement("span");
    text.className = "region-copy";
    const title = document.createElement("strong");
    title.textContent = destination;
    const subtitle = document.createElement("small");
    subtitle.textContent = progressLabel;
    text.append(title, subtitle);
    const status = document.createElement("span");
    status.className = "region-status";
    status.textContent = button.disabled ? "🔒" : perfect ? "★" : cleared ? bestScore === GOAL ? "4/5" : "✓" : attempted ? `${bestScore}/5` : "›";
    button.append(icon, text, status);
    button.addEventListener("click", () => startRound(index));
    list.append(button);
  });
  const mapNote = $("map-note");
  if (state.cleared_levels.length === state.levels.length) {
    mapNote.textContent = "World Challenge complete! You have mastered every continent.";
    $("globe-caption").textContent = "All quizzes cleared. Spin the globe and revisit any destination.";
  } else if (state.unlocked_level === 7) {
    mapNote.textContent = "All seven continents are cleared. The World Challenge is open!";
    $("globe-caption").textContent = "The World Challenge is open. Select its pin to play!";
  } else {
    const nextRegion = state.levels[state.unlocked_level].continent;
    mapNote.textContent = `Clear ${nextRegion} to unlock the next continent. Finish all seven to open the World Challenge.`;
    $("globe-caption").textContent = `Unlocked: ${nextRegion}. Drag the globe or tap an unlocked pin.`;
  }
  const perfectLevels = Object.values(state.level_best_scores).filter(
    (bestScore) => bestScore === QUESTIONS_PER_LEVEL,
  ).length;
  $("map-note").textContent += ` ${perfectLevels} destination${perfectLevels === 1 ? "" : "s"} mastered perfectly. Revisit amber quizzes to earn 5/5.`;
  drawGlobe();
}

async function startRound(index) {
  levelIndex = index;
  round = null;
  try {
    round = await api(`/api/round/?level=${encodeURIComponent(index)}`);
    questionIndex = 0;
    hintUsed = false;
    roundResult = null;
    $("world-screen").classList.add("hidden");
    $("quiz-screen").classList.remove("hidden");
    renderLevel();
    renderQuestion();
    renderProgress();
  } catch (error) {
    if (!$("world-screen").classList.contains("hidden")) {
      $("globe-caption").textContent = error.message || "Could not open that quiz. Please try again.";
    } else {
      showError(error);
    }
  }
}

function renderLevel() {
  const level = round.level_info;
  $("stage-name").textContent = level.name;
  $("stage-subtitle").textContent = level.region;
  $("stage-emoji").textContent = level.icon;
  $("level-tag").textContent = levelIndex === 7 ? "WORLD CHALLENGE" : `CONTINENT ${levelIndex + 1} / 7`;
  $("goal-count").textContent = `Goal: ${GOAL} correct`;
}

function renderQuestion() {
  answered = false;
  const question = round.questions[questionIndex];
  $("question-count").textContent = `Question ${questionIndex + 1} of ${QUESTIONS_PER_LEVEL}`;
  $("progress-fill").style.width = `${(questionIndex / QUESTIONS_PER_LEVEL) * 100}%`;
  document.querySelector('[role="progressbar"]').setAttribute("aria-valuenow", String(questionIndex));
  $("question-category").textContent = round.level_info.region;
  $("question-text").textContent = question.prompt;
  showFeedback(`Choose your answer. You need ${GOAL} correct answers out of ${QUESTIONS_PER_LEVEL} to clear this quiz.`);
  $("next-button").disabled = true;
  $("next-button").textContent = questionIndex === QUESTIONS_PER_LEVEL - 1 ? "See my results →" : "Lock it in →";
  $("hint-button").disabled = hintUsed;
  $("hint-status").textContent = hintUsed ? "(used)" : "";

  const answers = $("answers");
  answers.replaceChildren();
  question.options.forEach((label, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "answer";
    const letter = document.createElement("span");
    letter.className = "answer-letter";
    letter.textContent = String.fromCharCode(65 + index);
    const text = document.createElement("span");
    text.className = "answer-label";
    text.textContent = label;
    button.append(letter, text);
    button.addEventListener("click", () => selectAnswer(index));
    answers.append(button);
  });
}

async function selectAnswer(index) {
  if (answered) return;
  answered = true;
  const question = round.questions[questionIndex];
  [...$("answers").children].forEach((button) => {
    button.disabled = true;
  });
  let result;
  try {
    result = await api("/api/answer/", {
      method: "POST",
      body: JSON.stringify({ question_id: question.id, selected_index: index }),
    });
  } catch (error) {
    answered = false;
    [...$("answers").children].forEach((button) => {
      button.disabled = false;
    });
    showError(error);
    return;
  }

  const buttons = [...$("answers").children];
  result.correct_indices.forEach((correctIndex) => {
    buttons[correctIndex].classList.add("correct");
  });
  if (!result.correct) buttons[index].classList.add("incorrect");
  state.score = result.score;
  state.correct_answers += result.correct ? 1 : 0;
  state.best_streak = result.best_streak;
  state.current_streak = result.current_streak;
  if (result.round_complete) {
    roundResult = result;
    state.cleared_levels = result.cleared_levels;
    state.level_best_scores = result.level_best_scores;
    state.unlocked_level = result.unlocked_level;
  }
  renderProgress();
  showFeedback(result.explanation, result.correct ? "good" : "bad");
  $("next-button").disabled = false;
  $("progress-fill").style.width = `${((questionIndex + 1) / QUESTIONS_PER_LEVEL) * 100}%`;
  document.querySelector('[role="progressbar"]').setAttribute("aria-valuenow", String(questionIndex + 1));
}

async function nextQuestion() {
  if (!answered) return;
  if (questionIndex < QUESTIONS_PER_LEVEL - 1) {
    questionIndex++;
    renderQuestion();
    return;
  }
  if (!roundResult) {
    showError(new Error("The round result is missing. Start a new round to continue."));
    return;
  }
  showRoundResult(roundResult);
}

function showRoundResult(result) {
  if (result.all_cleared) {
    showDialog("🏆", "Atlas master!", `You cleared the World Challenge with ${result.correct_in_round} out of 5 correct. Every continent is yours to explore!`, "Back to the globe", showWorldScreen);
  } else if (result.cleared) {
    const unlockedWorld = result.newly_cleared && result.unlocked_level === 7;
    const nextContinent = state.levels[Math.min(levelIndex + 1, 6)].continent;
    const perfect = result.correct_in_round === QUESTIONS_PER_LEVEL;
    const detail = perfect
      ? "Perfect score! This destination is now marked green on your globe."
      : unlockedWorld
        ? "All seven continents are clear. The World Challenge is now open on your globe. Replay this destination for a perfect 5/5!"
        : result.newly_cleared
          ? `${nextContinent} is now unlocked. Replay this destination any time to turn its amber marker green with 5/5.`
          : "This destination stays cleared in amber. Replay it for a perfect 5/5 and a green marker.";
    const title = perfect
      ? result.new_best_score ? "Perfect score!" : "Perfect again!"
      : result.newly_cleared ? "Destination cleared!" : "Quiz complete!";
    showDialog(perfect ? "🌟" : "🎉", title, `${result.correct_in_round} out of 5 correct. ${detail}`, "Back to the globe", showWorldScreen);
  } else {
    showDialog("🧭", "Keep exploring!", `You got ${result.correct_in_round} out of 5. You need ${GOAL} to clear this quiz. Your best attempt is saved, and you can retry it from the globe.`, "Back to the globe", showWorldScreen);
  }
}

function showDialog(icon, title, copy, buttonText, action) {
  $("dialog-emoji").textContent = icon;
  $("dialog-title").textContent = title;
  $("dialog-copy").textContent = copy;
  $("dialog-button").textContent = buttonText;
  $("overlay").classList.remove("hidden");
  $("dialog-button").onclick = () => {
    $("overlay").classList.add("hidden");
    action();
  };
  $("dialog-button").focus();
}

function useHint() {
  if (hintUsed || answered || !round) return;
  hintUsed = true;
  $("hint-button").disabled = true;
  $("hint-status").textContent = "(used)";
  const incorrectIndexes = round.questions[questionIndex].options.map((_, index) => index);
  for (let i = incorrectIndexes.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [incorrectIndexes[i], incorrectIndexes[j]] = [incorrectIndexes[j], incorrectIndexes[i]];
  }
  incorrectIndexes.slice(0, 2).forEach((index) => $("answers").children[index].classList.add("eliminated"));
  showFeedback("Hint used — two choices are out. Pick from the remaining answers.");
}

function showWorldScreen() {
  $("welcome-screen").classList.add("hidden");
  $("quiz-screen").classList.add("hidden");
  $("world-screen").classList.remove("hidden");
  $("journey-hero").classList.remove("hidden");
  $("journey-stats").classList.remove("hidden");
  renderProgress();
}

function showWelcomeScreen() {
  $("welcome-screen").classList.remove("hidden");
  $("world-screen").classList.add("hidden");
  $("quiz-screen").classList.add("hidden");
  $("journey-hero").classList.add("hidden");
  $("journey-stats").classList.add("hidden");
}

function canvasPosition(event) {
  const bounds = globeCanvas.getBoundingClientRect();
  return {
    x: ((event.clientX - bounds.left) / bounds.width) * 600,
    y: ((event.clientY - bounds.top) / bounds.height) * 600,
  };
}

globeCanvas.addEventListener("pointerdown", (event) => {
  globePointer = { ...canvasPosition(event), lastX: event.clientX, lastY: event.clientY, moved: false, pointerId: event.pointerId };
  globeCanvas.setPointerCapture(event.pointerId);
});
globeCanvas.addEventListener("pointermove", (event) => {
  if (!globePointer || globePointer.pointerId !== event.pointerId) return;
  const deltaX = event.clientX - globePointer.lastX;
  const deltaY = event.clientY - globePointer.lastY;
  if (Math.abs(event.clientX - globePointer.lastX) + Math.abs(event.clientY - globePointer.lastY) > 2) {
    globePointer.moved = true;
  }
  if (!globePointer.moved) return;
  globeRotation += deltaX * .55;
  globeTilt = Math.max(-55, Math.min(55, globeTilt + deltaY * .35));
  globePointer.lastX = event.clientX;
  globePointer.lastY = event.clientY;
  globeCanvas.classList.add("is-dragging");
  drawGlobe();
});
globeCanvas.addEventListener("pointerup", (event) => {
  if (!globePointer || globePointer.pointerId !== event.pointerId) return;
  const pointer = globePointer;
  globePointer = null;
  globeCanvas.classList.remove("is-dragging");
  if (pointer.moved) return;
  const point = canvasPosition(event);
  const marker = globeMarkers.find((candidate) => Math.hypot(candidate.x - point.x, candidate.y - point.y) <= 27);
  if (!marker) return;
  if (marker.level > state.unlocked_level) {
    const region = marker.level === 7 ? "the World Challenge" : state.levels[marker.level].continent;
    $("globe-caption").textContent = `${region} is locked. Clear the previous continent quiz to unlock it.`;
    return;
  }
  startRound(marker.level);
});
globeCanvas.addEventListener("pointercancel", () => {
  globePointer = null;
  globeCanvas.classList.remove("is-dragging");
});
globeCanvas.addEventListener("keydown", (event) => {
  const directions = { ArrowLeft: [-15, 0], ArrowRight: [15, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] };
  const direction = directions[event.key];
  if (!direction) return;
  event.preventDefault();
  globeRotation += direction[0];
  globeTilt = Math.max(-55, Math.min(55, globeTilt + direction[1]));
  drawGlobe();
});

$("next-button").addEventListener("click", nextQuestion);
$("hint-button").addEventListener("click", useHint);
$("globe-return").addEventListener("click", showWorldScreen);
$("begin-journey").addEventListener("click", showWorldScreen);
$("reset-button").addEventListener("click", async () => {
  if (!window.confirm("Reset all saved Atlas Quest progress and start over?")) return;
  try {
    state = await api("/api/reset/", { method: "POST", body: "{}" });
    levelIndex = 0;
    renderProgress();
    showWorldScreen();
  } catch (error) {
    showError(error);
  }
});
$("help-button").addEventListener("click", () => $("help-overlay").classList.remove("hidden"));
$("close-help").addEventListener("click", () => $("help-overlay").classList.add("hidden"));
$("help-ok").addEventListener("click", () => $("help-overlay").classList.add("hidden"));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    $("help-overlay").classList.add("hidden");
    $("overlay").classList.add("hidden");
  }
});

async function boot() {
  try {
    state = await api("/api/progress/");
    await loadGlobeGeography();
    levelIndex = state.unlocked_level;
    renderProgress();
    showWelcomeScreen();
  } catch (error) {
    const message = $("welcome-error");
    message.textContent = error.message || "The game could not be loaded. Please refresh to try again.";
    message.classList.remove("hidden");
  }
}

boot();
