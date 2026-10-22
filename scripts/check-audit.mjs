const reviewedPaths = new Set([
	".>@tailwindcss/typography>tailwindcss>chokidar>braces",
	".>@tailwindcss/typography>tailwindcss>fast-glob>micromatch>braces",
	".>@tailwindcss/typography>tailwindcss>micromatch>braces",
	".>tailwindcss>chokidar>braces",
	".>tailwindcss>fast-glob>micromatch>braces",
	".>tailwindcss>micromatch>braces",
]);
const severities = ["info", "low", "moderate", "high", "critical"];

function isReviewedBuildIssue(advisory) {
	// Fixed repository-owned Tailwind globs never accept visitor input. No
	// watcher or brace parser ships in dist. Re-review as soon as a fix exists.
	return (
		advisory.id === 1240992 &&
		advisory.github_advisory_id === "GHSA-vfj7-8cjw-p6xm" &&
		advisory.module_name === "braces" &&
		advisory.severity === "high" &&
		advisory.patched_versions === null &&
		Array.isArray(advisory.findings) &&
		advisory.findings.length > 0 &&
		advisory.findings.every(
			(finding) =>
				finding.version === "3.0.3" &&
				Array.isArray(finding.paths) &&
				finding.paths.length > 0 &&
				finding.paths.every((path) => reviewedPaths.has(path)),
		)
	);
}

async function main() {
	let input = "";
	for await (const chunk of process.stdin) input += chunk;
	const report = JSON.parse(input.replace(/^\uFEFF/, ""));
	const advisories = report.advisories;
	const counts = report.metadata?.vulnerabilities;
	if (
		!advisories ||
		typeof advisories !== "object" ||
		Array.isArray(advisories) ||
		!counts ||
		severities.some(
			(severity) => !Number.isInteger(counts[severity]) || counts[severity] < 0,
		)
	) {
		throw new Error("Unknown or incomplete pnpm audit JSON; refusing to pass.");
	}

	const entries = Object.values(advisories);
	const observed = Object.fromEntries(
		severities.map((severity) => [severity, 0]),
	);
	for (const advisory of entries) {
		if (!severities.includes(advisory?.severity)) {
			throw new Error("Unknown advisory severity; refusing to pass.");
		}
		observed[advisory.severity]++;
	}
	if (severities.some((severity) => observed[severity] !== counts[severity])) {
		throw new Error(
			"Audit counts disagree with advisory details; refusing to pass.",
		);
	}

	const unexpected = entries.filter(
		(advisory) => !isReviewedBuildIssue(advisory),
	);
	if (unexpected.length > 0) {
		for (const advisory of unexpected) {
			console.error(
				`${advisory.severity}: ${advisory.module_name} ${advisory.github_advisory_id || advisory.id}`,
			);
		}
		throw new Error(
			`${unexpected.length} unreviewed dependency advisory/advisories.`,
		);
	}

	console.log(
		entries.length === 0
			? "No known dependency vulnerabilities."
			: "Only reviewed build-tool issue GHSA-vfj7-8cjw-p6xm (braces 3.0.3, fixed Tailwind globs).",
	);
}

main().catch((error) => {
	console.error(error.message);
	process.exitCode = 1;
});
