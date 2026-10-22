import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const articleSchema = z.object({
	title: z.string(),
	published: z.coerce.date(),
	updated: z.coerce.date().optional(),
	draft: z.boolean().default(false),
	description: z.string().default(""),
	image: z.string().default(""),
	tags: z.array(z.string()).default([]),
	category: z.string().nullable().default(""),
	lang: z.string().default(""),
	originalPath: z.string().optional(),
	wpId: z.number().int().optional(),
	wpTimezone: z.string().optional(),
	wpType: z.string().optional(),
	wpCategories: z.array(z.string()).default([]),
	wordCount: z.number().int().nonnegative().optional(),
	prevTitle: z.string().default(""),
	prevSlug: z.string().default(""),
	nextTitle: z.string().default(""),
	nextSlug: z.string().default(""),
});

export const collections = {
	posts: defineCollection({
		loader: glob({ pattern: "**/*.md", base: "./src/content/posts" }),
		schema: articleSchema,
	}),
	"legacy-pages": defineCollection({
		loader: glob({ pattern: "**/*.md", base: "./src/content/legacy-pages" }),
		schema: articleSchema,
	}),
	spec: defineCollection({
		loader: glob({ pattern: "**/*.md", base: "./src/content/spec" }),
		schema: z.object({}),
	}),
};
