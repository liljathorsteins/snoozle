import { z, defineCollection } from "astro:content";

export const collections = {
  articles: defineCollection({
    schema: z.object({
      title: z.string(),
      description: z.string(),
      published: z.string(),
      showComparison: z.boolean().default(true),
      reviewedBy: z.string(),
    }),
  }),
};
