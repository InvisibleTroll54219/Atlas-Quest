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

async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.method === "POST") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw new Error("The game server returned an unreadable response.");
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

function renderProgress() {
  $("score").textContent = state.score.toLocaleString();
  $("levels-stat").textContent = `${state.cleared_levels.length} / ${state.levels.length}`;
  $("map-progress").textContent = `${state.cleared_levels.length} / ${state.levels.length}`;
  $("correct-stat").textContent = state.correct_answers.toLocaleString();
  $("streak-stat").textContent = state.best_streak.toLocaleString();

  const list = $("stage-list");
  list.replaceChildren();
  state.levels.forEach((level, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `stage-item${index === levelIndex ? " active" : ""}`;
    button.disabled = index > state.unlocked_level;
    button.setAttribute("aria-label", `Level ${index + 1}: ${level.name}${button.disabled ? ", locked" : ""}`);

    const icon = document.createElement("span");
    icon.className = "stage-small-icon";
    icon.textContent = level.icon;
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = level.name;
    const subtitle = document.createElement("small");
    subtitle.textContent = level.region;
    text.append(title, subtitle);
    const status = document.createElement("span");
    status.className = "stage-status";
    status.textContent = state.cleared_levels.includes(index) ? "✓" : button.disabled ? "🔒" : "›";
    button.append(icon, text, status);
    button.addEventListener("click", () => startRound(index));
    list.append(button);
  });
}

async function startRound(index) {
  levelIndex = index;
  round = null;
  try {
    round = await api(`/api/round/?level=${encodeURIComponent(index)}`);
    questionIndex = 0;
    hintUsed = false;
    roundResult = null;
    renderLevel();
    renderQuestion();
    renderProgress();
  } catch (error) {
    showError(error);
  }
}

function renderLevel() {
  const level = round.level_info;
  $("stage-name").textContent = level.name;
  $("stage-subtitle").textContent = level.region;
  $("stage-emoji").textContent = level.icon;
  $("level-tag").textContent = `LEVEL ${levelIndex + 1}`;
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
  showFeedback("Choose your answer. You need 4 correct answers out of 5 to clear this level.");
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
  try {
    const result = await api("/api/answer/", {
      method: "POST",
      body: JSON.stringify({ question_id: question.id, selected_index: index }),
    });
    const buttons = [...$("answers").children];
    buttons[result.correct_index].classList.add("correct");
    if (!result.correct) buttons[index].classList.add("incorrect");
    state.score = result.score;
    state.correct_answers += result.correct ? 1 : 0;
    state.best_streak = result.best_streak;
    state.current_streak = result.current_streak;
    if (result.round_complete) {
      roundResult = result;
      state.cleared_levels = result.cleared_levels;
      state.unlocked_level = result.unlocked_level;
    }
    renderProgress();
    showFeedback(result.explanation, result.correct ? "good" : "bad");
    $("next-button").disabled = false;
    $("progress-fill").style.width = `${((questionIndex + 1) / QUESTIONS_PER_LEVEL) * 100}%`;
    document.querySelector('[role="progressbar"]').setAttribute("aria-valuenow", String(questionIndex + 1));
  } catch (error) {
    answered = false;
    [...$("answers").children].forEach((button) => {
      button.disabled = false;
    });
    showError(error);
  }
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
    showDialog("🏆", "Atlas master!", `You cleared all 8 destinations with ${result.correct_in_round} out of 5 correct this round. Your world knowledge is officially top-tier.`, "Play again", () => startRound(levelIndex));
  } else if (result.cleared) {
    const nextLevel = Math.min(levelIndex + 1, state.levels.length - 1);
    const detail = result.newly_cleared ? "A new destination is unlocked!" : "This destination stays cleared.";
    showDialog("🎉", result.newly_cleared ? "Destination cleared!" : "Round complete!", `${result.correct_in_round} out of 5 correct. ${detail}`, nextLevel > levelIndex ? "Next destination →" : "Play again", () => startRound(nextLevel));
  } else {
    showDialog("🧭", "One more try?", `You got ${result.correct_in_round} out of 5. You need ${GOAL} to clear this destination. Take what you learned and give it another shot!`, "Try this level again", () => startRound(levelIndex));
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

$("next-button").addEventListener("click", nextQuestion);
$("hint-button").addEventListener("click", useHint);
$("reset-button").addEventListener("click", async () => {
  if (!window.confirm("Reset all saved Atlas Quest progress and start over?")) return;
  try {
    state = await api("/api/reset/", { method: "POST", body: "{}" });
    levelIndex = 0;
    renderProgress();
    await startRound(0);
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
    levelIndex = state.unlocked_level;
    renderProgress();
    await startRound(levelIndex);
  } catch (error) {
    showError(error);
  }
}

boot();
