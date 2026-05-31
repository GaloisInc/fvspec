// scrape-dependents.js
import fs from 'fs';
import path from 'path';
import { Window } from 'happy-dom';

const OWNER = 'dubzzz';
const REPO = 'fast-check';
const BASE_URL = `https://github.com/${OWNER}/${REPO}/network/dependents`;

// File to store scraped dependents
const DATA_FILE = path.resolve('./dependents-ts.json');

// Load progress if exists
let dependents = [];
let visitedPages = new Set();
let nextCursor = null;

if (fs.existsSync(DATA_FILE)) {
    const saved = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    dependents = saved.dependents || [];
    visitedPages = new Set(saved.visitedPages || []);
    nextCursor = saved.nextCursor || null;
}

// Save function (resumable)
function saveProgress() {
    fs.writeFileSync(
        DATA_FILE,
        JSON.stringify({ dependents, visitedPages: [...visitedPages], nextCursor }, null, 2)
    );
    console.log(`Progress saved: ${dependents.length} dependents`);
}

async function fetchPage(url) {
    console.log(`Fetching: ${url}`);
    const res = await fetch(url, {
        headers: {
            'User-Agent': 'Mozilla/5.0',
        },
    });
    if (!res.ok) {
        throw new Error(`HTTP ${res.status} on ${url}`);
    }
    return await res.text();
}

function parseDependents(html) {
    const window = new Window();
    const document = window.document;
    document.body.innerHTML = html;

    const items = [];
    const rows = document.querySelectorAll('div.Box-row');

    rows.forEach(row => {
        const repoLink = row.querySelector('a[href^="/"][data-hovercard-type="repository"]');
        if (repoLink) {
            const fullName = repoLink.getAttribute('href').slice(1); // "owner/name"
            items.push(fullName);
        }
    });

    const nextLink = Array.from(document.querySelectorAll('a.btn')).find(link => link.textContent.trim() === 'Next');
    let nextCursor = null;
    if (nextLink && !nextLink.classList.contains('disabled')) {
        const href = nextLink.getAttribute('href');
        const match = href.match(/after=(.+)/);
        if (match) {
            nextCursor = match[1];
        }
    }

    return { items, nextCursor };
}

async function scrapeDependents() {
    let url = BASE_URL;
    if (nextCursor) {
        url += `?dependents_after=${nextCursor}`;
    }

    while (url) {
        if (visitedPages.has(url)) {
            console.log(`Skipping already visited: ${url}`);
            url = nextCursor ? `${BASE_URL}?dependents_after=${nextCursor}` : null;
            continue;
        }

        try {
            const html = await fetchPage(url);
            const { items, nextCursor: newCursor } = parseDependents(html);

            dependents.push(...items);
            visitedPages.add(url);
            nextCursor = newCursor;

            saveProgress();

            if (nextCursor) {
                url = `${BASE_URL}?dependents_after=${nextCursor}`;
            } else {
                url = null; // done
            }

            await new Promise(res => setTimeout(res, 1500)); // polite delay
        } catch (err) {
            console.error(`Error: ${err.message}`);
            saveProgress();
            break;
        }
    }
}

scrapeDependents();
