import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import Icon from "../../components/Icon";
import { DISCOVER_RESPONSIBLE_USE_URL } from "../../constants";
import { api } from "../../utils.jsx";

// Shown until an owner accepts, in place of Discover's run controls. Nothing
// runs the dredger before then: not a preview, an import or an automation.
export default function ResponsibleUse({ canAccept, onError }) {
  const queryClient = useQueryClient();
  const accept = useMutation({
    mutationFn: () => api("/discover/responsible-use", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discover"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (exc) => onError?.(exc),
  });

  return (
    <section className="discover-terms" aria-labelledby="discover-terms-title">
      <h3 id="discover-terms-title"><Icon name="shield" /> Before you use Discover</h3>
      <p>
        Discover visits the recipe sites you switch on or add, and copies their recipes into your Mealie. Some sites'
        terms of use don't allow automated visits like this.
      </p>
      <ul>
        <li>You choose which sites Discover visits, so checking and following each site's terms is up to you.</li>
        <li>
          The suggested sources didn't ban this when we last read their terms, but terms change. Sites you add yourself
          haven't been checked by anyone.
        </li>
        <li>Discover is for your own recipe collection. Don't use it to republish other people's recipes.</li>
        <li>CookDex is provided as-is, without any warranty, and its authors aren't responsible for how it's used.</li>
      </ul>
      <p className="muted tiny">
        CookDex always says who it is, follows each site's robots.txt and waits between requests.{" "}
        <a href={DISCOVER_RESPONSIBLE_USE_URL} target="_blank" rel="noreferrer">Read more about using Discover responsibly</a>
      </p>
      {canAccept ? (
        <button type="button" className="primary" disabled={accept.isPending} onClick={() => accept.mutate()}>
          {accept.isPending ? "Saving…" : "I understand and accept"}
        </button>
      ) : (
        <p className="muted">An owner has to accept this before anyone can use Discover.</p>
      )}
    </section>
  );
}
