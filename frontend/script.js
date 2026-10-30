
const API_URL = "http://127.0.0.1:8000/api/search/";

const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const limitInput = document.getElementById("limit");
const searchButton = document.getElementById("search-button");
const message = document.getElementById("message");
const resultsContainer = document.getElementById("results");
const resultCount = document.getElementById("result-count");

function showMessage(text) {
    message.textContent = text;
    message.hidden = false;
}

function getFirstValue(object, keys) {
    for (const key of keys) {
        if (object && object[key] !== undefined && object[key] !== null) {
            return object[key];
        }
    }
    return "";
}


function displayResults(data) {
    resultsContainer.replaceChildren();

    // Display the AI-generated answer first.
    if (data.answer) {
        const answerCard = document.createElement("article");
        answerCard.className = "result-card";

        const heading = document.createElement("h3");
        heading.textContent = "AI-generated answer";

        const answerText = document.createElement("p");
        answerText.textContent = data.answer;

        answerCard.append(heading, answerText);
        resultsContainer.append(answerCard);
    }

    // Use the actual results array returned by Django.
    const items = Array.isArray(data.results) ? data.results : [];

    resultCount.textContent =
        `${data.count ?? items.length} result(s) · ${data.method ?? "Search"}`;

    if (items.length === 0) {
        showMessage(
            data.answer
                ? "No individual event records were returned."
                : "No matching cricket events found."
        );
        return;
    }

    message.hidden = true;

    for (const item of items) {
        const card = document.createElement("article");
        card.className = "result-card";

        const top = document.createElement("div");
        top.className = "result-top";

        const tag = document.createElement("span");
        tag.className = "event-tag";
        tag.textContent = String(item.event || "MATCH EVENT");

        const meta = document.createElement("span");
        meta.className = "result-meta";
        meta.textContent = [
            item.match_id,
            item.team,
            item.over !== undefined ? `Over ${item.over}` : ""
        ].filter(Boolean).join(" · ");

        top.append(tag, meta);

        const commentary = document.createElement("p");
        commentary.textContent = item.commentary || "No commentary available.";

        const details = document.createElement("p");
        details.className = "result-meta";
        details.style.marginTop = "12px";
        details.textContent = [
            item.player ? `Player: ${item.player}` : "",
            item.runs !== undefined ? `Runs: ${item.runs}` : "",
            item.status ? `Status: ${item.status}` : "",
            item.score !== undefined ? `Relevance: ${(Number(item.score) * 100).toFixed(1)}%` : ""
        ].filter(Boolean).join(" · ");

        card.append(top, commentary, details);
        resultsContainer.append(card);
    }
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const query = queryInput.value.trim();

    if (!query) {
        showMessage("Please enter a search question.");
        return;
    }

    searchButton.disabled = true;
    searchButton.textContent = "Searching...";
    resultCount.textContent = "Searching";
    resultsContainer.replaceChildren();
    showMessage("Searching your cricket logs...");

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query,
                limit: Number(limitInput.value)
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || data.error || `HTTP error ${response.status}`
            );
        }

        displayResults(data);
    } catch (error) {
        console.error("Cricket search failed:", error);
        resultCount.textContent = "Search failed";

        showMessage(
            `Could not complete the search: ${error.message}. ` +
            "Check that Django is running and that the API permits requests from this page."
        );
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = "Search →";
    }
});

document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
        queryInput.value = button.textContent.trim();
        queryInput.focus();
    });
});
