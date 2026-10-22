// biome-ignore lint/suspicious/noShadowRestrictedNames: <toString from mdast-util-to-string>
import { toString } from "mdast-util-to-string";
import getReadingTime from "reading-time";
import sanitizeHtml from "sanitize-html";

function visibleText(node) {
	if (node.type === "html") {
		return sanitizeHtml(node.value, { allowedTags: [], allowedAttributes: {} });
	}
	if (node.type === "text" || node.type === "code") return node.value;
	return (node.children || []).map(visibleText).join(" ");
}

export function remarkReadingTime() {
	return (tree, { data }) => {
		const textOnPage = visibleText(tree) || toString(tree);
		const readingTime = getReadingTime(textOnPage);
		data.astro.frontmatter.minutes = Math.max(
			1,
			Math.round(readingTime.minutes),
		);
		data.astro.frontmatter.words = readingTime.words;
	};
}
