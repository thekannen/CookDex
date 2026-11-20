import React from "react";
import Icon from "../../components/Icon";
import { DOCS_URL } from "../../constants";
import { formatDateTime } from "../../utils.jsx";
import { FORKED_APP_STORE_URL, FORKED_ROADMAP_URL } from "../../features/forked/forked";
import appStoreBadge from "../../assets/app-store-badge-black.svg";
import forkedIcon from "../../assets/forked-icon-112.png";
import forkedIconDark from "../../assets/forked-icon-dark-112.png";
import forkedQr from "../../assets/forked-app-store-qr.svg";

export default function AboutPage({ aboutMeta, healthMeta, lastLoadedAt }) {
  const appVersion = aboutMeta?.app_version || healthMeta?.version || "-";
  const backendStatus = healthMeta?.ok === false ? "Degraded" : "Connected";
  const lastSyncLabel = lastLoadedAt ? formatDateTime(lastLoadedAt) : "-";

  return (
    <section className="page-grid about-grid">
      <div className="about-column">
        <article className="card">
          <h3><Icon name="info" /> CookDex v{appVersion}</h3>
          <ul className="kv-list">
            <li>
              <span>Latest release</span>
              <strong>{aboutMeta?.update?.latest ? `v${aboutMeta.update.latest}` : "Unknown"}</strong>
            </li>
            <li>
              <span>Server</span>
              <strong>{backendStatus}</strong>
            </li>
            <li>
              <span>This page's data loaded</span>
              <strong>{lastSyncLabel}</strong>
            </li>
            <li>
              <span>License</span>
              <strong>AGPL-3.0</strong>
            </li>
          </ul>
        </article>

        <article className="card">
          <h3><Icon name="external" /> Project Links</h3>
          <a
            className="link-btn"
            href={aboutMeta?.links?.docs || DOCS_URL}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="external" />
            Documentation
          </a>
          <a
            className="link-btn"
            href={aboutMeta?.links?.github || "https://github.com/thekannen/cookdex"}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="github" />
            GitHub Repository
          </a>
          <a
            className="link-btn sponsor-btn"
            href={aboutMeta?.links?.sponsor || "https://github.com/sponsors/thekannen"}
            target="_blank"
            rel="noreferrer"
          >
            <svg className="ui-icon" viewBox="0 0 16 16" fill="#db61a2" aria-hidden="true">
              <path d="m8 14.25.345.666a.75.75 0 0 1-.69 0l-.008-.004-.018-.01a7.152 7.152 0 0 1-.31-.17 22.055 22.055 0 0 1-3.434-2.414C2.045 10.731 0 8.35 0 5.5 0 2.836 2.086 1 4.25 1 5.797 1 7.153 1.802 8 3.02 8.847 1.802 10.203 1 11.75 1 13.914 1 16 2.836 16 5.5c0 2.85-2.045 5.231-3.885 6.818a22.066 22.066 0 0 1-3.744 2.584l-.018.01-.006.003h-.002Z" />
            </svg>
            Sponsor
          </a>
        </article>
      </div>

      <article className="card">
        <h3><Icon name="shield" /> Privacy &amp; Data</h3>
        <ul className="kv-list">
          <li>
            <span>Telemetry</span>
            <strong>None</strong>
          </li>
          <li>
            <span>Analytics &amp; Tracking</span>
            <strong>None</strong>
          </li>
          <li>
            <span>Credentials</span>
            <strong>Local only, encrypted at rest</strong>
          </li>
          <li>
            <span>Talks to</span>
            <strong>Your Mealie, and only what you switch on</strong>
          </li>
        </ul>
        <p className="privacy-detail">
          CookDex has no analytics or usage tracking. By default, the server checks
          GitHub for a new release about once a day, sending only the CookDex version
          in its request header. No recipes, credentials, or user identifiers are included.
          GitHub receives the server's network address as part of the connection.
          Turn off Check for updates in Settings to disable these requests.
          Credentials are stored locally, encrypted at rest, and used only with
          the services you configure.
        </p>
        <p className="privacy-detail">
          <strong>AI helper.</strong> If you set one up, recipe names, a short description and
          ingredient lists are sent to it (OpenAI, Anthropic, or Ollama on your own machine) when a job asks
          for suggestions. Nothing else from your recipes is sent.
        </p>
        <p className="privacy-detail">
          <strong>Discover.</strong> When you import from recipe sites, CookDex fetches pages from
          each site you've switched on, so those sites see your server's network address, as they
          would for any visitor. No sites are switched on until you choose them.
        </p>
      </article>

      <ForkedCard />
    </section>
  );
}

// Forked is Knownframe's iOS app for Mealie. CookDex's cleanup is what it
// shows off, so the card says how the two fit, not just that Forked exists.
// Every image is bundled: the page makes no request to Apple or anyone else.
function ForkedCard() {
  return (
    <article className="card forked-card" aria-labelledby="forked-card-title">
      <div className="forked-card-body">
        <div className="forked-card-intro">
          <span className="forked-mark" aria-hidden="true">
            <img className="forked-mark-light" src={forkedIcon} width="56" height="56" alt="" />
            <img className="forked-mark-dark" src={forkedIconDark} width="56" height="56" alt="" />
          </span>
          <div>
            <p className="forked-eyebrow">Also from Knownframe · iOS app</p>
            <h3 id="forked-card-title">Cook from your library with Forked</h3>
          </div>
        </div>
        <p className="forked-lede">
          A native iPhone and iPad app for your Mealie library: browse recipes as photo cards, plan your meals, and
          keep a shopping list that stays in step with Mealie. The cleanup CookDex does is what makes it work well.
        </p>
        <ul className="forked-fit">
          <li><strong>Tags and categories</strong> drive its filters and smart cookbooks.</li>
          <li><strong>Parsed ingredients</strong> combine on the shopping list and let diet and allergy filters see each food.</li>
          <li><strong>Servings</strong> let every recipe scale its amounts.</li>
        </ul>
        <p className="privacy-detail">Free to download. Forked Pro is an optional one-time upgrade.</p>
      </div>
      <div className="forked-get">
        <a className="forked-badge" href={FORKED_APP_STORE_URL} target="_blank" rel="noreferrer">
          <img src={appStoreBadge} width="144" height="48" alt="Download on the App Store" />
        </a>
        <figure className="forked-qr">
          <img src={forkedQr} width="112" height="112" alt="QR code that opens Forked on the App Store" />
          <figcaption>Scan with your iPhone camera</figcaption>
        </figure>
        <a className="link-inline forked-roadmap" href={FORKED_ROADMAP_URL} target="_blank" rel="noreferrer">
          Roadmap and feature requests ↗
        </a>
      </div>
    </article>
  );
}
