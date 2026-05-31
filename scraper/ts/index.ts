import { exec } from "child_process";
import postgres from "postgres";
import { loadFile } from "./loadFile";
import { hasLegalLicense } from "./license";
import path from "path";

const DRY = process.env.DRY === "true" || process.env.DRY === "1";

const SEARCH_STRINGS = [
	"from fast-check language:TypeScript",
	"from fast-check language:JavaScript",
];

let sql = DRY
	? postgres({
		host: "127.0.0.1",
		port: 5433,
		username: "postgres",
		password: "postgres",
		database: "postgres",
		max: 1,
		connect_timeout: 0,
		debug: false,
	})
	: postgres(process.env.CONNECTION_STRING);

async function callGh(searchUrl: string) {
	let maxPage: number | null = 1;
	const res = await fetch(searchUrl, {
		headers: {
			Authorization: `token ${process.env.TOKEN}`,
		},
	});
	// parse `link` header for last page
	const linkHeader = res.headers.get("link");
	if (linkHeader) {
		const links = linkHeader.split(", ");
		for (const link of links) {
			if (link.includes('rel="last"')) {
				const lastPage = link.match(/page=(\d+)/);
				if (lastPage) {
					maxPage = Number.parseInt(lastPage[1]);
				}
			}
		}
	}
	if (res.headers.get("X-RateLimit-Remaining") === "0") {
		let resetTime = res.headers.get("X-RateLimit-Reset");
		if (resetTime) {
			await new Promise((resolve) => {
				let resetDate = new Date(Number.parseInt(resetTime) * 1000);
				let now = new Date();
				let waitTime = resetDate.getTime() - now.getTime();
				console.log(`Rate limit exceeded. Waiting for ${waitTime}ms`);
				// github will sometimes rate limit you saying you need to wait -60ms????
				setTimeout(resolve, waitTime + 5000);
			});
		}
	}
	return { maxPage, res: await res.json() };
}

export interface CodeSearchResult {
	owner: string;
	repo: string;
}

async function* searchForFastCheckRepos(
	searchStrings: string[],
): AsyncGenerator<CodeSearchResult[]> {
	for (const searchString of searchStrings) {
		let page = 1;
		while (true) {
			let searchUrl = `https://api.github.com/search/code?q=${encodeURIComponent(
				searchString,
			)}&page=${page}&per_page=100`;
			let { maxPage, res } = await callGh(searchUrl);
			if (res.total_count === 0 || page > maxPage) {
				break;
			}
			console.log(
				`Found ${res.items.length} results for ${searchString} (page ${page})`,
			);
			yield res.items.map((item: any) => {
				const [owner, repo] = item.repository.full_name.split("/");
				return { owner, repo };
			});
			page++;
		}
	}
}

const cacheFile = (await Bun.file("./cache.json").json()) || {};

if (!cacheFile.offset) cacheFile.offset = 0;
if (!cacheFile.repos) cacheFile.repos = [];

// A set of repos that use fast-check
const fastCheckRepos: Set<string> = new Set(
	cacheFile.repos.map((repo: CodeSearchResult) => `${repo.owner}/${repo.repo}`),
);
async function* getNewFastCheckReposViaApi(
	searchStrings: string[],
	fastCheckRepos: Set<string>,
): AsyncGenerator<CodeSearchResult> {
	for await (const batch of searchForFastCheckRepos(searchStrings)) {
		cacheFile.offset += 1;
		for (const repo of batch) {
			const repoFullName = `${repo.owner}/${repo.repo}`;
			if (!fastCheckRepos.has(repoFullName)) {
				fastCheckRepos.add(repoFullName);
				cacheFile.repos = Array.from(fastCheckRepos);
				await Bun.write("./cache.json", JSON.stringify(cacheFile, null, 2));
				yield repo;
			}
		}
	}
}

const DATA_FILE = path.resolve('../dependents-ts.json');
async function* getNewFastCheckReposViaDependents(
	fastCheckRepos: Set<string>,
): AsyncGenerator<CodeSearchResult> {
	const dependents = (await Bun.file(DATA_FILE).json()).dependents;
	for (const dependent of dependents) {
		const [owner, repo] = dependent.split("/");
		const repoFullName = `${owner}/${repo}`;
		if (!fastCheckRepos.has(repoFullName)) {
			fastCheckRepos.add(repoFullName);
			cacheFile.repos = Array.from(fastCheckRepos);
			await Bun.write("./cache.json", JSON.stringify(cacheFile, null, 2));
			yield { owner, repo };
		}
	}
}

export function* chunkGenerator<T>(array: T[], size: number) {
	for (let i = 0; i < array.length; i += size) {
		yield array.slice(i, i + size);
	}
}

for await (const repo of getNewFastCheckReposViaDependents(fastCheckRepos)) {
	console.log(`Would scrape repo ${repo.owner}/${repo.repo}`);
	const match =
		await sql`SELECT parsed_at, id FROM scrapedrepos WHERE name = ${repo.owner + "/" + repo.repo} LIMIT 1`.execute();
	if (match.count !== 0) {
		console.log(`  Repo ${repo.owner}/${repo.repo} already scraped`);
		continue;
	}
	const repoInfo = await callGh(
		`https://api.github.com/repos/${repo.owner}/${repo.repo}`,
	);
	const [license, license_status] = await hasLegalLicense(repoInfo.res);
	// todo: fix date
	let insert_res =
		await sql`INSERT INTO scrapedrepos (source, name, url, license, license_status, stars, forks, parsed_at) \
	VALUES ('gh', ${repoInfo.res.full_name}, ${repoInfo.res.clone_url}, ${license || null}, ${license_status || "none"}, ${repoInfo.res.stargazers_count}, ${repoInfo.res.forks}, ${new Date().toISOString()})\
	RETURNING id, hash`.execute();

	if (license_status !== "ok") {
		continue;
	}

	let repoId = match[0]?.id || insert_res[0].id;
	let oldHash = match[0]?.hash;

	// Clone the repository
	await new Promise<void>((resolve, reject) => {
		exec(
			`git clone https://github.com/${repo.owner}/${repo.repo}.git ./repos/${repo.owner}/${repo.repo}`,
			(error, stdout, stderr) => {
				if (error) {
					console.error(
						`  Error cloning repo ${repo.owner}/${repo.repo}: ${error.message}`,
					);
					reject();
				}
				if (stderr) {
					console.log(stderr);
				}
				resolve();
			},
		);
	});

	const hash = await new Promise<string>((resolve, reject) => {
		exec(
			`git -C ./repos/${repo.owner}/${repo.repo} rev-parse HEAD`,
			(error, stdout, stderr) => {
				if (error) {
					console.error(
						`  Error getting hash for repo ${repo.owner}/${repo.repo}: ${error.message}`,
					);
					reject(error);
					return;
				}
				resolve(stdout.trim());
			},
		);
	});

	if (oldHash && oldHash === hash) {
		console.log(`  Repo ${repo.owner}/${repo.repo} already scraped`);
		continue;
	}

	await sql`UPDATE scrapedrepos SET hash = ${hash} WHERE id = ${repoId}`.execute();

	const files = await new Promise<string[]>((resolve, reject) => {
		exec(
			`rg -l "(import\\s+.*\\s+from\\s+|require\\s*\\()\\s*['\\"]fast-check['\\"]" --glob "*.js" --glob "*.ts" ./repos/${repo.owner}/${repo.repo}`,
			(error, stdout, stderr) => {
				if (error) {
					console.error(
						`  No matches on repo ${repo.owner}/${repo.repo}: ${error.message}`,
					);
					resolve([]);
				}
				if (stderr) {
					console.error(`stderr: ${stderr}`);
				}
				resolve(stdout.split("\n").filter((file) => file));
			},
		);
	});

	await sql`DELETE FROM scrapedtests where repo_id = ${repoId}`.execute();

	const pendingInsert = files.map((localFile) => {
		console.log(
			`  Scraping file ${localFile} in repo ${repo.owner}/${repo.repo}`,
		);
		const loadedFile = loadFile(localFile);
		return loadedFile.tests.map((test) => {
			const localFunctionsWeFound = test.functionsCalledInTest.flatMap((fn) => {
				const match = loadedFile.localFunctions[fn];
				if (match?.called && match?.sourceCode) {
					return [[match.searchName, match.sourceCode]];
				}
				return [];
			});
			return {
				test,
				depNames: localFunctionsWeFound.map((f) => f[0]),
				deps: localFunctionsWeFound.map((f) => f[1]),
				fileName: localFile,
			};
		});
	});

	// INSERT INTO scrapedtests (repo_id, pbt_name, pbt, dep_names, deps, source) VALUES
	for (const chunk of chunkGenerator(pendingInsert.flat(), 5)) {
		await sql`
			INSERT INTO scrapedtests (repo_id, pbt_name, pbt, dep_names, deps, source, mode, summaryconfidence)
			VALUES ${sql(
			chunk.map((test) => [
				repoId,
				test.test.testName,
				test.test.test,
				test.depNames,
				test.deps,
				test.fileName,
				"fast-check",
				1,
			]),
		)}
		`.execute();
	}
	console.log(
		`  Inserted ${pendingInsert.flat().length} tests for repo ${repo.owner}/${repo.repo}`,
	);
}
