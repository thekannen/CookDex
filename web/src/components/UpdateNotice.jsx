import React, { useState } from 'react';
import { showUpdate, readDismissed, dismissUpdate, updateStorage } from './updateNoticeState.mjs';

export default function UpdateNotice({ status }) {
  const [dismissed, setDismissed] = useState(() => readDismissed(updateStorage()));
  if (!showUpdate(status, dismissed)) return null;
  return <div className="banner info" role="status">
    <span>CookDex v{status.latest} is available — <a href={status.release_url} target="_blank" rel="noreferrer">release notes</a></span>
    <button className="banner-close" aria-label="Dismiss update notice"
      onClick={() => setDismissed(dismissUpdate(updateStorage(), status.latest))}>×</button>
  </div>;
}
