import { useQuery } from "@tanstack/react-query";

import { api } from "../../utils.jsx";

// Mealie's wording, used until /provider answers (and in tests).
export const DEFAULT_PROVIDER = {
  kind: "mealie",
  name: "Mealie",
  capabilities: [],
  term_kinds: ["tags", "categories", "tools"],
  vocabulary: {
    backend: "Mealie",
    terms: { tags: "Tags", categories: "Categories", tools: "Tools" },
    term_singular: { tags: "tag", categories: "category", tools: "tool" },
    collections: "Cookbooks",
    address_label: "Mealie address",
    token_label: "Mealie API token",
  },
};

// Which recipe manager CookDex is connected to, what it can do, and the
// words to use for it. Features should check capabilities, not the name.
export function useProvider() {
  const query = useQuery({ queryKey: ["provider"], queryFn: () => api("/provider"), staleTime: Infinity });
  const provider = query.data || DEFAULT_PROVIDER;
  return {
    ...provider,
    has: (capability) => (provider.capabilities || []).includes(capability),
    isLoading: query.isLoading,
  };
}
