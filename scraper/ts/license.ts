import type { Repo } from ".";

const allowedLicenses = [
	"MIT",
	"MIT-0",
	"Apache-2.0",
	"ISC",
	"0BSD",
	"BSD-1-Clause",
	"BSD-2-Clause",
	"BSD-3-Clause",
	"Unlicense",
	"BlueOak-1.0.0",
	"CC0-1.0",
];

const disallowedLicenses = [
	"AGPL-3.0",
	"GPL-3.0",
	"GPL-2.0",
	"LGPL-3.0",
	"LGPL-2.1",
	"MPL-2.0",
];

//
export async function hasLegalLicense(
	repo: Repo,
): Promise<[string | false, string]> {
	try {
		if (!repo.license) {
			await fetch(
				`https://api.github.com/repos/${repo.owner}/${repo.repo}/license`,
				{
					headers: {
						Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
						Accept: "application/vnd.github.v3+json",
					},
				},
			)
				.then((response) => {
					if (response.status === 404) {
						return [false, "unknown"];
					}
					return response.json();
				})
				.then((data) => {
					repo.license = data;
				})
				.catch((error) => {
					console.error("Error fetching license:", error);
				});
		}

		if (!repo.license) {
			return [false, "unknown"];
		}

		const spdxId = repo.license.spdx_id;

		if (allowedLicenses.includes(spdxId)) {
			return [spdxId, "ok"];
		}

		if (disallowedLicenses.includes(spdxId)) {
			return [spdxId, "bad"];
		}

		console.log(repo.license.name);
		return [spdxId, "unknown"];
	} catch (error) {
		return [false, "unknown"];
	}
}
