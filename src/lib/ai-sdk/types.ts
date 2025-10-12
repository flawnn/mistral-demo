import { z } from "zod";

export interface AIResponse {
  content: string;
  error?: string;
}

export interface AIQueryOptions {
  temperature?: number;
  maxTokens?: number;
  stream?: boolean;
}

export const LocationQuerySchema = z.object({
  coordinates: z.string().describe("Coordinates in 'lat,lon' format"),
  type: z.string().describe("Type of object to detect"),
  radius: z.number().nullable().describe("Search radius in meters"),
  error: z
    .string()
    .nullable()
    .describe("Error message if query cannot be processed"),
});

export type LocationQuery = z.infer<typeof LocationQuerySchema>;

// Key places mapping for the system prompt
export const KEY_PLACES = {
  "ETH Zurich": "47.376440,8.548157",
  "JFK Airport": "40.6413,-73.7809",
  "Chrysler car factory in Detroit": "42.379616, -82.969175",
  "Amsterdam Airport Schiphol": "52.3128,4.7402",
  "Berlin Brandenburg Airport": "52.3650,13.5010",
  // Add more key places as needed
} as const;
